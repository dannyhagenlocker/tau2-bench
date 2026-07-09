"""Sweep embedding-clustering settings to find the best configuration.

Grid: embedder x scope x algo x distance_threshold. For each config we run the
embedding engine and score the resulting clusters with:

- silhouette (cosine, on the embedder's own vectors) -- primary *unsupervised*
  quality signal: high = cohesive, well-separated clusters.
- structure: n_clusters, singleton %, largest-cluster share.
- agreement vs the signature engine (ARI / homogeneity / completeness) -- for
  context, not as ground truth.

Recommends the config with the best silhouette among "reasonable" ones (not
collapsed into one blob, not mostly singletons). Writes
reports/<run>/clusters_sweep.{json,md}.
"""

from __future__ import annotations

import argparse
import json

from lib.bootstrap import bootstrap

bootstrap()

from contracts.models import FeaturesArtifact  # noqa: E402
from lib.clustering import (  # noqa: E402
    assign_cluster_to_simulations,
    cluster_l0,
    cluster_l1_l2,
)
from lib.embedding_cluster import (  # noqa: E402
    build_cluster_document,
    cluster_embeddings,
    get_embedder,
)
from lib.io import artifact_path, read_json_artifact, write_text_artifact  # noqa: E402

DEFAULT_EMBEDDERS = ["tfidf", "char", "lsa"]
DEFAULT_THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
DEFAULT_SCOPES = ["l0", "global"]


def _structure(art) -> dict:
    counts = [c.count for c in art.clusters]
    n = sum(counts) or 1
    return {
        "n_clusters": len(art.clusters),
        "singletons": sum(1 for c in counts if c == 1),
        "singleton_pct": round(
            sum(1 for c in counts if c == 1) / max(len(counts), 1), 3
        ),
        "largest_share": round(max(counts, default=0) / n, 3),
        "mean_size": round(n / max(len(counts), 1), 2),
    }


def _silhouette(vectors, labels) -> float | None:
    uniq = set(labels)
    if len(uniq) < 2 or len(uniq) >= len(labels):
        return None
    try:
        from sklearn.metrics import silhouette_score

        return float(silhouette_score(vectors, labels, metric="cosine"))
    except Exception:
        return None


def _agreement(sig_labels, emb_labels) -> dict:
    try:
        from sklearn.metrics import (
            adjusted_rand_score,
            homogeneity_completeness_v_measure,
        )

        hom, comp, vm = homogeneity_completeness_v_measure(sig_labels, emb_labels)
        return {
            "ari": round(float(adjusted_rand_score(sig_labels, emb_labels)), 3),
            "homogeneity": round(float(hom), 3),
            "completeness": round(float(comp), 3),
            "v_measure": round(float(vm), 3),
        }
    except Exception:
        return {}


def run_sweep(
    run_name: str,
    *,
    embedders: list[str] | None = None,
    thresholds: list[float] | None = None,
    scopes: list[str] | None = None,
    include_hdbscan: bool = True,
    overwrite: bool = False,
) -> dict:
    embedders = embedders or DEFAULT_EMBEDDERS
    thresholds = thresholds or DEFAULT_THRESHOLDS
    scopes = scopes or DEFAULT_SCOPES

    features = read_json_artifact(
        artifact_path(run_name, "features.json"), FeaturesArtifact
    )
    sims = features.simulations
    failing = [s for s in sims if s.failure_type.value != "pass"]
    failing_ids = [s.simulation_id for s in failing]
    docs = [build_cluster_document(s) for s in failing]

    # signature engine reference labels (for agreement context)
    l0 = cluster_l0(sims, run_name)
    sig = cluster_l1_l2(sims, l0, run_name)
    sig_map = assign_cluster_to_simulations(sims, sig)
    sig_labels = [sig_map.get(sid, "?") for sid in failing_ids]
    sig_struct = _structure(sig)

    # cache one global embedding per embedder for silhouette scoring
    import numpy as np

    global_vecs: dict[str, object] = {}
    for emb_name in embedders:
        try:
            global_vecs[emb_name] = np.asarray(
                get_embedder(emb_name).embed(docs), dtype=float
            )
        except Exception as exc:
            global_vecs[emb_name] = exc  # record unavailable embedder

    results: list[dict] = []
    for emb_name in embedders:
        vecs = global_vecs[emb_name]
        if isinstance(vecs, Exception):
            results.append({"embedder": emb_name, "error": str(vecs)})
            continue
        for scope in scopes:
            configs = [("agglomerative", t) for t in thresholds]
            if include_hdbscan:
                configs.append(("hdbscan", None))
            for algo, thr in configs:
                art = cluster_embeddings(
                    sims,
                    run_name,
                    embedder=get_embedder(emb_name),
                    scope=scope,
                    algo=algo,
                    distance_threshold=thr if thr is not None else 0.6,
                )
                emb_map = assign_cluster_to_simulations(sims, art)
                emb_labels = [emb_map.get(sid, "?") for sid in failing_ids]
                struct = _structure(art)
                results.append(
                    {
                        "embedder": emb_name,
                        "scope": scope,
                        "algo": algo,
                        "distance_threshold": thr,
                        **struct,
                        "silhouette": _silhouette(vecs, emb_labels),
                        "agreement": _agreement(sig_labels, emb_labels),
                    }
                )

    recommendation = _recommend(results, n_failures=len(failing_ids))
    summary = {
        "run": run_name,
        "n_failures": len(failing_ids),
        "signature_reference": sig_struct,
        "recommendation": recommendation,
        "results": results,
    }
    write_text_artifact(
        run_name,
        "clusters_sweep.json",
        json.dumps(summary, indent=2),
        overwrite=overwrite,
    )
    write_text_artifact(
        run_name, "clusters_sweep.md", _render_md(summary), overwrite=overwrite
    )
    return summary


def _reasonable(r: dict, n_failures: int) -> bool:
    """Filter out degenerate clusterings before ranking by silhouette."""
    if r.get("silhouette") is None:
        return False
    if r["n_clusters"] < 3:
        return False
    if r["singleton_pct"] > 0.5:
        return False
    if r["largest_share"] > 0.6:
        return False
    return True


def _recommend(results: list[dict], *, n_failures: int) -> dict | None:
    candidates = [r for r in results if "error" not in r and _reasonable(r, n_failures)]
    if not candidates:
        # relax: any config with a silhouette
        candidates = [r for r in results if r.get("silhouette") is not None]
    if not candidates:
        return None
    best = max(candidates, key=lambda r: r["silhouette"])
    return {
        "embedder": best["embedder"],
        "scope": best["scope"],
        "algo": best["algo"],
        "distance_threshold": best["distance_threshold"],
        "silhouette": best["silhouette"],
        "n_clusters": best["n_clusters"],
        "singleton_pct": best["singleton_pct"],
    }


def _render_md(s: dict) -> str:
    rec = s["recommendation"]
    lines = [
        f"# Clustering settings sweep — {s['run']}",
        "",
        f"Failures: {s['n_failures']}  |  signature engine: "
        f"{s['signature_reference']['n_clusters']} clusters, "
        f"{s['signature_reference']['singletons']} singletons",
        "",
        "## Recommendation",
        "",
    ]
    if rec:
        lines += [
            f"**embedder=`{rec['embedder']}` scope=`{rec['scope']}` "
            f"algo=`{rec['algo']}` threshold=`{rec['distance_threshold']}`** "
            f"— silhouette={rec['silhouette']:.3f}, {rec['n_clusters']} clusters, "
            f"{rec['singleton_pct'] * 100:.0f}% singletons",
        ]
    else:
        lines.append("_No non-degenerate configuration found._")
    lines += [
        "",
        "_Silhouette (cosine) is the primary signal; higher = more cohesive/"
        "separated. Configs collapsing to one blob or mostly singletons are "
        "excluded from the recommendation._",
        "",
        "## All configurations (sorted by silhouette)",
        "",
        "| embedder | scope | algo | thr | clusters | singl% | largest% | silhouette | ARI |",
        "|----------|-------|------|-----|----------|--------|----------|------------|-----|",
    ]
    rows = [r for r in s["results"] if "error" not in r]
    rows.sort(key=lambda r: (r["silhouette"] is None, -(r["silhouette"] or -1)))
    for r in rows:
        sil = f"{r['silhouette']:.3f}" if r["silhouette"] is not None else "n/a"
        thr = r["distance_threshold"] if r["distance_threshold"] is not None else "-"
        ari = r.get("agreement", {}).get("ari", "n/a")
        lines.append(
            f"| {r['embedder']} | {r['scope']} | {r['algo']} | {thr} | "
            f"{r['n_clusters']} | {r['singleton_pct'] * 100:.0f} | "
            f"{r['largest_share'] * 100:.0f} | {sil} | {ari} |"
        )
    errs = [r for r in s["results"] if "error" in r]
    if errs:
        lines += ["", "## Unavailable embedders", ""]
        for r in errs:
            lines.append(f"- `{r['embedder']}`: {r['error']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep clustering settings")
    parser.add_argument("--run", required=True)
    parser.add_argument(
        "--embedders", default=",".join(DEFAULT_EMBEDDERS), help="comma-separated"
    )
    parser.add_argument(
        "--thresholds",
        default=",".join(str(t) for t in DEFAULT_THRESHOLDS),
        help="comma-separated agglomerative cosine distance thresholds",
    )
    parser.add_argument("--scopes", default=",".join(DEFAULT_SCOPES))
    parser.add_argument("--no-hdbscan", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    summary = run_sweep(
        args.run,
        embedders=[e.strip() for e in args.embedders.split(",") if e.strip()],
        thresholds=[float(t) for t in args.thresholds.split(",") if t.strip()],
        scopes=[s.strip() for s in args.scopes.split(",") if s.strip()],
        include_hdbscan=not args.no_hdbscan,
        overwrite=args.overwrite,
    )
    rec = summary["recommendation"]
    if rec:
        print(
            f"Best: embedder={rec['embedder']} scope={rec['scope']} "
            f"algo={rec['algo']} threshold={rec['distance_threshold']} "
            f"silhouette={rec['silhouette']:.3f} clusters={rec['n_clusters']}"
        )
    print(f"Wrote clusters_sweep.{{json,md}} for {args.run}")


if __name__ == "__main__":
    main()
