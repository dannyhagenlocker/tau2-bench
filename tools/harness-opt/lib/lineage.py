"""Git lineage + worktree mechanics for the Phase 2 proposal pipeline.

End-product shape (see docs/phases/phase-2/README.md):

- A pinned **base commit** roots every lineage.
- ``lineage/<id>`` is a durable branch per improvement-loop rollout. Accepting a
  proposal advances it by exactly one squashed commit, so proposals stack
  cumulatively and ``git log lineage/<id>`` reads as the improvement narrative.
- ``proposal/<id>`` is an ephemeral eval branch forked from the current lineage
  tip; folded into the lineage on accept, deleted on reject.
- Each lineage owns one git worktree (``.harness-opt-worktrees/<id>``) so the
  user's main checkout is never touched.

All functions shell out to git with an explicit ``repo`` root so tests can point
at a throwaway repository. Nothing here ever touches the caller's current
checkout or force-updates refs.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from contracts.models import LineageArtifact, LineageProposalRef
from lib.io import read_json_artifact
from lib.paths import (
    REPO_ROOT,
    lineage_state_path,
    lineage_worktree_dir,
    lineages_dir,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lineage_branch(lineage_id: str) -> str:
    return f"lineage/{lineage_id}"


def proposal_branch(proposal_id: str) -> str:
    return f"proposal/{proposal_id}"


def _git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (code {proc.returncode}):\n{proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def _branch_exists(repo: Path, branch: str) -> bool:
    return (
        subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=str(repo),
        ).returncode
        == 0
    )


def base_commit(repo: Path = REPO_ROOT) -> str:
    return _git(repo, "rev-parse", "HEAD")


def rev_parse(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref)


# --- lineage state persistence -------------------------------------------------


def load_lineage_state(lineage_id: str) -> Optional[LineageArtifact]:
    path = lineage_state_path(lineage_id)
    if not path.exists():
        return None
    return read_json_artifact(path, LineageArtifact)


def save_lineage_state(state: LineageArtifact) -> Path:
    lineages_dir().mkdir(parents=True, exist_ok=True)
    state.updated_at = _now()
    path = lineage_state_path(state.lineage_id)
    path.write_text(state.model_dump_json(indent=2))
    return path


# --- worktree + branch lifecycle ----------------------------------------------


def ensure_lineage(
    lineage_id: str,
    *,
    base: Optional[str] = None,
    repo: Path = REPO_ROOT,
) -> tuple[Path, LineageArtifact]:
    """Ensure lineage/<id> branch + its worktree exist; return (worktree, state).

    Creates the branch at ``base`` (default: repo HEAD) the first time. Reuses an
    existing branch/worktree/state on subsequent calls; ``base`` is ignored once
    the lineage exists (the base commit is pinned).
    """
    branch = lineage_branch(lineage_id)
    worktree = lineage_worktree_dir(lineage_id)
    state = load_lineage_state(lineage_id)

    if not _branch_exists(repo, branch):
        base_sha = _git(repo, "rev-parse", base or "HEAD")
        _git(repo, "branch", branch, base_sha)
    else:
        base_sha = state.base_commit if state else _git(repo, "rev-parse", branch)

    if not worktree.exists():
        worktree.parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", str(worktree), branch)
    else:
        # Make sure the worktree is on the lineage branch (not a leftover proposal).
        _git(worktree, "checkout", branch)

    tip = _git(worktree, "rev-parse", "HEAD")
    if state is None:
        state = LineageArtifact(
            lineage_id=lineage_id,
            branch=branch,
            base_commit=base_sha,
            tip_commit=tip,
        )
        save_lineage_state(state)
    else:
        state.tip_commit = tip
        save_lineage_state(state)
    return worktree, state


def lineage_tip(lineage_id: str, *, repo: Path = REPO_ROOT) -> str:
    return _git(repo, "rev-parse", lineage_branch(lineage_id))


def start_proposal(worktree: Path, proposal_id: str) -> str:
    """Fork an ephemeral proposal branch from the current lineage tip. Returns tip sha."""
    tip = _git(worktree, "rev-parse", "HEAD")
    _git(worktree, "checkout", "-B", proposal_branch(proposal_id))
    return tip


def commit_proposal(worktree: Path, message: str) -> Optional[str]:
    """Stage + commit any working-tree changes on the proposal branch.

    Returns the new commit sha, or None when the coder made no changes.
    """
    _git(worktree, "add", "-A")
    status = _git(worktree, "status", "--porcelain")
    if not status.strip():
        # Nothing staged; maybe the coder already committed. Report current HEAD
        # only if the branch is ahead of its start point is handled by the caller.
        return None
    _git(worktree, "commit", "-m", message, "--no-verify")
    return _git(worktree, "rev-parse", "HEAD")


def diff_vs_lineage(
    worktree: Path, lineage_id: str, proposal_id: str
) -> tuple[str, str]:
    """Return (unified patch, shortstat) of proposal branch vs the lineage tip."""
    lb = lineage_branch(lineage_id)
    pb = proposal_branch(proposal_id)
    patch = _git(worktree, "diff", f"{lb}...{pb}")
    shortstat = _git(worktree, "diff", "--shortstat", f"{lb}...{pb}")
    return patch, shortstat.strip()


def has_changes(worktree: Path, lineage_id: str, proposal_id: str) -> bool:
    patch, _ = diff_vs_lineage(worktree, lineage_id, proposal_id)
    return bool(patch.strip())


def accept_proposal(
    worktree: Path,
    lineage_id: str,
    proposal_id: str,
    squash_message: str,
) -> str:
    """Squash the proposal branch into one commit on lineage/<id>. Returns new tip.

    Uses ``git merge --squash`` so the lineage gains exactly one clean commit per
    accepted proposal regardless of how many commits the coder made. Deletes the
    ephemeral proposal branch afterward.
    """
    lb = lineage_branch(lineage_id)
    pb = proposal_branch(proposal_id)
    _git(worktree, "checkout", lb)
    _git(worktree, "merge", "--squash", pb)
    _git(worktree, "commit", "-m", squash_message, "--no-verify")
    new_tip = _git(worktree, "rev-parse", "HEAD")
    _git(worktree, "branch", "-D", pb)
    return new_tip


def reject_proposal(worktree: Path, lineage_id: str, proposal_id: str) -> None:
    """Discard the ephemeral proposal branch; lineage is untouched."""
    lb = lineage_branch(lineage_id)
    pb = proposal_branch(proposal_id)
    _git(worktree, "checkout", lb)
    if _branch_exists(worktree, pb):
        _git(worktree, "branch", "-D", pb)


def record_accepted(
    state: LineageArtifact,
    proposal_id: str,
    cluster_id: str,
    commit: str,
    summary: Optional[str],
    *,
    bump_generation: bool = False,
) -> LineageArtifact:
    state.accepted_proposals.append(
        LineageProposalRef(
            proposal_id=proposal_id,
            cluster_id=cluster_id,
            commit=commit,
            summary=summary,
        )
    )
    state.tip_commit = commit
    if bump_generation:
        state.generation += 1
    save_lineage_state(state)
    return state


def remove_lineage_worktree(lineage_id: str, *, repo: Path = REPO_ROOT) -> None:
    worktree = lineage_worktree_dir(lineage_id)
    if worktree.exists():
        _git(repo, "worktree", "remove", "--force", str(worktree), check=False)
