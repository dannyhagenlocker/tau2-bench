"""Build oracle or per-cluster subset specifications."""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


from lib.bootstrap import bootstrap

bootstrap()

import pandas as pd
from contracts.models import ClustersArtifact, SubsetSpecArtifact
from lib.io import read_json_artifact, write_json_artifact
from lib.paths import artifact_path, proposal_dir


def _load_task_summary(run_name: str) -> pd.DataFrame:
    path = artifact_path(run_name, "task_summary.csv")
    return pd.read_csv(path)


def _stable_pass_tasks(df: pd.DataFrame, max_n: int = 10) -> list[str]:
    grouped = df.groupby("task_id")["reward"].apply(list)
    stable = []
    for task_id, rewards in grouped.items():
        if all(r >= 0.999 for r in rewards):
            stable.append(str(task_id))
    return sorted(stable)[:max_n]


def _representative_failures(
    clusters: ClustersArtifact,
    df: pd.DataFrame,
    max_n: int = 10,
) -> list[str]:
    """Pick failing tasks spanning distinct L0 parents."""
    seen_parents: set[str] = set()
    picks: list[str] = []
    for cluster in clusters.clusters:
        if cluster.failure_type == "pass":
            continue
        parent = cluster.parent_l0_id or cluster.id
        if parent in seen_parents:
            continue
        for tid in cluster.task_ids:
            task_rewards = df[df["task_id"].astype(str) == str(tid)]["reward"]
            if len(task_rewards) and task_rewards.max() < 0.999:
                picks.append(str(tid))
                seen_parents.add(parent)
                break
        if len(picks) >= max_n:
            break
    return picks


def run_build_oracle(
    run_name: str,
    baseline_run: str | None = None,
    *,
    overwrite: bool = False,
) -> SubsetSpecArtifact:
    baseline = baseline_run or run_name
    df = _load_task_summary(run_name)
    clusters = read_json_artifact(
        artifact_path(run_name, "clusters.json"), ClustersArtifact
    )

    stable = _stable_pass_tasks(df)
    fails = _representative_failures(clusters, df)
    task_ids = list(dict.fromkeys(stable + fails))

    spec = SubsetSpecArtifact(
        mode="oracle",
        run_name=run_name,
        baseline_run=baseline,
        task_ids=task_ids,
        oracle_stable_pass_ids=stable,
        oracle_representative_fail_ids=fails,
        created_at=_utc_now(),
    )
    write_json_artifact(run_name, "oracle.json", spec, overwrite=overwrite)
    return spec


def run_build_cluster_subset(
    run_name: str,
    cluster_id: str,
    baseline_run: str | None = None,
    *,
    overwrite: bool = False,
) -> SubsetSpecArtifact:
    baseline = baseline_run or run_name
    df = _load_task_summary(run_name)
    clusters = read_json_artifact(
        artifact_path(run_name, "clusters.json"), ClustersArtifact
    )

    cluster = next((c for c in clusters.clusters if c.id == cluster_id), None)
    if cluster is None:
        raise ValueError(f"Cluster not found: {cluster_id}")

    task_fail_rate: dict[str, float] = {}
    grouped = df.groupby("task_id")["reward"].apply(list)
    for tid in cluster.task_ids:
        rewards = grouped.get(tid, grouped.get(str(tid), []))
        if len(rewards):
            task_fail_rate[str(tid)] = 1.0 - sum(
                1 for r in rewards if r >= 0.999
            ) / len(rewards)

    target = sorted(task_fail_rate, key=task_fail_rate.get, reverse=True)[:8]

    stable = _stable_pass_tasks(df, max_n=20)
    oracle_path = artifact_path(baseline, "oracle.json")
    oracle_stable: list[str] = []
    if oracle_path.exists():
        oracle = read_json_artifact(oracle_path, SubsetSpecArtifact)
        oracle_stable = oracle.oracle_stable_pass_ids

    cluster_task_set = set(str(t) for t in cluster.task_ids)
    controls = [t for t in stable if t not in cluster_task_set and t not in target][:4]
    mandatory = [t for t in oracle_stable if t not in target]

    task_ids = list(dict.fromkeys(target + controls + mandatory))

    proposal_id = f"{cluster_id}-{uuid.uuid4().hex[:8]}"
    spec = SubsetSpecArtifact(
        mode="cluster",
        run_name=run_name,
        baseline_run=baseline,
        cluster_id=cluster_id,
        proposal_id=proposal_id,
        task_ids=task_ids,
        target_task_ids=target,
        control_task_ids=controls,
        oracle_stable_pass_ids=mandatory,
        created_at=_utc_now(),
    )

    prop_dir = proposal_dir(run_name, proposal_id)
    prop_dir.mkdir(parents=True, exist_ok=True)
    out_path = prop_dir / "subset_spec.json"
    if out_path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite {out_path}")
    out_path.write_text(spec.model_dump_json(indent=2))
    return spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Build subset specs")
    parser.add_argument("--run", required=True)
    parser.add_argument("--mode", choices=["oracle", "cluster"], required=True)
    parser.add_argument("--cluster", help="Cluster id for mode=cluster")
    parser.add_argument("--baseline")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.mode == "oracle":
        run_build_oracle(args.run, baseline_run=args.baseline, overwrite=args.overwrite)
        print(f"Wrote oracle.json for run {args.run}")
    else:
        if not args.cluster:
            parser.error("--cluster required for mode=cluster")
        spec = run_build_cluster_subset(
            args.run,
            args.cluster,
            baseline_run=args.baseline,
            overwrite=args.overwrite,
        )
        print(f"Wrote proposals/{spec.proposal_id}/subset_spec.json")


if __name__ == "__main__":
    main()
