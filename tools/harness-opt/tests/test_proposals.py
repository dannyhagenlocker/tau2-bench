"""Tests for the Phase 2 proposal pipeline (lineage git mechanics, coder, index)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from contracts.models import ProposalMetadataArtifact
from lib import allowlist
from lib import lineage as lin
from lib.coder import ManualCoder, OpenAICoder, _apply_edits, get_coder


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


def test_auto_prefers_openai_when_key_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert isinstance(get_coder("auto"), OpenAICoder)


def test_auto_falls_back_to_manual(monkeypatch):
    # No OpenAI key and no CLI backends available → manual.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("lib.coder.ClaudeCoder.available", lambda self: False)
    monkeypatch.setattr("lib.coder.CursorCoder.available", lambda self: False)
    assert isinstance(get_coder("auto"), ManualCoder)


@pytest.mark.parametrize(
    "path,expected",
    [
        ("src/tau2/agent/llm_agent.py", True),
        ("src/tau2/registry.py", True),
        ("src/tau2/utils/llm_utils.py", True),
        ("src/tau2/orchestrator/orchestrator.py", True),
        ("src/tau2/agent/my_new_agent.py", True),  # new agent module
        ("src/tau2/agent/__init__.py", False),  # dunder
        ("src/tau2/agent/sub/deep.py", False),  # nested, not directly under agent/
        ("src/tau2/domains/retail/tools.py", False),  # tool behaviour
        ("src/tau2/evaluator/evaluator.py", False),  # scorer
        ("src/tau2/user/user_simulator.py", False),  # user sim
        ("data/tau2/domains/retail/tasks.json", False),
        ("data/tau2/domains/retail/policy.md", False),
        ("tools/harness-opt/dashboard_v3/data.py", False),
    ],
)
def test_allowlist(path, expected):
    assert allowlist.is_allowed(path) is expected


def test_assert_allowed_raises_on_forbidden():
    with pytest.raises(PermissionError):
        allowlist.assert_allowed(
            ["src/tau2/agent/llm_agent.py", "src/tau2/evaluator/evaluator.py"]
        )


def test_apply_edits_atomic_and_allowlisted(tmp_path):
    (tmp_path / "src" / "tau2" / "agent").mkdir(parents=True)
    target = tmp_path / "src" / "tau2" / "agent" / "llm_agent.py"
    target.write_text("AGENT_INSTRUCTION = 'v0'\n")

    # A unique-match replace + a new agent file, both allowlisted.
    ok, err, touched = _apply_edits(
        tmp_path,
        [
            {
                "path": "src/tau2/agent/llm_agent.py",
                "old_string": "AGENT_INSTRUCTION = 'v0'",
                "new_string": "AGENT_INSTRUCTION = 'v1: confirm before mutations'",
            },
            {
                "path": "src/tau2/agent/careful_agent.py",
                "new_file": True,
                "content": "# custom agent\n",
            },
        ],
    )
    assert ok and err is None
    assert "v1: confirm" in target.read_text()
    assert (tmp_path / "src" / "tau2" / "agent" / "careful_agent.py").exists()
    assert set(touched) == {
        "src/tau2/agent/llm_agent.py",
        "src/tau2/agent/careful_agent.py",
    }


def test_apply_edits_rejects_non_unique_old_string(tmp_path):
    (tmp_path / "src" / "tau2" / "agent").mkdir(parents=True)
    target = tmp_path / "src" / "tau2" / "agent" / "llm_agent.py"
    target.write_text("x = 1\nx = 1\n")  # two matches
    ok, err, _ = _apply_edits(
        tmp_path,
        [
            {
                "path": "src/tau2/agent/llm_agent.py",
                "old_string": "x = 1",
                "new_string": "x = 2",
            }
        ],
    )
    assert not ok and "not unique" in err
    assert target.read_text() == "x = 1\nx = 1\n"  # unchanged (atomic)


def test_openai_coder_applies_monkeypatched_edits(tmp_path, monkeypatch):
    (tmp_path / "src" / "tau2" / "agent").mkdir(parents=True)
    (tmp_path / "src" / "tau2" / "agent" / "llm_agent.py").write_text(
        "AGENT_INSTRUCTION = 'v0'\n"
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _Resp:
        content = json.dumps(
            {
                "summary": "add confirmation reminder",
                "edits": [
                    {
                        "path": "src/tau2/agent/llm_agent.py",
                        "old_string": "AGENT_INSTRUCTION = 'v0'",
                        "new_string": "AGENT_INSTRUCTION = 'v0 + confirm'",
                    }
                ],
            }
        )
        cost = 0.001

    def _fake_generate(model, messages, **kwargs):
        return _Resp()

    import tau2.utils.llm_utils as llm_utils

    monkeypatch.setattr(llm_utils, "generate", _fake_generate)

    res = OpenAICoder(model="gpt-4.1").run("fix it", tmp_path)
    assert res.ok and res.backend == "openai"
    assert res.cost == 0.001 and res.model == "gpt-4.1"
    assert (
        "confirm" in (tmp_path / "src" / "tau2" / "agent" / "llm_agent.py").read_text()
    )


def _feat(sim_id, task_id, chain, *, single_tool=True):
    from contracts.models import FailureType, PolicyFlags, SimulationFeatures

    return SimulationFeatures(
        simulation_id=sim_id,
        task_id=task_id,
        trial=0,
        reward=0.0,
        failure_type=FailureType.DB_ONLY,
        normalized_tool_chain=chain,
        write_tool_sequence=chain,
        policy_flags=PolicyFlags(single_tool_per_turn=single_tool, num_env_errors=0),
        num_steps=len(chain),
        embedding_text="x",
    )


def test_select_diverse_prefers_distinct_tasks_then_chains():
    from lib.sampling import select_diverse

    feats = [
        _feat("a1", "task1", ["cancel_pending_order"]),
        _feat("a2", "task1", ["cancel_pending_order"]),  # dup task+chain
        _feat("b1", "task2", ["modify_pending_order_items"]),
        _feat("c1", "task3", ["cancel_pending_order"]),
    ]
    # n=3 should pick 3 distinct tasks (task1, task2, task3), not two task1 trials.
    picked = select_diverse(feats, 3)
    assert [p.task_id for p in picked] == ["task1", "task2", "task3"]

    # n=2 → first two distinct tasks.
    assert {p.task_id for p in select_diverse(feats, 2)} == {"task1", "task2"}

    # n larger than distinct tasks falls back to filling remaining sims.
    assert len(select_diverse(feats, 10)) == 4


def test_render_trace_keeps_args_truncates_results_and_nl():
    from lib.trace_render import render_trace

    from tau2.data_model.message import (
        AssistantMessage,
        ToolCall,
        ToolMessage,
        UserMessage,
    )
    from tau2.data_model.simulation import (
        DBCheck,
        NLAssertionCheck,
        RewardInfo,
        SimulationRun,
    )
    from tau2.data_model.tasks import RewardType
    from tau2.utils.utils import get_now

    big_result = "X" * 5000  # long tool output that must be truncated
    messages = [
        UserMessage(role="user", content="cancel my order"),
        AssistantMessage(
            role="assistant",
            tool_calls=[
                ToolCall(
                    id="t1",
                    name="cancel_pending_order",
                    arguments={"order_id": "#W123", "reason": "no longer needed"},
                )
            ],
        ),
        ToolMessage(role="tool", id="t1", content=big_result, requestor="assistant"),
    ]
    sim = SimulationRun(
        id="s1",
        task_id="42",
        trial=0,
        start_time=get_now(),
        end_time=get_now(),
        duration=1.0,
        termination_reason="user_stop",
        agent_cost=0.01,
        user_cost=0.0,
        reward_info=RewardInfo(
            reward=0.0,
            reward_basis=[RewardType.DB, RewardType.NL_ASSERTION],
            reward_breakdown={RewardType.DB: 0.0, RewardType.NL_ASSERTION: 0.0},
            db_check=DBCheck(db_match=False, db_reward=0.0),
            nl_assertions=[
                NLAssertionCheck(
                    nl_assertion="Agent should state the refund amount",
                    met=False,
                    justification="never mentioned the amount",
                )
            ],
        ),
        messages=messages,
        mode="half_duplex",
    )

    out = render_trace(sim, max_tool_result_chars=100, max_chars=5000)
    # Tool-call args kept in full (critical for DB diagnosis).
    assert '"order_id": "#W123"' in out
    assert "no longer needed" in out
    # Long tool result truncated.
    assert big_result not in out and "chars)" in out
    # Failed NL assertion surfaced with justification.
    assert "refund amount" in out and "never mentioned" in out
    # Task header present.
    assert "task=42" in out


def test_openai_coder_retries_on_non_unique_old_string(tmp_path, monkeypatch):
    (tmp_path / "src" / "tau2" / "agent").mkdir(parents=True)
    target = tmp_path / "src" / "tau2" / "agent" / "llm_agent.py"
    target.write_text(
        "x = 1\nx = 1\n"
    )  # 'x = 1' appears twice → first attempt ambiguous
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    calls = {"n": 0}

    def fake_generate(model, messages, **kwargs):
        calls["n"] += 1

        class R:
            cost = 0.001

        if calls["n"] == 1:
            R.content = json.dumps(
                {
                    "summary": "s",
                    "edits": [
                        {
                            "path": "src/tau2/agent/llm_agent.py",
                            "old_string": "x = 1",
                            "new_string": "x = 2",
                        }
                    ],
                }
            )
        else:
            R.content = json.dumps(
                {
                    "summary": "s",
                    "edits": [
                        {
                            "path": "src/tau2/agent/llm_agent.py",
                            "old_string": "x = 1\nx = 1",
                            "new_string": "x = 9\nx = 1",
                        }
                    ],
                }
            )
        return R()

    import tau2.utils.llm_utils as llm_utils

    monkeypatch.setattr(llm_utils, "generate", fake_generate)

    res = OpenAICoder(model="gpt-4.1").run("fix", tmp_path)
    assert res.ok
    assert calls["n"] == 2  # recovered on the second attempt
    assert "x = 9" in target.read_text()
    assert res.cost == pytest.approx(0.002)  # cost accumulated across attempts


def test_openai_coder_rejects_forbidden_path(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _Resp:
        content = json.dumps(
            {
                "summary": "sneaky",
                "edits": [
                    {
                        "path": "src/tau2/evaluator/evaluator.py",
                        "old_string": "a",
                        "new_string": "b",
                    }
                ],
            }
        )
        cost = 0.0

    import tau2.utils.llm_utils as llm_utils

    monkeypatch.setattr(llm_utils, "generate", lambda *a, **k: _Resp())

    res = OpenAICoder().run("do it", tmp_path)
    assert not res.ok
    assert "allowlist" in (res.error or "")


def test_ensure_lineage_creates_branch_and_worktree(tmp_repo):
    worktree, state = lin.ensure_lineage("genA", repo=tmp_repo)
    assert worktree.exists()
    assert state.branch == "lineage/genA"
    assert state.base_commit == state.tip_commit  # nothing accepted yet
    branches = _git(tmp_repo, "branch", "--list", "lineage/genA")
    assert "lineage/genA" in branches


def test_ensure_lineage_reuses_worktree_across_checkouts(
    tmp_repo, monkeypatch, tmp_path
):
    # First call creates the worktree at the configured location.
    wt1, _ = lin.ensure_lineage("genA", repo=tmp_repo)
    assert wt1.exists()

    # Simulate invoking from a *different* checkout (different worktrees dir).
    # The branch is already checked out at wt1, so a naive `git worktree add`
    # would fail ("already checked out"); ensure_lineage must reuse wt1 instead.
    monkeypatch.setenv("HARNESS_OPT_WORKTREES_DIR", str(tmp_path / "other_checkout_wt"))
    wt2, _ = lin.ensure_lineage("genA", repo=tmp_repo)
    assert wt2 == wt1


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


def test_proposal_files_and_apply_edit(tmp_repo):
    worktree, _ = lin.ensure_lineage("genA", repo=tmp_repo)
    lin.start_proposal(worktree, "p1")
    _edit_and_commit(worktree, "AGENT_INSTRUCTION = 'v1'\n", "p1")

    # proposal_files exposes original (lineage tip) vs modified (branch).
    files = lin.proposal_files(worktree, "genA", "p1")
    assert len(files) == 1
    f = files[0]
    assert f["path"] == "src/tau2/agent/llm_agent.py"
    assert "v0" in f["original"] and "v1" in f["modified"]

    # human edit → amend, single commit preserved, diff reflects new content.
    base_tip = _git(tmp_repo, "rev-parse", "lineage/genA")
    patch, stat = lin.apply_proposal_files(
        worktree,
        "genA",
        "p1",
        {"src/tau2/agent/llm_agent.py": "AGENT_INSTRUCTION = 'v2 edited'\n"},
    )
    assert "v2 edited" in patch
    # Still exactly one commit ahead of the lineage tip (amended, not stacked).
    assert _git(worktree, "rev-list", "--count", f"{base_tip}..proposal/p1") == "1"


def test_apply_proposal_files_rejects_forbidden_path(tmp_repo):
    worktree, _ = lin.ensure_lineage("genA", repo=tmp_repo)
    lin.start_proposal(worktree, "p1")
    _edit_and_commit(worktree, "AGENT_INSTRUCTION = 'v1'\n", "p1")
    with pytest.raises(PermissionError):
        lin.apply_proposal_files(
            worktree, "genA", "p1", {"src/tau2/evaluator/evaluator.py": "cheat"}
        )


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
