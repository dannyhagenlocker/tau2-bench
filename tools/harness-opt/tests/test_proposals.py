"""Tests for the Phase 2 proposal pipeline (lineage git mechanics, coder, index)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from contracts.models import ProposalMetadataArtifact
from lib import lineage as lin
from lib.coder import ManualCoder, get_coder


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def tmp_repo(tmp_path, monkeypatch):
    """A throwaway git repo + isolated worktree/reports dirs for lineage tests."""
    repo = tmp_path / "repo"
    (repo / "src" / "tau2" / "agent").mkdir(parents=True)
    (repo / "src" / "tau2" / "agent" / "llm_agent.py").write_text(
        "AGENT_INSTRUCTION = 'v0'\n"
    )
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")

    reports = tmp_path / "reports"
    worktrees = tmp_path / "wt"
    monkeypatch.setenv("HARNESS_OPT_REPORTS_DIR", str(reports))
    monkeypatch.setenv("HARNESS_OPT_WORKTREES_DIR", str(worktrees))
    monkeypatch.setattr("lib.paths.REPORTS_DIR", reports)
    return repo


def _edit_and_commit(worktree: Path, content: str, msg: str) -> None:
    (worktree / "src" / "tau2" / "agent" / "llm_agent.py").write_text(content)
    lin.commit_proposal(worktree, msg)


def test_coder_manual_default(monkeypatch):
    assert isinstance(get_coder("manual"), ManualCoder)
    res = ManualCoder().run("do stuff", Path("."))
    assert res.ok and res.backend == "manual"


def test_ensure_lineage_creates_branch_and_worktree(tmp_repo):
    worktree, state = lin.ensure_lineage("genA", repo=tmp_repo)
    assert worktree.exists()
    assert state.branch == "lineage/genA"
    assert state.base_commit == state.tip_commit  # nothing accepted yet
    branches = _git(tmp_repo, "branch", "--list", "lineage/genA")
    assert "lineage/genA" in branches


def test_accept_advances_tip_by_one_squashed_commit(tmp_repo):
    worktree, state = lin.ensure_lineage("genA", repo=tmp_repo)
    base = state.base_commit

    lin.start_proposal(worktree, "p1")
    _edit_and_commit(worktree, "AGENT_INSTRUCTION = 'v1'\n", "wip a")
    _edit_and_commit(
        worktree, "AGENT_INSTRUCTION = 'v1b'\n", "wip b"
    )  # 2 coder commits
    assert lin.has_changes(worktree, "genA", "p1")

    tip = lin.accept_proposal(worktree, "genA", "p1", "accept(c1): fix")
    # Exactly one commit added on top of base.
    count = _git(worktree, "rev-list", "--count", f"{base}..lineage/genA")
    assert count == "1"
    # Proposal branch is gone.
    assert "proposal/p1" not in _git(worktree, "branch", "--list", "proposal/p1")
    assert tip == _git(tmp_repo, "rev-parse", "lineage/genA")


def test_proposals_stack_cumulatively(tmp_repo):
    worktree, state = lin.ensure_lineage("genA", repo=tmp_repo)
    base = state.base_commit

    lin.start_proposal(worktree, "p1")
    _edit_and_commit(worktree, "AGENT_INSTRUCTION = 'v1'\n", "p1")
    lin.accept_proposal(worktree, "genA", "p1", "accept(c1)")

    # Second proposal forks from the NEW tip (cumulative), not base.
    parent = lin.start_proposal(worktree, "p2")
    assert parent == _git(tmp_repo, "rev-parse", "lineage/genA")
    _edit_and_commit(worktree, "AGENT_INSTRUCTION = 'v1'\nEXTRA = 1\n", "p2")
    lin.accept_proposal(worktree, "genA", "p2", "accept(c2)")

    count = _git(worktree, "rev-list", "--count", f"{base}..lineage/genA")
    assert count == "2"  # two stacked accepted proposals
    # The cumulative change includes both edits.
    final = (worktree / "src" / "tau2" / "agent" / "llm_agent.py").read_text()
    assert "v1" in final and "EXTRA = 1" in final


def test_reject_leaves_lineage_untouched(tmp_repo):
    worktree, state = lin.ensure_lineage("genA", repo=tmp_repo)
    tip_before = _git(tmp_repo, "rev-parse", "lineage/genA")

    lin.start_proposal(worktree, "p1")
    _edit_and_commit(worktree, "AGENT_INSTRUCTION = 'bad'\n", "p1")
    lin.reject_proposal(worktree, "genA", "p1")

    assert "proposal/p1" not in _git(worktree, "branch", "--list", "proposal/p1")
    assert _git(tmp_repo, "rev-parse", "lineage/genA") == tip_before


def test_lineage_state_persists_and_indexes(tmp_repo):
    from lib.paths import lineages_dir
    from lib.proposals_index import rewrite_lineages_index

    worktree, state = lin.ensure_lineage("genA", repo=tmp_repo)
    lin.start_proposal(worktree, "p1")
    _edit_and_commit(worktree, "AGENT_INSTRUCTION = 'v1'\n", "p1")
    tip = lin.accept_proposal(worktree, "genA", "p1", "accept(c1)")
    lin.record_accepted(state, "p1", "c_000", tip, "fix auth", bump_generation=True)

    rewrite_lineages_index()
    idx = (lineages_dir() / "index.json").read_text()
    assert "genA" in idx and "c_000" in idx
    assert (lineages_dir() / "README.md").exists()


def test_run_index_from_metadata(tmp_repo, monkeypatch):
    from lib.paths import proposals_dir
    from lib.proposals_index import rewrite_run_index

    run = "run1"
    pdir = proposals_dir(run) / "prop-1"
    pdir.mkdir(parents=True)
    meta = ProposalMetadataArtifact(
        proposal_id="prop-1",
        cluster_id="c_000",
        run_name=run,
        branch_name="proposal/prop-1",
        example_task_ids=["1", "2"],
        failure_mode_summary="wrong cancel_reason",
        status="draft",
        lineage_id="genA",
        diff_stat="1 file changed",
    )
    (pdir / "metadata.json").write_text(meta.model_dump_json(indent=2))

    rewrite_run_index(run)
    idx = (proposals_dir(run) / "index.json").read_text()
    assert "prop-1" in idx and "c_000" in idx
    assert (proposals_dir(run) / "README.md").exists()
