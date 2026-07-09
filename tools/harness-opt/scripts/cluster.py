"""Cluster simulation features (L0 + final)."""

from __future__ import annotations

import argparse

from lib.bootstrap import bootstrap

bootstrap()

from contracts.models import FeaturesArtifact
from lib.clustering import cluster_l0, cluster_l1_l2
from lib.io import read_json_artifact, write_json_artifact
from lib.paths import artifact_path


def run_cluster(
    run_name: str,
    *,
    method: str = "signature",
    # Embedding defaults are the ablation-validated winner on baseline-gpt55-t2,
    # scored against hand-labeled root causes: neural 'st' (all-MiniLM-L6-v2) /
    # global scope / core+last_message document (best ARI 0.70 vs 0.47 tfidf,
    # 0.20 signatures). The distance threshold is AUTO-selected per run (a fixed
    # threshold didn't transfer across failure distributions), and it falls back
    # to tfidf when no neural backend is available. See eval/ablation.*.md.
    embedder: str = "st",
    scope: str = "global",
    algo: str = "agglomerative",
    distance_threshold: float = 0.0,  # <=0 => auto-select per run
    max_cluster_share: float = 0.45,
    doc_fields: str = "last_message",
    overwrite: bool = False,
) -> None:
    features_path = artifact_path(run_name, "features.json")
    features = read_json_artifact(features_path, FeaturesArtifact)

    # L0 taxonomy is deterministic and method-agnostic; always written.
    l0 = cluster_l0(features.simulations, run_name)

    if method == "embedding":
        from lib.embedding_cluster import (
            cluster_embeddings,
            get_embedder,
            st_available,
        )

        # Graceful fallback: neural 'st' needs a torch install or a cached
        # MiniLM. If unavailable, drop to tfidf (auto-threshold still applies).
        if embedder == "st" and not st_available():
            print("Warning: 'st' embedder unavailable; falling back to tfidf.")
            embedder = "tfidf"

        fields = {f.strip() for f in doc_fields.split(",") if f.strip()}
        final = cluster_embeddings(
            features.simulations,
            run_name,
            embedder=get_embedder(embedder),
            scope=scope,
            algo=algo,
            distance_threshold=distance_threshold,  # <=0 => auto
            document_fields=fields,
            max_cluster_share=max_cluster_share,
        )
        # Observability: report the resulting structure (auto-threshold outcome).
        counts = [c.count for c in final.clusters]
        if counts:
            total = sum(counts)
            mode = "auto" if distance_threshold <= 0 else f"fixed@{distance_threshold}"
            print(
                f"embedding[{embedder}, {mode}, cap={max_cluster_share}]: "
                f"{len(counts)} clusters, largest={max(counts)} "
                f"({100 * max(counts) // total}%), "
                f"singletons={sum(1 for c in counts if c == 1)}"
            )
    elif method == "signature":
        final = cluster_l1_l2(features.simulations, l0, run_name)
    else:
        raise ValueError(f"Unknown clustering method '{method}'")

    write_json_artifact(run_name, "clusters_l0.json", l0, overwrite=overwrite)
    write_json_artifact(run_name, "clusters.json", final, overwrite=overwrite)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster failure modes")
    parser.add_argument("--run", required=True)
    parser.add_argument(
        "--method",
        default="signature",
        choices=["signature", "embedding"],
        help="clustering engine (default: signature)",
    )
    parser.add_argument(
        "--embedder", default="st", help="embedding backend: st, tfidf, char, or lsa"
    )
    parser.add_argument(
        "--scope",
        default="global",
        choices=["l0", "global"],
        help="embedding scope: within L0 buckets or all failures",
    )
    parser.add_argument(
        "--algo",
        default="agglomerative",
        choices=["agglomerative", "hdbscan"],
        help="embedding clustering algorithm",
    )
    parser.add_argument(
        "--distance-threshold",
        type=float,
        default=0.0,
        help="cosine distance threshold; <=0 auto-selects per run",
    )
    parser.add_argument(
        "--max-cluster-share",
        type=float,
        default=0.45,
        help="auto-threshold: cap on largest cluster's share of failures",
    )
    parser.add_argument(
        "--doc-fields",
        default="last_message",
        help="comma-sep 'why' segments: nl,escalation,last_message,tool_errors",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run_cluster(
        args.run,
        method=args.method,
        embedder=args.embedder,
        scope=args.scope,
        algo=args.algo,
        distance_threshold=args.distance_threshold,
        max_cluster_share=args.max_cluster_share,
        doc_fields=args.doc_fields,
        overwrite=args.overwrite,
    )
    print(
        f"Wrote clusters_l0.json and clusters.json for run {args.run} "
        f"(method={args.method})"
    )


if __name__ == "__main__":
    main()
