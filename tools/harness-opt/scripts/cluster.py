"""Cluster simulation features (L0 + final)."""

from __future__ import annotations

import argparse

from lib.bootstrap import bootstrap

bootstrap()

from contracts.models import FeaturesArtifact
from lib.clustering import cluster_l0, cluster_l1_l2
from lib.io import read_json_artifact, write_json_artifact
from lib.paths import artifact_path


def run_cluster(run_name: str, *, overwrite: bool = False) -> None:
    features_path = artifact_path(run_name, "features.json")
    features = read_json_artifact(features_path, FeaturesArtifact)

    l0 = cluster_l0(features.simulations, run_name)
    final = cluster_l1_l2(features.simulations, l0, run_name)

    write_json_artifact(run_name, "clusters_l0.json", l0, overwrite=overwrite)
    write_json_artifact(run_name, "clusters.json", final, overwrite=overwrite)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster failure modes")
    parser.add_argument("--run", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run_cluster(args.run, overwrite=args.overwrite)
    print(f"Wrote clusters_l0.json and clusters.json for run {args.run}")


if __name__ == "__main__":
    main()
