"""Parse simulation trajectories into structured features (trace-only)."""

from __future__ import annotations

import re
from typing import Any, Optional

from contracts.models import (
    FailureType,
    PolicyFlags,
    SimulationFeatures,
    ToolCallRecord,
)
from lib.db_diff import compute_db_diff

from tau2.data_model.message import AssistantMessage, Message, ToolMessage, UserMessage
from tau2.data_model.simulation import RewardInfo, RewardType, SimulationRun
from tau2.data_model.tasks import RewardType as TaskRewardType
from tau2.data_model.tasks import Task
from tau2.metrics.agent_metrics import is_successful
from tau2.metrics.break_down_metrics import get_write_tools

AUTH_TOOLS = frozenset(
    {"find_user_id_by_email", "find_user_id_by_name_zip", "get_user_details"}
)
CONFIRM_PATTERNS = re.compile(
    r"\b(yes|yeah|yep|confirm|confirmed|go ahead|please do|that's correct)\b",
    re.IGNORECASE,
)

_WRITE_TOOLS_CACHE: dict[str, frozenset[str]] = {}


def get_agent_write_tools(domain: str) -> frozenset[str]:
    if domain not in _WRITE_TOOLS_CACHE:
        agent_writes, _ = get_write_tools(domain)
        _WRITE_TOOLS_CACHE[domain] = frozenset(agent_writes)
    return _WRITE_TOOLS_CACHE[domain]


def _component_failed(
    reward_info: RewardInfo,
    component: TaskRewardType,
) -> bool:
    """True when a gating reward component failed (must be in reward_basis)."""
    if component not in (reward_info.reward_basis or []):
        return False

    breakdown = reward_info.reward_breakdown or {}
    val = breakdown.get(component)
    if val is not None:
        return not is_successful(val)

    if component == TaskRewardType.DB and reward_info.db_check is not None:
        return not reward_info.db_check.db_match
    if component == TaskRewardType.NL_ASSERTION and reward_info.nl_assertions:
        return any(not c.met for c in reward_info.nl_assertions)
    if component == TaskRewardType.COMMUNICATE and reward_info.communicate_checks:
        return any(not c.met for c in reward_info.communicate_checks)
    return False


def classify_failure(
    reward_info: Optional[RewardInfo],
    termination_reason: Optional[str],
) -> FailureType:
    if reward_info is None:
        return FailureType.TERMINATION

    if is_successful(reward_info.reward):
        return FailureType.PASS

    if termination_reason not in (None, "user_stop", "agent_stop"):
        return FailureType.TERMINATION

    db_fail = _component_failed(reward_info, TaskRewardType.DB)
    nl_fail = _component_failed(reward_info, TaskRewardType.NL_ASSERTION)
    comm_fail = _component_failed(reward_info, TaskRewardType.COMMUNICATE)

    if db_fail and nl_fail:
        return FailureType.MIXED
    if db_fail:
        return FailureType.DB_ONLY
    if nl_fail:
        return FailureType.NL_ONLY
    if comm_fail:
        return FailureType.COMMUNICATE_ONLY
    return FailureType.TERMINATION


def _reward_components(
    reward_info: Optional[RewardInfo],
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if reward_info is None or reward_info.reward_breakdown is None:
        return None, None, None
    breakdown = reward_info.reward_breakdown
    db = breakdown.get(RewardType.DB) if RewardType.DB in breakdown else None
    nl = (
        breakdown.get(RewardType.NL_ASSERTION)
        if RewardType.NL_ASSERTION in breakdown
        else None
    )
    comm = (
        breakdown.get(RewardType.COMMUNICATE)
        if RewardType.COMMUNICATE in breakdown
        else None
    )
    return db, nl, comm


def extract_tool_sequence(messages: list[Message]) -> list[ToolCallRecord]:
    """Extract agent tool calls in order with error flags from tool responses."""
    records: list[ToolCallRecord] = []
    pending: dict[str, ToolCallRecord] = {}
    turn = 0

    for msg in messages:
        if isinstance(msg, AssistantMessage) and msg.is_tool_call():
            for tc in msg.tool_calls or []:
                rec = ToolCallRecord(name=tc.name, turn=turn, error=False)
                records.append(rec)
                pending[tc.id] = rec
            turn += 1
        elif isinstance(msg, ToolMessage):
            tc_id = msg.id
            if tc_id and tc_id in pending and msg.error:
                pending[tc_id].error = True

    return records


def _user_confirmed_before_index(messages: list[Message], write_index: int) -> bool:
    """Heuristic: user said yes/confirm in assistant text turns before write."""
    assistant_turns = 0
    for msg in messages:
        if isinstance(msg, AssistantMessage):
            if msg.is_tool_call():
                if assistant_turns >= write_index:
                    break
                assistant_turns += 1
        elif isinstance(msg, UserMessage) and msg.content:
            if assistant_turns < write_index and CONFIRM_PATTERNS.search(msg.content):
                return True
    return False


def compute_policy_flags(
    messages: list[Message],
    tool_sequence: list[ToolCallRecord],
    domain: str,
) -> PolicyFlags:
    write_tools = get_agent_write_tools(domain)
    num_env_errors = sum(1 for t in tool_sequence if t.error)

    single_tool_per_turn = True
    turn_counts: dict[int, int] = {}
    for rec in tool_sequence:
        turn_counts[rec.turn] = turn_counts.get(rec.turn, 0) + 1
    if any(c > 1 for c in turn_counts.values()):
        single_tool_per_turn = False

    auth_before_mutate: Optional[bool] = None
    confirm_before_write: Optional[bool] = None

    write_indices = [i for i, t in enumerate(tool_sequence) if t.name in write_tools]
    if write_indices:
        first_write_idx = write_indices[0]
        prior_tools = {tool_sequence[i].name for i in range(first_write_idx)}
        auth_before_mutate = bool(prior_tools & AUTH_TOOLS)
        confirm_before_write = _user_confirmed_before_index(messages, first_write_idx)
    elif tool_sequence:
        auth_before_mutate = True
        confirm_before_write = None

    return PolicyFlags(
        auth_before_mutate=auth_before_mutate,
        confirm_before_write=confirm_before_write,
        single_tool_per_turn=single_tool_per_turn,
        num_env_errors=num_env_errors,
    )


_NL_NOISE = re.compile(r"(#\w+|\$[\d,.]+|\b\d[\d,.]*\b|'[^']*'|\"[^\"]*\")")


def denoise_nl(text: Optional[str]) -> str:
    """Strip task-specific values (amounts, IDs, quotes) so assertions cluster."""
    stripped = _NL_NOISE.sub("", text or "")
    return re.sub(r"\s+", " ", stripped).strip().lower()


def build_nl_signature(
    reward_info: Optional[RewardInfo],
) -> tuple[Optional[str], list[str]]:
    """P3: denoised signature of the failed NL assertions (order-independent)."""
    if reward_info is None or not reward_info.nl_assertions:
        return None, []
    failed = [c.nl_assertion for c in reward_info.nl_assertions if not c.met]
    denoised = sorted({d for a in failed if (d := denoise_nl(a))})
    if not denoised:
        return None, []
    return "|".join(denoised), denoised


def normalize_tool_chain(tool_sequence: list[ToolCallRecord]) -> list[str]:
    """P2: tool names with consecutive duplicates collapsed (args ignored)."""
    chain: list[str] = []
    for rec in tool_sequence:
        if not chain or chain[-1] != rec.name:
            chain.append(rec.name)
    return chain


def extract_write_sequence(
    tool_sequence: list[ToolCallRecord],
    write_tools: frozenset[str],
) -> list[str]:
    """P2: ordered write (mutating) tool calls, consecutive duplicates collapsed."""
    seq: list[str] = []
    for rec in tool_sequence:
        if rec.name in write_tools and (not seq or seq[-1] != rec.name):
            seq.append(rec.name)
    return seq


def build_embedding_text(
    failure_type: FailureType,
    normalized_tool_chain: list[str],
    policy_flags: PolicyFlags,
    termination_reason: Optional[str],
    db_diff_signature: Optional[str] = None,
    nl_failure_signature: Optional[str] = None,
) -> str:
    tools = ",".join(normalized_tool_chain) or "none"
    flags: list[str] = []
    if policy_flags.auth_before_mutate is True:
        flags.append("auth_ok")
    elif policy_flags.auth_before_mutate is False:
        flags.append("auth_missing")
    if policy_flags.confirm_before_write is True:
        flags.append("confirm_ok")
    elif policy_flags.confirm_before_write is False:
        flags.append("confirm_missing")
    if not policy_flags.single_tool_per_turn:
        flags.append("multi_tool_turn")
    if policy_flags.num_env_errors:
        flags.append(f"env_errors={policy_flags.num_env_errors}")

    term = termination_reason or "none"
    parts = [
        f"failure_type={failure_type.value}",
        f"tools={tools}",
        f"flags={','.join(flags) or 'none'}",
        f"termination={term}",
    ]
    if db_diff_signature:
        parts.append(f"db_diff={db_diff_signature}")
    if nl_failure_signature:
        parts.append(f"nl_diff={nl_failure_signature}")
    return " | ".join(parts)


_DB_FAILURE_TYPES = frozenset({FailureType.DB_ONLY, FailureType.MIXED})
_NL_FAILURE_TYPES = frozenset({FailureType.NL_ONLY, FailureType.MIXED})


def extract_simulation_features(
    sim: SimulationRun,
    *,
    domain: str = "retail",
    task: Optional[Task] = None,
    base_db: Any = None,
) -> SimulationFeatures:
    messages = sim.get_messages()
    tool_sequence = extract_tool_sequence(messages)
    failure_type = classify_failure(sim.reward_info, sim.termination_reason)
    policy_flags = compute_policy_flags(messages, tool_sequence, domain)
    db_reward, nl_reward, communicate_reward = _reward_components(sim.reward_info)

    normalized_chain = normalize_tool_chain(tool_sequence)
    write_sequence = extract_write_sequence(
        tool_sequence, get_agent_write_tools(domain)
    )

    # P1: only replay DB diffs for DB-gated failures (expensive, and pointless
    # for passing / NL-only / prematurely-terminated sims).
    db_diff_signature: Optional[str] = None
    db_diff_kinds: Optional[dict[str, int]] = None
    db_diff_entities: list[str] = []
    if failure_type in _DB_FAILURE_TYPES and task is not None and base_db is not None:
        diff = compute_db_diff(task, sim, base_db)
        if diff is not None:
            db_diff_signature = diff.signature
            db_diff_kinds = diff.kinds
            db_diff_entities = diff.entities

    # P3: denoised NL-assertion failure signal.
    nl_failure_signature: Optional[str] = None
    nl_failed_assertions: list[str] = []
    if failure_type in _NL_FAILURE_TYPES:
        nl_failure_signature, nl_failed_assertions = build_nl_signature(sim.reward_info)

    embedding_text = build_embedding_text(
        failure_type,
        normalized_chain,
        policy_flags,
        sim.termination_reason,
        db_diff_signature=db_diff_signature,
        nl_failure_signature=nl_failure_signature,
    )

    return SimulationFeatures(
        simulation_id=sim.id,
        task_id=sim.task_id,
        trial=sim.trial or 0,
        reward=sim.reward_info.reward if sim.reward_info else 0.0,
        failure_type=failure_type,
        termination_reason=sim.termination_reason,
        db_reward=db_reward,
        nl_reward=nl_reward,
        communicate_reward=communicate_reward,
        tool_sequence=tool_sequence,
        normalized_tool_chain=normalized_chain,
        write_tool_sequence=write_sequence,
        db_diff_signature=db_diff_signature,
        db_diff_kinds=db_diff_kinds,
        db_diff_entities=db_diff_entities,
        nl_failure_signature=nl_failure_signature,
        nl_failed_assertions=nl_failed_assertions,
        policy_flags=policy_flags,
        num_steps=len(messages),
        agent_cost=sim.agent_cost,
        embedding_text=embedding_text,
    )
