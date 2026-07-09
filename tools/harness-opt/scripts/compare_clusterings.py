"""Compare the signature vs embedding clustering engines on one run.

Runs both engines in-memory over the same features.json and reports how much
they agree (Adjusted Rand Index, homogeneity/completeness/V-measure), how
"pure" each embedding cluster is w.r.t. signatures, and concrete disagreements.
Writes reports/<run>/clusters_comparison.{json,md}. Never touches clusters.json.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict

from lib.bootstrap import bootstrap

bootstrap()

from contracts.models import FeaturesArtifact  # noqa: E402
from lib.clustering import (  # noqa: E402
    assign_cluster_to_simulations,
    cluster_l0,
    cluster_l1_l2,
)
from lib.embedding_cluster import cluster_embeddings, get_embedder  # noqa: E402
from lib.io import artifact_path, read_json_artifact, write_text_artifact  # noqa: E402


def _labels_for_failing(
    assignment: dict[str, str], failing_ids: list[str]
) -> list[str]:
    return [assignment.get(sid, "?") for sid in failing_ids]


def _singletons(clusters) -> int:
    return sum(1 for c in clusters.clusters if c.count == 1)


def run_compare(
    run_name: str,
    *,
    embedder: str = "st",
    scope: str = "global",
    algo: str = "agglomerative",
    distance_threshold: float = 0.0,  # <=0 => auto per run
    overwrite: bool = False,
) -> dict:
    features = read_json_artifact(
        artifact_path(run_name, "features.json"), FeaturesArtifact
    )
    sims = features.simulations

    l0 = cluster_l0(sims, run_name)
    sig = cluster_l1_l2(sims, l0, run_name)
    emb = cluster_embeddings(
        sims,
        run_name,
        embedder=get_embedder(embedder),
        scope=scope,
        algo=algo,
        distance_threshold=distance_threshold,
    )

    sig_map = assign_cluster_to_simulations(sims, sig)
    emb_map = assign_cluster_to_simulations(sims, emb)

    failing_ids = [s.simulation_id for s in sims if s.failure_type.value != "pass"]
    sig_labels = _labels_for_failing(sig_map, failing_ids)
    emb_labels = _labels_for_failing(emb_map, failing_ids)

    metrics: dict = {}
    try:
        from sklearn.metrics import (
            adjusted_rand_score,
            homogeneity_completeness_v_measure,
        )

        metrics["adjusted_rand_index"] = float(
            adjusted_rand_score(sig_labels, emb_labels)
        )
        hom, comp, vm = homogeneity_completeness_v_measure(sig_labels, emb_labels)
        metrics["homogeneity"] = float(hom)
        metrics["completeness"] = float(comp)
        metrics["v_measure"] = float(vm)
    except Exception as exc:  # pragma: no cover
        metrics["error"] = str(exc)

    # per embedding cluster: signature composition (purity)
    emb_members: dict[str, list[str]] = defaultdict(list)
    for sid, label in zip(failing_ids, emb_labels):
        emb_members[label].append(sid)
    sig_cluster_name = {c.id: c.signature or c.name for c in sig.clusters}
    emb_purity = []
    for cid, members in sorted(emb_members.items(), key=lambda kv: -len(kv[1])):
        comp = Counter(sig_cluster_name.get(sig_map.get(m, "?"), "?") for m in members)
        top_sig, top_n = comp.most_common(1)[0]
        emb_purity.append(
            {
                "embedding_cluster": cid,
                "size": len(members),
                "purity": round(top_n / len(members), 3),
                "dominant_signature": top_sig,
                "signature_mix": dict(comp),
            }
        )

    summary = {
        "run": run_name,
        "embedder": embedder,
        "scope": scope,
        "algo": algo,
        "distance_threshold": distance_threshold,
        "n_failures": len(failing_ids),
        "signature": {
            "n_clusters": len(sig.clusters),
            "singletons": _singletons(sig),
        },
        "embedding": {
            "n_clusters": len(emb.clusters),
            "singletons": _singletons(emb),
        },
        "agreement": metrics,
        "embedding_cluster_purity": emb_purity,
    }

    write_text_artifact(
        run_name,
        "clusters_comparison.json",
        json.dumps(summary, indent=2),
        overwrite=overwrite,
    )
    write_text_artifact(
        run_name,
        "clusters_comparison.md",
        _render_md(summary),
        overwrite=overwrite,
    )
    return summary


def _render_md(s: dict) -> str:
    ag = s["agreement"]
    lines = [
        f"# Clustering comparison — {s['run']}",
        "",
        f"Embedding config: embedder=`{s['embedder']}`, scope=`{s['scope']}`, "
        f"algo=`{s['algo']}`, distance_threshold={s['distance_threshold']}",
        "",
        "## Engine sizes",
        "",
        "| Engine | Clusters | Singletons |",
        "|--------|----------|------------|",
        f"| signature | {s['signature']['n_clusters']} | {s['signature']['singletons']} |",
        f"| embedding | {s['embedding']['n_clusters']} | {s['embedding']['singletons']} |",
        "",
        f"Failures compared: {s['n_failures']}",
        "",
        "## Agreement (embedding vs signature labels)",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Adjusted Rand Index | {ag.get('adjusted_rand_index', 'n/a')} |",
        f"| Homogeneity | {ag.get('homogeneity', 'n/a')} |",
        f"| Completeness | {ag.get('completeness', 'n/a')} |",
        f"| V-measure | {ag.get('v_measure', 'n/a')} |",
        "",
        "_ARI≈1: engines agree; ≈0: independent. Homogeneity high = each embedding "
        "cluster is signature-pure; completeness high = each signature stays intact._",
        "",
        "## Embedding clusters vs signatures (purity)",
        "",
        "| Emb cluster | Size | Purity | Dominant signature | Mix |",
        "|-------------|------|--------|--------------------|-----|",
    ]
    for row in s["embedding_cluster_purity"]:
        mix = "; ".join(f"{k}×{v}" for k, v in row["signature_mix"].items())
        lines.append(
            f"| {row['embedding_cluster']} | {row['size']} | {row['purity']} | "
            f"`{row['dominant_signature'][:50]}` | {mix[:80]} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare clustering engines")
    parser.add_argument("--run", required=True)
    parser.add_argument("--embedder", default="st")
    parser.add_argument("--scope", default="global", choices=["l0", "global"])
    parser.add_argument(
        "--algo", default="agglomerative", choices=["agglomerative", "hdbscan"]
    )
    parser.add_argument("--distance-threshold", type=float, default=0.0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    summary = run_compare(
        args.run,
        embedder=args.embedder,
        scope=args.scope,
        algo=args.algo,
        distance_threshold=args.distance_threshold,
        overwrite=args.overwrite,
    )
    ag = summary["agreement"]
    print(
        f"Compared {summary['n_failures']} failures: "
        f"signature={summary['signature']['n_clusters']} clusters, "
        f"embedding={summary['embedding']['n_clusters']} clusters, "
        f"ARI={ag.get('adjusted_rand_index', 'n/a')}"
    )
    print(f"Wrote clusters_comparison.{{json,md}} for {args.run}")


if __name__ == "__main__":
    main()
