"""Generate manifest, task_summary.csv, and analysis_summary.md."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from lib.bootstrap import bootstrap

bootstrap()

import pandas as pd
from contracts.models import (
    ClusterLabelsArtifact,
    ClustersArtifact,
    FeaturesArtifact,
    ManifestArtifact,
)
from lib.clustering import assign_cluster_to_simulations
from lib.io import (
    artifact_path,
    get_git_sha,
    load_simulation_path,
    read_json_artifact,
    write_json_artifact,
    write_text_artifact,
)
from lib.paths import REPO_ROOT

from tau2.data_model.simulation import Results
from tau2.metrics.agent_metrics import compute_metrics, is_successful


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_report(
    run_name: str,
    *,
    baseline_run: str | None = None,
    overwrite: bool = False,
) -> ManifestArtifact:
    sim_path = load_simulation_path(run_name)
    results = Results.load(sim_path)

    features = read_json_artifact(
        artifact_path(run_name, "features.json"), FeaturesArtifact
    )
    clusters = read_json_artifact(
        artifact_path(run_name, "clusters.json"), ClustersArtifact
    )
    l0_path = artifact_path(run_name, "clusters_l0.json")
    l0_clusters = (
        read_json_artifact(l0_path, ClustersArtifact)
        if l0_path.exists()
        else ClustersArtifact(run_name=run_name, layer="l0", clusters=[])
    )
    labels_path = artifact_path(run_name, "cluster_labels.json")
    labels = None
    if labels_path.exists():
        labels = read_json_artifact(labels_path, ClusterLabelsArtifact)

    cluster_map = assign_cluster_to_simulations(features.simulations, clusters)

    rows = []
    for sim in features.simulations:
        rows.append(
            {
                "task_id": sim.task_id,
                "trial": sim.trial,
                "simulation_id": sim.simulation_id,
                "reward": sim.reward,
                "db_reward": sim.db_reward,
                "nl_reward": sim.nl_reward,
                "communicate_reward": sim.communicate_reward,
                "mechanism_class": sim.mechanism_class,
                "failure_type": sim.failure_type.value,
                "termination_reason": sim.termination_reason,
                "db_diff_signature": sim.db_diff_signature,
                "nl_failure_signature": sim.nl_failure_signature,
                "cluster_id": cluster_map.get(sim.simulation_id, ""),
                "agent_cost": sim.agent_cost,
                "num_steps": sim.num_steps,
            }
        )
    df = pd.DataFrame(rows)
    csv_path = artifact_path(run_name, "task_summary.csv")
    if csv_path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite {csv_path}")
    df.to_csv(csv_path, index=False)

    try:
        metrics = compute_metrics(results)
        pass_rate = metrics.avg_reward
    except (StopIteration, ValueError):
        pass_rate = (
            sum(s.reward for s in features.simulations) / len(features.simulations)
            if features.simulations
            else 0.0
        )
    n_fail = sum(1 for s in features.simulations if not is_successful(s.reward))
    n_total = len(features.simulations)

    cluster_lines = []
    label_by_id = {lb.cluster_id: lb for lb in labels.labels} if labels else {}
    for c in clusters.clusters[:15]:
        label = label_by_id.get(c.id)
        title = label.display_name if label else c.name
        cluster_lines.append(
            f"- **{c.id}** ({title}): n={c.count}, failure_rate={c.failure_rate:.2f}"
        )

    n_clusters = len(clusters.clusters)
    n_singletons = sum(1 for c in clusters.clusters if c.count == 1)
    singleton_pct = (n_singletons / n_clusters * 100) if n_clusters else 0.0

    l0_lines = []
    for c in sorted(l0_clusters.clusters, key=lambda x: -x.count):
        l0_lines.append(f"- `{c.name}`: n={c.count}")

    summary_md = f"""# Analysis Summary — {run_name}

Generated: {_utc_now()}

## Overview

| Metric | Value |
|--------|-------|
| Simulations | {n_total} |
| Pass rate (avg reward) | {pass_rate:.3f} |
| Failures | {n_fail} |
| Agent LLM | {results.info.agent_info.llm} |
| User LLM | {results.info.user_info.llm} |
| Baseline reference | {baseline_run or run_name} |
| Failure clusters | {n_clusters} ({n_singletons} singletons, {singleton_pct:.0f}%) |

## L0 buckets (failure taxonomy)

{chr(10).join(l0_lines) if l0_lines else "_No L0 buckets._"}

## Top failure clusters

{chr(10).join(cluster_lines) if cluster_lines else "_No failure clusters._"}

## Notes

Subset eval has high variance (~±10% on 15-20 tasks). Use full 114-task × 2-trial runs at generation boundaries for confidence claims.
"""

    write_text_artifact(
        run_name, "analysis_summary.md", summary_md, overwrite=overwrite
    )

    manifest = ManifestArtifact(
        run_name=run_name,
        simulation_path=str(sim_path.relative_to(REPO_ROOT)),
        baseline_run=baseline_run or run_name,
        git_sha=get_git_sha(),
        domain=features.domain,
        num_simulations=n_total,
        num_trials=results.info.num_trials,
        agent_llm=results.info.agent_info.llm,
        user_llm=results.info.user_info.llm,
        created_at=_utc_now(),
        artifacts={
            "features.json": "features.json",
            "clusters_l0.json": "clusters_l0.json",
            "clusters.json": "clusters.json",
            "cluster_labels.json": "cluster_labels.json",
            "task_summary.csv": "task_summary.csv",
            "analysis_summary.md": "analysis_summary.md",
        },
    )
    write_json_artifact(run_name, "manifest.json", manifest, overwrite=overwrite)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate report artifacts")
    parser.add_argument("--run", required=True)
    parser.add_argument("--baseline")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run_report(args.run, baseline_run=args.baseline, overwrite=args.overwrite)
    print(f"Wrote manifest.json, task_summary.csv, analysis_summary.md for {args.run}")


if __name__ == "__main__":
    main()
