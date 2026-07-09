"""Run (or re-run) the subset eval for an existing proposal.

Decoupled from `propose` so the flow can be: propose (draft) → edit the diff →
eval → (re-edit → re-eval) → accept. Evaluates whatever is currently committed
on the proposal's branch, against the generation baseline run.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Optional

from lib.bootstrap import bootstrap

bootstrap()

from contracts.models import (  # noqa: E402
    ProposalMetadataArtifact,
    SubsetResultsArtifact,
    SubsetSpecArtifact,
)
from lib import lineage as lin  # noqa: E402
from lib.io import read_json_artifact  # noqa: E402
from lib.paths import proposal_dir  # noqa: E402
from lib.proposals_index import rewrite_all  # noqa: E402
from scripts.eval_subset import run_eval_subset  # noqa: E402
from scripts.propose import _run_candidate_subset  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_eval_proposal(
    run_name: str,
    proposal_id: str,
    *,
    baseline_run: Optional[str] = None,
    num_trials: int = 1,
    max_concurrency: int = 10,
) -> SubsetResultsArtifact:
    pdir = proposal_dir(run_name, proposal_id)
    meta_path = pdir / "metadata.json"
    if not meta_path.exists():
        raise SystemExit(f"Proposal not found: {run_name}/{proposal_id}")
    meta = read_json_artifact(meta_path, ProposalMetadataArtifact)
    if meta.diff_stat in (None, "no changes"):
        raise SystemExit(f"Proposal {proposal_id} has no diff to evaluate.")

    lineage_id = meta.lineage_id or run_name
    baseline = baseline_run or run_name
    spec = read_json_artifact(pdir / "subset_spec.json", SubsetSpecArtifact)

    def _set_status(status: str) -> None:
        meta.status = status  # type: ignore[assignment]
        meta_path.write_text(meta.model_dump_json(indent=2))
        (pdir / "proposal_status.json").write_text(f'{{"status": "{status}"}}\n')
        rewrite_all(run_name)

    # Persist "evaluating" up front so the state survives a dashboard refresh
    # (a concurrent GET on the proposal will see it while the run is in flight).
    _set_status("evaluating")

    worktree, _ = lin.ensure_lineage(lineage_id)
    lin.checkout_proposal(worktree, proposal_id)

    candidate_run = f"proposal-{proposal_id}-eval"
    try:
        _run_candidate_subset(
            worktree,
            spec.task_ids,
            candidate_run,
            num_trials=num_trials,
            max_concurrency=max_concurrency,
            log_path=pdir / "eval.log",
        )
        result = run_eval_subset(
            run_name,
            proposal_id,
            baseline_run=baseline,
            candidate_run=candidate_run,
            overwrite=True,
        )
    except Exception:
        _set_status("draft")  # eval failed → back to draft (see eval.log)
        raise

    meta.status = "evaluated"
    meta.eval_verdict = result.verdict
    meta.candidate_run = candidate_run
    meta.evaluated_at = _now()
    meta_path.write_text(meta.model_dump_json(indent=2))
    (pdir / "proposal_status.json").write_text('{"status": "evaluated"}\n')
    rewrite_all(run_name)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Eval (or re-eval) a proposal subset")
    parser.add_argument("--run", required=True)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--baseline", help="Generation baseline run (default: run)")
    parser.add_argument("--num-trials", type=int, default=1)
    parser.add_argument("--max-concurrency", type=int, default=10)
    args = parser.parse_args()
    result = run_eval_proposal(
        args.run,
        args.proposal,
        baseline_run=args.baseline,
        num_trials=args.num_trials,
        max_concurrency=args.max_concurrency,
    )
    print(f"Verdict: {result.verdict} — {result.recommendation}")


if __name__ == "__main__":
    main()
