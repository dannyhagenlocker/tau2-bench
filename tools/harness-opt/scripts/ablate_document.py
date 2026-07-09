"""Ablation: which document signals best recover hand-labeled root causes?

For each (embedder, document field-subset) we embed the labeled failing traces,
cluster them (agglomerative cosine; best threshold by V-measure), and score the
clustering against the ground-truth root-cause labels
(tools/harness-opt/eval/root_cause_labels.<run>.json) with V-measure / ARI.

This tells us *which* "why" signals (NL, escalation, last message, tool errors)
carry root-cause information, on top of the structured core spine. Also reports
the signature engine's score for reference. Writes eval/ablation.<run>.{json,md}.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.bootstrap import bootstrap

bootstrap()

from contracts.models import FeaturesArtifact  # noqa: E402
from lib.clustering import (  # noqa: E402
    assign_cluster_to_simulations,
    cluster_l0,
    cluster_l1_l2,
)
from lib.embedding_cluster import build_cluster_document, get_embedder  # noqa: E402
from lib.io import artifact_path, read_json_artifact  # noqa: E402

HARNESS_OPT = Path(__file__).resolve().parents[1]

# Document field-subsets to ablate (core spine is always present).
SUBSETS: dict[str, set[str]] = {
    "core": set(),
    "core+nl": {"nl"},
    "core+escalation": {"escalation"},
    "core+last_message": {"last_message"},
    "core+tool_errors": {"tool_errors"},
    "core+mechanism": {"mechanism"},
    "core+last+mechanism": {"last_message", "mechanism"},
    "core+esc+last": {"escalation", "last_message"},
    "core+esc+last+nl": {"escalation", "last_message", "nl"},
    "all_why": {"nl", "escalation", "last_message", "tool_errors", "mechanism"},
}
EMBEDDERS = ["tfidf", "char", "lsa", "st"]
THRESHOLDS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]


def _cluster(vectors, threshold: float) -> list[int]:
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering

    if len(vectors) <= 1:
        return [0] * len(vectors)
    if np.allclose(vectors, vectors[0]):
        return [0] * len(vectors)
    return [
        int(x)
        for x in AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=threshold,
            metric="cosine",
            linkage="average",
        ).fit_predict(vectors)
    ]


def _score(y_true: list[str], y_pred: list[int]) -> dict:
    from sklearn.metrics import (
        adjusted_rand_score,
        homogeneity_completeness_v_measure,
    )

    hom, comp, vm = homogeneity_completeness_v_measure(y_true, y_pred)
    return {
        "v_measure": round(float(vm), 3),
        "homogeneity": round(float(hom), 3),
        "completeness": round(float(comp), 3),
        "ari": round(float(adjusted_rand_score(y_true, y_pred)), 3),
        "n_clusters": len(set(y_pred)),
    }


def _best_over_thresholds(vectors, y_true: list[str]) -> dict:
    best = None
    for thr in THRESHOLDS:
        s = _score(y_true, _cluster(vectors, thr))
        s["threshold"] = thr
        if best is None or s["v_measure"] > best["v_measure"]:
            best = s
    return best


def run_ablation(run_name: str, *, overwrite: bool = False) -> dict:
    import numpy as np

    features = read_json_artifact(
        artifact_path(run_name, "features.json"), FeaturesArtifact
    )
    labels_path = HARNESS_OPT / "eval" / f"root_cause_labels.{run_name}.json"
    gold = json.loads(labels_path.read_text())["labels"]

    by_id = {s.simulation_id: s for s in features.simulations}
    labeled_ids = [sid for sid in gold if sid in by_id]
    sims = [by_id[sid] for sid in labeled_ids]
    y_true = [gold[sid]["root_cause"] for sid in labeled_ids]

    # reference: signature engine's recovery of root causes
    l0 = cluster_l0(features.simulations, run_name)
    sig = cluster_l1_l2(features.simulations, l0, run_name)
    sig_map = assign_cluster_to_simulations(features.simulations, sig)
    sig_pred = [sig_map.get(sid, "?") for sid in labeled_ids]
    signature_ref = _score(y_true, sig_pred)

    results: list[dict] = []
    for emb_name in EMBEDDERS:
        embedder = get_embedder(emb_name)
        for subset_name, fields in SUBSETS.items():
            docs = [build_cluster_document(s, fields=fields) for s in sims]
            try:
                vectors = np.asarray(embedder.embed(docs), dtype=float)
            except Exception as exc:
                results.append(
                    {"embedder": emb_name, "subset": subset_name, "error": str(exc)}
                )
                continue
            best = _best_over_thresholds(vectors, y_true)
            best.update({"embedder": emb_name, "subset": subset_name})
            results.append(best)

    ok = [r for r in results if "error" not in r]
    best_overall = max(ok, key=lambda r: r["v_measure"]) if ok else None
    # ARI rewards correct pairwise grouping (penalizes over-splitting), so it
    # aligns better with "one cluster = one root cause" than V-measure, whose
    # homogeneity term rewards pure-but-fragmented clusterings.
    best_by_ari = max(ok, key=lambda r: r["ari"]) if ok else None

    # marginal contribution of each single why-field over core (best embedder)
    marginal = _marginal_contributions(results, best_overall)

    summary = {
        "run": run_name,
        "n_labeled": len(labeled_ids),
        "n_classes": len(set(y_true)),
        "signature_reference": signature_ref,
        "best": best_overall,
        "best_by_ari": best_by_ari,
        "marginal_over_core": marginal,
        "results": results,
    }

    eval_dir = HARNESS_OPT / "eval"
    out_json = eval_dir / f"ablation.{run_name}.json"
    out_md = eval_dir / f"ablation.{run_name}.md"
    if (out_json.exists() or out_md.exists()) and not overwrite:
        raise FileExistsError(f"Refusing to overwrite ablation artifacts in {eval_dir}")
    out_json.write_text(json.dumps(summary, indent=2))
    out_md.write_text(_render_md(summary))
    return summary


def _marginal_contributions(results: list[dict], best_overall: dict | None) -> dict:
    if not best_overall:
        return {}
    emb = best_overall["embedder"]
    by_subset = {
        r["subset"]: r["v_measure"]
        for r in results
        if r.get("embedder") == emb and "error" not in r
    }
    core = by_subset.get("core")
    if core is None:
        return {}
    out = {"embedder": emb, "core_v_measure": core, "deltas": {}}
    for subset in (
        "core+nl",
        "core+escalation",
        "core+last_message",
        "core+tool_errors",
    ):
        if subset in by_subset:
            out["deltas"][subset.replace("core+", "")] = round(
                by_subset[subset] - core, 3
            )
    return out


def _render_md(s: dict) -> str:
    b = s["best"]
    ref = s["signature_reference"]
    lines = [
        f"# Document ablation — {s['run']}",
        "",
        f"{s['n_labeled']} labeled failures, {s['n_classes']} root-cause classes. "
        "Score = V-measure of clustering vs hand-labeled root cause (best threshold).",
        "",
        f"**Signature engine reference:** V-measure={ref['v_measure']}, "
        f"ARI={ref['ari']}, {ref['n_clusters']} clusters",
        "",
    ]
    if b:
        lines += [
            f"**Best by V-measure (purity):** embedder=`{b['embedder']}`, "
            f"doc=`{b['subset']}`, threshold={b['threshold']} \u2192 "
            f"V-measure={b['v_measure']}, ARI={b['ari']}, {b['n_clusters']} clusters",
            "",
        ]
    ba = s.get("best_by_ari")
    if ba:
        lines += [
            f"**Best by ARI (grouping \u2014 our target):** embedder=`{ba['embedder']}`, "
            f"doc=`{ba['subset']}`, threshold={ba['threshold']} \u2192 "
            f"ARI={ba['ari']}, V-measure={ba['v_measure']}, {ba['n_clusters']} clusters",
            "",
        ]
    mc = s.get("marginal_over_core")
    if mc and mc.get("deltas"):
        lines += [
            f"## Marginal V-measure vs core spine (embedder=`{mc['embedder']}`, "
            f"core={mc['core_v_measure']})",
            "",
            "| Added signal | \u0394 V-measure |",
            "|--------------|------------|",
        ]
        for k, v in sorted(mc["deltas"].items(), key=lambda kv: -kv[1]):
            lines.append(f"| {k} | {v:+.3f} |")
        lines.append("")
    lines += [
        "## All configs (sorted by V-measure)",
        "",
        "| embedder | document | V-measure | ARI | homog | compl | k | thr |",
        "|----------|----------|-----------|-----|-------|-------|---|-----|",
    ]
    ok = [r for r in s["results"] if "error" not in r]
    ok.sort(key=lambda r: -r["v_measure"])
    for r in ok:
        lines.append(
            f"| {r['embedder']} | {r['subset']} | {r['v_measure']} | {r['ari']} | "
            f"{r['homogeneity']} | {r['completeness']} | {r['n_clusters']} | "
            f"{r['threshold']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ablate document signals vs labels")
    parser.add_argument("--run", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    summary = run_ablation(args.run, overwrite=args.overwrite)
    b = summary["best"]
    ba = summary.get("best_by_ari")
    ref = summary["signature_reference"]
    print(f"signature reference: V-measure={ref['v_measure']} ARI={ref['ari']}")
    if b:
        print(
            f"best V-measure: embedder={b['embedder']} doc={b['subset']} "
            f"V-measure={b['v_measure']} ARI={b['ari']} k={b['n_clusters']}"
        )
    if ba:
        print(
            f"best ARI: embedder={ba['embedder']} doc={ba['subset']} "
            f"ARI={ba['ari']} V-measure={ba['v_measure']} k={ba['n_clusters']}"
        )
    print(f"marginal_over_core: {summary.get('marginal_over_core', {}).get('deltas')}")
    print(f"Wrote eval/ablation.{args.run}.{{json,md}}")


if __name__ == "__main__":
    main()
