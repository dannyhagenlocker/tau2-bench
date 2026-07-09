"""Evaluate a proposal subset against baseline (subprocess tau2 run)."""

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime

from lib.bootstrap import bootstrap

bootstrap()


from contracts.models import SubsetResultsArtifact, SubsetSpecArtifact, TaskComparison
from lib.io import read_json_artifact
from lib.paths import REPO_ROOT, proposal_dir

from tau2.data_model.simulation import Results
from tau2.utils.io_utils import load_results_dict


def _task_rewards_from_run(run_name: str) -> dict[str, float]:
    results_path = REPO_ROOT / "data" / "simulations" / run_name
    if not results_path.exists():
        results_path = results_path.parent / f"{run_name}.json"
    data = load_results_dict(str(results_path))
    rewards: dict[str, float] = {}
    for sim in data.get("simulations", []):
        tid = str(sim.get("task_id"))
        ri = sim.get("reward_info") or {}
        reward = ri.get("reward", 0.0)
        if tid in rewards:
            rewards[tid] = max(rewards[tid], reward)
        else:
            rewards[tid] = reward
    return rewards


def _baseline_rewards(baseline_run: str, task_ids: list[str]) -> dict[str, float]:
    path = REPO_ROOT / "data" / "simulations" / baseline_run
    results = Results.load(path / "results.json" if path.is_dir() else path)
    out: dict[str, float] = {}
    for sim in results.simulations:
        if str(sim.task_id) in task_ids or sim.task_id in task_ids:
            r = sim.reward_info.reward if sim.reward_info else 0.0
            tid = str(sim.task_id)
            out[tid] = max(out.get(tid, 0.0), r)
    return out


def _role_for_task(task_id: str, spec: SubsetSpecArtifact) -> str:
    if task_id in spec.target_task_ids:
        return "target"
    if task_id in spec.oracle_stable_pass_ids:
        return "oracle_stable"
    if task_id in spec.oracle_representative_fail_ids:
        return "oracle_fail"
    return "control"


def run_eval_subset(
    run_name: str,
    proposal_id: str,
    *,
    baseline_run: str | None = None,
    candidate_run: str | None = None,
    skip_tau2: bool = False,
    overwrite: bool = False,
) -> SubsetResultsArtifact:
    spec_path = proposal_dir(run_name, proposal_id) / "subset_spec.json"
    spec = read_json_artifact(spec_path, SubsetSpecArtifact)
    baseline = baseline_run or spec.baseline_run or run_name

    if candidate_run is None and not skip_tau2:
        candidate_run = f"proposal-{proposal_id}-eval"
        cmd = [
            "uv",
            "run",
            "tau2",
            "run",
            "--domain",
            "retail",
            "--task-ids",
            *spec.task_ids,
            "--num-trials",
            "1",
            "--save-to",
            candidate_run,
            "--max-concurrency",
            "10",
        ]
        subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    elif candidate_run is None:
        candidate_run = baseline

    baseline_rewards = _baseline_rewards(baseline, spec.task_ids)
    candidate_rewards = _task_rewards_from_run(candidate_run)

    comparisons: list[TaskComparison] = []
    improvements: list[str] = []
    regressions: list[str] = []
    target_improvements = 0
    control_regressions = 0

    for tid in spec.task_ids:
        b = baseline_rewards.get(tid, 0.0)
        c = candidate_rewards.get(tid, 0.0)
        role = _role_for_task(tid, spec)
        comparisons.append(
            TaskComparison(
                task_id=tid,
                role=role,
                baseline_reward=b,
                candidate_reward=c,
                delta=c - b,
            )
        )
        if b < 0.999 and c >= 0.999:
            improvements.append(tid)
            if role == "target":
                target_improvements += 1
        if b >= 0.999 and c < 0.999:
            regressions.append(tid)
            if role in ("control", "oracle_stable"):
                control_regressions += 1

    if control_regressions > 0:
        verdict = "fail"
        recommendation = (
            f"Reject: {control_regressions} control/oracle stable regression(s)."
        )
    elif target_improvements > 0:
        verdict = "pass"
        recommendation = (
            f"Accept candidate: {target_improvements} target improvement(s), "
            f"{len(improvements)} total flips fail→pass."
        )
    elif improvements:
        verdict = "review"
        recommendation = "Review: improvements outside target set only."
    else:
        verdict = "fail"
        recommendation = "Reject: no improvements on subset."

    result = SubsetResultsArtifact(
        proposal_id=proposal_id,
        baseline_run=baseline,
        candidate_run=candidate_run or "",
        subset_spec_path=str(spec_path.relative_to(REPO_ROOT)),
        tasks=comparisons,
        improvements=improvements,
        regressions=regressions,
        target_improvements=target_improvements,
        control_regressions=control_regressions,
        verdict=verdict,
        recommendation=recommendation,
        created_at=datetime.utcnow().isoformat(),
    )

    out_path = proposal_dir(run_name, proposal_id) / "subset_results.json"
    if out_path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite {out_path}")
    out_path.write_text(result.model_dump_json(indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Eval proposal subset vs baseline")
    parser.add_argument("--run", required=True)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--baseline")
    parser.add_argument("--candidate-run", help="Use existing run instead of tau2")
    parser.add_argument(
        "--skip-tau2", action="store_true", help="Compare baseline to itself (test)"
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = run_eval_subset(
        args.run,
        args.proposal,
        baseline_run=args.baseline,
        candidate_run=args.candidate_run,
        skip_tau2=args.skip_tau2,
        overwrite=args.overwrite,
    )
    print(f"Verdict: {result.verdict} — {result.recommendation}")


if __name__ == "__main__":
    main()
