"""Turn one failure cluster into an auto-coded, subset-gated harness proposal.

Flow: acquire lineage lock -> build subset -> ensure lineage worktree at tip ->
fork proposal branch from tip -> run coding-agent backend in the worktree ->
commit + diff vs tip -> (optional) subset eval vs the generation baseline ->
write the artifact package -> rewrite discoverability indexes.

Proposals stack cumulatively on ``lineage/<id>`` (fork from tip); accepting one
is a separate step (manage_proposal.py) that squashes it onto the lineage.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lib.bootstrap import bootstrap

bootstrap()

from contracts.models import (  # noqa: E402
    ClusterLabelsArtifact,
    ClustersArtifact,
    FeaturesArtifact,
    ProposalMetadataArtifact,
    SubsetResultsArtifact,
)
from lib import lineage as lin  # noqa: E402
from lib.coder import get_coder  # noqa: E402
from lib.io import load_simulation_path, read_json_artifact  # noqa: E402
from lib.paths import (  # noqa: E402
    REPO_ROOT,
    artifact_path,
    lineage_lock,
    proposal_dir,
)
from lib.proposal_prompt import build_coder_prompt, build_failure_summary  # noqa: E402
from lib.proposals_index import rewrite_all  # noqa: E402
from lib.sampling import select_diverse  # noqa: E402
from lib.trace_render import render_traces  # noqa: E402
from scripts.build_subset import run_build_cluster_subset  # noqa: E402

from tau2.data_model.simulation import Results  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _lineage_lock(lineage_id: str):
    lock = lineage_lock(lineage_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise SystemExit(
            f"Lineage '{lineage_id}' is locked ({lock}). Another `propose` may be "
            "running on this lineage; remove the lock file if it is stale."
        ) from exc
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


MIN_PER_TRACE_CHARS = 3000
MAX_PER_TRACE_CHARS = 12000


def _pick_reps(cluster, features_by_id, n: int):
    """Diversity-ordered representatives across the whole cluster (not first N)."""
    feats = [features_by_id[s] for s in cluster.simulation_ids if s in features_by_id]
    return select_diverse(feats, n)


def _render_rep_traces(
    run_name: str, sim_ids: list[str], trace_char_budget: int
) -> list[str]:
    """Render transcripts for the reps, splitting a total char budget across them.

    Adaptive per-trace cap: small clusters get rich full traces; large clusters
    get more traces each slightly trimmed. Total stays bounded (cost control).
    """
    if not sim_ids:
        return []
    try:
        results = Results.load(load_simulation_path(run_name))
    except Exception:
        return []
    by_id = {s.id: s for s in results.simulations}
    sims = [by_id[sid] for sid in sim_ids if sid in by_id]
    if not sims:
        return []
    per_trace = max(
        MIN_PER_TRACE_CHARS,
        min(MAX_PER_TRACE_CHARS, trace_char_budget // len(sims)),
    )
    return render_traces(sims, max_chars=per_trace, max_tool_result_chars=500)


def _run_candidate_subset(
    worktree: Path,
    task_ids: list[str],
    candidate_run: str,
    *,
    num_trials: int,
    max_concurrency: int,
) -> None:
    """Run the subset in the worktree (edited harness) then copy results to main data/."""
    import subprocess

    cmd = [
        "uv",
        "run",
        "tau2",
        "run",
        "--domain",
        "retail",
        "--task-ids",
        *task_ids,
        "--num-trials",
        str(num_trials),
        "--save-to",
        candidate_run,
        "--max-concurrency",
        str(max_concurrency),
    ]
    subprocess.run(cmd, cwd=str(worktree), check=True)

    src = worktree / "data" / "simulations" / candidate_run
    if not src.exists():
        src = src.with_suffix(".json")
    dst = REPO_ROOT / "data" / "simulations" / candidate_run
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    elif src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    else:
        raise FileNotFoundError(f"Candidate run results not found in worktree: {src}")


def _render_proposal_md(
    meta: ProposalMetadataArtifact,
    summary: str,
    coder_summary: str,
    subset: Optional[SubsetResultsArtifact],
) -> str:
    lines = [
        f"# Proposal {meta.proposal_id}",
        "",
        f"- Cluster: `{meta.cluster_id}`",
        f"- Lineage: `{meta.lineage_id}` (branch `{meta.branch_name}`)",
        f"- Status: **{meta.status}**"
        + (f" — verdict **{meta.eval_verdict}**" if meta.eval_verdict else ""),
        f"- Coder backend: {meta.coder_backend}",
        f"- Parent commit: `{(meta.parent_commit or '')[:12]}`",
        f"- Diff: {meta.diff_stat or 'no changes'}",
        "",
        "## Failure mode",
        "",
        summary,
        "",
        "## Proposed change",
        "",
        coder_summary or "_(no coder summary)_",
        "",
        "## Evaluation",
        "",
    ]
    if subset is None:
        lines.append("_Subset eval not run (draft). Re-run with --eval to gate._")
    else:
        lines.append(f"**{subset.verdict}** — {subset.recommendation}")
        lines.append("")
        lines.append("| Task | Role | Baseline | Candidate | Δ |")
        lines.append("|------|------|----------|-----------|---|")
        for t in subset.tasks:
            lines.append(
                f"| {t.task_id} | {t.role} | {t.baseline_reward:.2f} | "
                f"{t.candidate_reward:.2f} | {t.delta:+.2f} |"
            )
    lines.append("")
    return "\n".join(lines)


def run_propose(
    run_name: str,
    cluster_id: str,
    *,
    lineage_id: Optional[str] = None,
    baseline_run: Optional[str] = None,
    coder: str = "auto",
    coder_model: Optional[str] = None,
    num_traces: int = 12,
    trace_char_budget: int = 80000,
    do_eval: bool = False,
    num_trials: int = 1,
    max_concurrency: int = 10,
    overwrite: bool = False,
) -> ProposalMetadataArtifact:
    lineage_id = lineage_id or run_name
    baseline_run = baseline_run or run_name

    clusters = read_json_artifact(
        artifact_path(run_name, "clusters.json"), ClustersArtifact
    )
    cluster = next((c for c in clusters.clusters if c.id == cluster_id), None)
    if cluster is None:
        raise SystemExit(f"Cluster not found in {run_name}: {cluster_id}")

    features = read_json_artifact(
        artifact_path(run_name, "features.json"), FeaturesArtifact
    )
    features_by_id = {s.simulation_id: s for s in features.simulations}
    labels_path = artifact_path(run_name, "cluster_labels.json")
    label = None
    if labels_path.exists():
        labels = read_json_artifact(labels_path, ClusterLabelsArtifact)
        label = next((x for x in labels.labels if x.cluster_id == cluster_id), None)

    with _lineage_lock(lineage_id):
        # 1. Subset spec (also mints the proposal_id).
        spec = run_build_cluster_subset(
            run_name, cluster_id, baseline_run=baseline_run, overwrite=overwrite
        )
        proposal_id = spec.proposal_id or f"{cluster_id}"
        pdir = proposal_dir(run_name, proposal_id)
        pdir.mkdir(parents=True, exist_ok=True)

        # 2. Lineage worktree + ephemeral proposal branch from the tip.
        worktree, state = lin.ensure_lineage(lineage_id)
        parent_commit = lin.start_proposal(worktree, proposal_id)

        # 3. Coder edits the harness inside the worktree.
        reps = _pick_reps(cluster, features_by_id, num_traces)
        summary = build_failure_summary(cluster, label, reps)
        rep_traces = _render_rep_traces(
            run_name, [r.simulation_id for r in reps], trace_char_budget
        )
        prompt = build_coder_prompt(cluster, label, reps, rep_traces=rep_traces)
        backend = get_coder(coder, model=coder_model)
        coder_result = backend.run(prompt, worktree)
        (pdir / "coder_log.json").write_text(
            json.dumps(coder_result.to_log(prompt), indent=2)
        )

        # 4. Commit on the proposal branch; capture diff vs lineage tip.
        lin.commit_proposal(worktree, f"proposal {proposal_id}: {cluster_id}")
        patch, diff_stat = lin.diff_vs_lineage(worktree, lineage_id, proposal_id)
        (pdir / "diff.patch").write_text(patch)
        changed = bool(patch.strip())

        # 5. Optional subset gate vs the generation baseline run.
        subset_results: Optional[SubsetResultsArtifact] = None
        candidate_run = None
        status = "draft"
        eval_verdict = None
        if do_eval and changed:
            from scripts.eval_subset import run_eval_subset

            candidate_run = f"proposal-{proposal_id}-eval"
            _run_candidate_subset(
                worktree,
                spec.task_ids,
                candidate_run,
                num_trials=num_trials,
                max_concurrency=max_concurrency,
            )
            subset_results = run_eval_subset(
                run_name,
                proposal_id,
                baseline_run=baseline_run,
                candidate_run=candidate_run,
                overwrite=overwrite,
            )
            status = "evaluated"
            eval_verdict = subset_results.verdict

        # 6. Metadata + proposal.md + status.
        meta = ProposalMetadataArtifact(
            proposal_id=proposal_id,
            cluster_id=cluster_id,
            run_name=run_name,
            branch_name=lin.proposal_branch(proposal_id),
            example_task_ids=spec.target_task_ids or spec.task_ids[:8],
            failure_mode_summary=summary,
            status=status,
            lineage_id=lineage_id,
            coder_backend=coder_result.backend,
            parent_commit=parent_commit,
            generation=state.generation,
            diff_stat=diff_stat or ("no changes" if not changed else None),
            eval_verdict=eval_verdict,
            candidate_run=candidate_run,
            evaluated_at=_now() if status == "evaluated" else None,
        )
        (pdir / "metadata.json").write_text(meta.model_dump_json(indent=2))
        (pdir / "proposal.md").write_text(
            _render_proposal_md(meta, summary, coder_result.summary, subset_results)
        )
        (pdir / "proposal_status.json").write_text(
            json.dumps({"status": meta.status}, indent=2)
        )

        rewrite_all(run_name)
        return meta


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a harness proposal from a cluster"
    )
    parser.add_argument("--run", required=True)
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--lineage", help="Lineage id (default: run name)")
    parser.add_argument("--baseline", help="Generation baseline run (default: run)")
    parser.add_argument(
        "--coder", default="auto", help="auto|openai|claude|cursor|manual"
    )
    parser.add_argument("--coder-model", help="Proposer model (default: gpt-4.1)")
    parser.add_argument(
        "--num-traces", type=int, default=12, help="Max diverse traces sampled"
    )
    parser.add_argument(
        "--trace-char-budget",
        type=int,
        default=80000,
        help="Total char budget across sampled traces (cost control)",
    )
    parser.add_argument(
        "--eval", action="store_true", help="Run subset eval (spends OpenAI budget)"
    )
    parser.add_argument("--num-trials", type=int, default=1)
    parser.add_argument("--max-concurrency", type=int, default=10)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    meta = run_propose(
        args.run,
        args.cluster,
        lineage_id=args.lineage,
        baseline_run=args.baseline,
        coder=args.coder,
        coder_model=args.coder_model,
        num_traces=args.num_traces,
        trace_char_budget=args.trace_char_budget,
        do_eval=args.eval,
        num_trials=args.num_trials,
        max_concurrency=args.max_concurrency,
        overwrite=args.overwrite,
    )
    print(
        f"Proposal {meta.proposal_id} [{meta.status}] on lineage {meta.lineage_id} "
        f"(coder={meta.coder_backend}, diff={meta.diff_stat}). "
        f"See reports/{args.run}/proposals/{meta.proposal_id}/"
    )


if __name__ == "__main__":
    main()
