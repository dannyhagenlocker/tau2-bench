"""v3 data layer: typed, cached read access to Phase 0 artifacts + traces.

Serves the FastAPI API. Trace nodes are built lazily per simulation (the node
builder + timing live in `dashboard_v2.generate`, reused here as the single
source of truth) so the client never downloads all transcripts at once.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from lib.bootstrap import bootstrap

bootstrap()

import pandas as pd  # noqa: E402
from contracts.models import (  # noqa: E402
    ClusterLabelsArtifact,
    ClustersArtifact,
    FeaturesArtifact,
    ManifestArtifact,
)
from dashboard_v2.generate import _flags, _steps_for_sim  # noqa: E402
from lib.io import read_json_artifact  # noqa: E402
from lib.paths import REPO_ROOT, artifact_path, report_dir  # noqa: E402
from lib.paths import _reports_dir as reports_root  # noqa: E402
from lib.signature_gloss import (  # noqa: E402
    gloss_cluster_signature,
    gloss_db_signature,
)

from tau2.data_model.simulation import Results  # noqa: E402


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


# ---- caches keyed on artifact mtime -------------------------------------

_RESULTS: dict[str, tuple[float, dict]] = {}
_SUMMARY: dict[str, tuple[float, dict]] = {}


def list_runs() -> list[dict[str, Any]]:
    root = reports_root()
    if not root.exists():
        return []
    runs = []
    for p in sorted(root.iterdir()):
        man_path = p / "manifest.json"
        if not (p.is_dir() and man_path.exists()):
            continue
        try:
            man = read_json_artifact(man_path, ManifestArtifact)
        except Exception:
            continue
        runs.append(
            {
                "run": p.name,
                "domain": man.domain,
                "num_simulations": man.num_simulations,
                "agent_llm": man.agent_llm,
                "baseline_run": man.baseline_run,
                "created_at": man.created_at,
                "mtime": _mtime(man_path),
            }
        )
    runs.sort(key=lambda r: r["mtime"], reverse=True)
    return runs


def _load_results(run: str) -> dict:
    man = read_json_artifact(artifact_path(run, "manifest.json"), ManifestArtifact)
    sim_path = Path(man.simulation_path)
    if not sim_path.is_absolute():
        sim_path = REPO_ROOT / man.simulation_path
    key = _mtime(sim_path if sim_path.exists() else artifact_path(run, "manifest.json"))
    cached = _RESULTS.get(run)
    if cached and cached[0] == key:
        return cached[1]
    results = Results.load(str(sim_path))
    sims_by_id = {s.id: s for s in results.simulations}
    _RESULTS[run] = (key, sims_by_id)
    return sims_by_id


def run_summary(run: str) -> dict[str, Any]:
    """Everything the client needs up-front: metadata, L0, clusters, a light
    per-sim index, and flaky pass/fail pairs. Trace nodes are NOT included."""
    key = (
        _mtime(artifact_path(run, "clusters.json"))
        + _mtime(artifact_path(run, "features.json"))
        + _mtime(artifact_path(run, "cluster_labels.json"))
    )
    cached = _SUMMARY.get(run)
    if cached and cached[0] == key:
        return cached[1]

    manifest = read_json_artifact(artifact_path(run, "manifest.json"), ManifestArtifact)
    features = read_json_artifact(artifact_path(run, "features.json"), FeaturesArtifact)
    clusters = read_json_artifact(artifact_path(run, "clusters.json"), ClustersArtifact)
    l0 = read_json_artifact(artifact_path(run, "clusters_l0.json"), ClustersArtifact)
    labels_path = artifact_path(run, "cluster_labels.json")
    labels: Optional[ClusterLabelsArtifact] = (
        read_json_artifact(labels_path, ClusterLabelsArtifact)
        if labels_path.exists()
        else None
    )
    label_by_id = {lb.cluster_id: lb for lb in labels.labels} if labels else {}

    cluster_of: dict[str, str] = {}
    for c in clusters.clusters:
        for sid in c.simulation_ids:
            cluster_of[sid] = c.id

    sims_index: dict[str, Any] = {}
    for f in features.simulations:
        sims_index[f.simulation_id] = {
            "simulation_id": f.simulation_id,
            "task_id": f.task_id,
            "trial": f.trial,
            "reward": f.reward,
            "failure_type": f.failure_type.value,
            "termination_reason": f.termination_reason,
            "db_diff_signature": f.db_diff_signature,
            "db_gloss": gloss_db_signature(f.db_diff_signature),
            "nl_failure_signature": f.nl_failure_signature,
            "tool_chain": f.normalized_tool_chain or [t.name for t in f.tool_sequence],
            "flags": _flags(f),
            "num_steps": f.num_steps,
            "agent_cost": f.agent_cost,
            "cluster_id": cluster_of.get(
                f.simulation_id, "pass" if f.reward >= 0.999 else ""
            ),
        }

    clusters_payload = []
    for c in clusters.clusters:
        lb = label_by_id.get(c.id)
        clusters_payload.append(
            {
                "id": c.id,
                "name": c.name,
                "failure_type": c.failure_type,
                "signature": c.signature or "",
                "gloss": gloss_cluster_signature(c.signature or c.name),
                "count": c.count,
                "failure_rate": c.failure_rate,
                "label": lb.display_name if lb else c.name,
                "blame": lb.blame_tags if lb else [],
                "summary": lb.summary if lb else "",
                "sims": [s for s in c.simulation_ids if s in sims_index],
            }
        )

    # flaky pass/fail pairs
    by_task: dict[str, list[tuple[str, float]]] = {}
    for sid, sp in sims_index.items():
        by_task.setdefault(sp["task_id"], []).append((sid, sp["reward"]))
    flaky = []
    for task_id, entries in by_task.items():
        passed = [s for s, r in entries if r >= 0.999]
        failed = [s for s, r in entries if r < 0.999]
        if passed and failed:
            flaky.append(
                {
                    "task_id": task_id,
                    "pass_sim": passed[0],
                    "fail_sim": failed[0],
                    "n_trials": len(entries),
                }
            )
    flaky.sort(key=lambda x: str(x["task_id"]))

    pass_rate = (
        sum(1 for f in features.simulations if f.reward >= 0.999)
        / len(features.simulations)
        if features.simulations
        else 0.0
    )
    n_clusters = len(clusters_payload)
    n_singletons = sum(1 for c in clusters_payload if c["count"] == 1)

    summary = {
        "run": run,
        "manifest": {
            "domain": manifest.domain,
            "num_simulations": manifest.num_simulations,
            "num_trials": manifest.num_trials,
            "agent_llm": manifest.agent_llm,
            "user_llm": manifest.user_llm,
            "baseline_run": manifest.baseline_run,
            "created_at": manifest.created_at,
            "git_sha": manifest.git_sha,
        },
        "pass_rate": pass_rate,
        "n_failures": sum(1 for f in features.simulations if f.reward < 0.999),
        "n_clusters": n_clusters,
        "n_singletons": n_singletons,
        "l0": [{"name": c.name, "count": c.count} for c in l0.clusters],
        "clusters": clusters_payload,
        "flaky": flaky,
        "sims": sims_index,
    }
    _SUMMARY[run] = (key, summary)
    return summary


def _failure_reason(sim) -> Optional[dict[str, Any]]:
    """Ground-truth ('golden') reason a trace failed, from the evaluator's
    RewardInfo: reward breakdown, DB match, and — most usefully — the failed
    NL-assertion / communicate checks with the judge's justification text."""
    ri = getattr(sim, "reward_info", None)
    if ri is None:
        return None

    def _named(d):
        return {getattr(k, "value", str(k)): v for k, v in (d or {}).items()}

    nl_failures = [
        {"assertion": c.nl_assertion, "justification": c.justification}
        for c in (ri.nl_assertions or [])
        if not c.met
    ]
    comm_failures = [
        {"info": c.info, "justification": c.justification}
        for c in (ri.communicate_checks or [])
        if not c.met
    ]
    return {
        "reward": ri.reward,
        "reward_basis": [
            getattr(rt, "value", str(rt)) for rt in (ri.reward_basis or [])
        ],
        "reward_breakdown": _named(ri.reward_breakdown),
        "db_match": (ri.db_check.db_match if ri.db_check else None),
        "nl_failures": nl_failures,
        "communicate_failures": comm_failures,
        "termination_reason": getattr(sim, "termination_reason", None),
    }


def sim_detail(run: str, sim_id: str) -> Optional[dict[str, Any]]:
    sims = _load_results(run)
    sim = sims.get(sim_id)
    if sim is None:
        return None
    steps, total_dur = _steps_for_sim(sim)
    summary = run_summary(run)
    meta = summary["sims"].get(sim_id, {})
    return {
        **meta,
        "total_dur": total_dur,
        "steps": steps,
        "failure_reason": _failure_reason(sim),
    }


def task_rows(run: str) -> list[dict[str, Any]]:
    df = pd.read_csv(artifact_path(run, "task_summary.csv"))
    cols = [
        c for c in ["task_id", "trial", "reward", "failure_type"] if c in df.columns
    ]
    return df[cols].to_dict(orient="records")


def summary_markdown(run: str) -> str:
    path = artifact_path(run, "analysis_summary.md")
    return path.read_text() if path.exists() else ""


def report_exists(run: str) -> bool:
    return (report_dir(run) / "manifest.json").exists()
