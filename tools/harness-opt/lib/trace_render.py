"""Render sampled cluster traces into compact, cost-bounded transcripts.

The proposer needs to see what the agent actually *did*, not just per-sim
metadata. We render the trajectory with targeted truncation:

- Tool-call **arguments** are kept in full (small, and critical for diagnosing
  wrong-write DB failures — order ids, item ids, payment methods, etc.).
- Tool **results** are truncated hard (big JSON dumps like get_order_details are
  the bulk of the tokens and the least useful for diagnosing agent behaviour).
- Failed NL assertions (assertion + judge justification) are surfaced — they are
  the gold signal for NL_ASSERTION failures.
- The whole transcript is middle-elided to a per-trace character cap, keeping the
  task setup (head) and the resolution (tail) where failures usually surface.
"""

from __future__ import annotations

import json

from tau2.data_model.message import AssistantMessage, ToolMessage, UserMessage
from tau2.data_model.simulation import SimulationRun

DEFAULT_MAX_TOOL_RESULT_CHARS = 300
DEFAULT_MAX_TRACE_CHARS = 5000


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + f" …(+{len(text) - limit} chars)"


def _truncate_middle(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = limit * 2 // 3
    tail = limit - head
    return (
        text[:head].rstrip()
        + f"\n… ({len(text) - limit} chars elided) …\n"
        + text[-tail:].lstrip()
    )


def _failed_nl_assertions(sim: SimulationRun) -> list[str]:
    ri = sim.reward_info
    if ri is None or not ri.nl_assertions:
        return []
    out = []
    for c in ri.nl_assertions:
        if not c.met:
            just = (c.justification or "").strip()
            out.append(f'- FAILED: "{c.nl_assertion}"' + (f" — {just}" if just else ""))
    return out


def render_trace(
    sim: SimulationRun,
    *,
    max_tool_result_chars: int = DEFAULT_MAX_TOOL_RESULT_CHARS,
    max_chars: int = DEFAULT_MAX_TRACE_CHARS,
) -> str:
    """Render one simulation into a compact, truncated transcript string."""
    lines: list[str] = []
    for msg in sim.get_messages():
        if isinstance(msg, AssistantMessage):
            if msg.content and msg.content.strip():
                lines.append(f"[agent] {msg.content.strip()}")
            for tc in msg.tool_calls or []:
                args = json.dumps(tc.arguments, ensure_ascii=False, sort_keys=True)
                lines.append(f"[agent→tool] {tc.name}({args})")
        elif isinstance(msg, UserMessage):
            if msg.content and msg.content.strip():
                lines.append(f"[user] {msg.content.strip()}")
            for tc in msg.tool_calls or []:
                args = json.dumps(tc.arguments, ensure_ascii=False, sort_keys=True)
                lines.append(f"[user→tool] {tc.name}({args})")
        elif isinstance(msg, ToolMessage):
            tag = "tool ERROR" if msg.error else "tool"
            lines.append(
                f"[{tag}] {_truncate(msg.content or '', max_tool_result_chars)}"
            )

    transcript = _truncate_middle("\n".join(lines), max_chars)

    nl = _failed_nl_assertions(sim)
    header = f"### Trace: task={sim.task_id} trial={sim.trial} reward={sim.reward_info.reward if sim.reward_info else '?'}"
    parts = [header]
    if nl:
        parts.append("Failed NL assertions:\n" + "\n".join(nl))
    parts.append("Transcript:\n" + transcript)
    return "\n".join(parts)


def render_traces(
    sims: list[SimulationRun],
    *,
    max_tool_result_chars: int = DEFAULT_MAX_TOOL_RESULT_CHARS,
    max_chars: int = DEFAULT_MAX_TRACE_CHARS,
) -> list[str]:
    return [
        render_trace(
            s, max_tool_result_chars=max_tool_result_chars, max_chars=max_chars
        )
        for s in sims
    ]
