"""Build the coder-agent prompt and the human failure-mode summary for a cluster."""

from __future__ import annotations

from typing import Optional

from contracts.models import Cluster, ClusterLabel, SimulationFeatures

HARNESS_CONSTRAINTS = """\
HARD CONSTRAINTS (violating any invalidates the change):
- Change ONLY the agent-side harness: src/tau2/agent/** (prompts, agent logic),
  src/tau2/utils/llm_utils.py, or the agent path of src/tau2/orchestrator/.
  Register any new agent in src/tau2/registry.py.
- DO NOT edit tasks, scorer/evaluator, tool behavior, the simulated user, or the
  domain policy: data/tau2/domains/**, src/tau2/domains/retail/tools.py,
  src/tau2/evaluator/**, src/tau2/user/** are OFF-LIMITS.
- No task-specific hacks or lookup tables. The change must generalize.
- Make the SMALLEST change that plausibly fixes this one failure mode.
- Do not touch tools/harness-opt/** or anything under dashboard*/.
"""


def build_failure_summary(
    cluster: Cluster,
    label: Optional[ClusterLabel],
    reps: list[SimulationFeatures],
) -> str:
    """Short, human-readable description of the cluster's failure mechanism."""
    parts: list[str] = []
    title = label.display_name if label else cluster.name
    parts.append(f"{title} ({cluster.failure_type}, {cluster.count} sims)")
    if cluster.signature:
        parts.append(f"signature: {cluster.signature}")
    if label and label.blame_tags:
        parts.append(f"blame: {', '.join(label.blame_tags)}")
    if label and label.summary:
        parts.append(label.summary)
    return "\n".join(parts)


def _rep_snippet(f: SimulationFeatures) -> str:
    bits = [f"task={f.task_id}", f"failure={f.failure_type.value}"]
    if f.db_diff_signature:
        bits.append(f"db_diff={f.db_diff_signature}")
    if f.nl_failure_signature:
        bits.append(f"nl={f.nl_failure_signature}")
    chain = f.write_tool_sequence or f.normalized_tool_chain
    if chain:
        bits.append(f"tools={'->'.join(chain)}")
    pf = f.policy_flags
    flags = []
    if pf.auth_before_mutate is False:
        flags.append("auth_missing")
    if pf.confirm_before_write is False:
        flags.append("confirm_missing")
    if not pf.single_tool_per_turn:
        flags.append("multi_tool_turn")
    if flags:
        bits.append(f"flags={','.join(flags)}")
    return " | ".join(bits)


def build_coder_prompt(
    cluster: Cluster,
    label: Optional[ClusterLabel],
    reps: list[SimulationFeatures],
    *,
    domain: str = "retail",
) -> str:
    """Construct the headless coding-agent prompt for one failure cluster."""
    summary = build_failure_summary(cluster, label, reps)
    rep_lines = "\n".join(f"  - {_rep_snippet(f)}" for f in reps) or "  (none)"
    task_ids = ", ".join(cluster.task_ids[:12]) or "(unknown)"

    return f"""\
You are improving the τ2-bench {domain} customer-service agent harness. You are
running headless in an isolated git worktree. Make a focused code change that
addresses ONE observed failure mode, then stop.

## Failure mode (from offline trace clustering)
{summary}

## Representative failing traces
{rep_lines}

## Affected tasks (subset that gates this change)
{task_ids}

## What to do
1. Read the relevant harness code (start with src/tau2/agent/llm_agent.py:
   AGENT_INSTRUCTION / SYSTEM_PROMPT).
2. Diagnose how this failure mode arises from the agent's behavior.
3. Make the smallest agent-side change that plausibly fixes it and generalizes.
4. End with a short summary: the hypothesis, the exact change, and the risk.

{HARNESS_CONSTRAINTS}
"""
