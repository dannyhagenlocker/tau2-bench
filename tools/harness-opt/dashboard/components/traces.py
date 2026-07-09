"""Trace rendering: timeline, cluster gallery, side-by-side diff.

Reads raw trajectories (via state.simulations) plus the per-sim feature record
(via state.features_by_id) so a trace can be shown alongside its computed
signals (failure type, DB-diff / NL signatures, tool chain, policy flags).
"""

from __future__ import annotations

import json
from typing import Optional

import dashboard.state as state
import streamlit as st
from contracts.models import SimulationFeatures

_ROLE_ICON = {"assistant": "🤖", "user": "🧑", "tool": "🔧", "system": "⚙️"}


def _fmt_args(arguments: dict) -> str:
    try:
        return json.dumps(arguments, indent=2, default=str)
    except (TypeError, ValueError):
        return str(arguments)


def signal_badges(feat: Optional[SimulationFeatures]) -> None:
    """Render the computed signals for a sim as compact markdown."""
    if feat is None:
        st.caption("No feature record for this simulation.")
        return
    cols = st.columns(4)
    cols[0].metric("Reward", f"{feat.reward:.2f}")
    cols[1].metric("Failure", feat.failure_type.value)
    cols[2].metric("Steps", feat.num_steps)
    cols[3].metric("Cost", f"${feat.agent_cost:.3f}" if feat.agent_cost else "—")

    if feat.db_diff_signature:
        st.markdown(f"**DB diff:** `{feat.db_diff_signature}`")
    if feat.nl_failure_signature:
        st.markdown(f"**NL failure:** `{feat.nl_failure_signature}`")
    chain = feat.normalized_tool_chain or [t.name for t in feat.tool_sequence]
    st.markdown(f"**Tool chain:** {' → '.join(chain) if chain else '_none_'}")

    pf = feat.policy_flags
    flags = []
    if pf.auth_before_mutate is False:
        flags.append("auth_missing")
    if pf.confirm_before_write is False:
        flags.append("confirm_missing")
    if not pf.single_tool_per_turn:
        flags.append("multi_tool_turn")
    if pf.num_env_errors:
        flags.append(f"env_errors={pf.num_env_errors}")
    if flags:
        st.markdown("**Flags:** " + ", ".join(f"`{f}`" for f in flags))


def render_message(msg) -> None:
    role = getattr(msg, "role", "system")
    icon = _ROLE_ICON.get(role, "•")
    content = getattr(msg, "content", None)
    tool_calls = getattr(msg, "tool_calls", None)

    if role == "tool":
        requestor = getattr(msg, "requestor", "assistant")
        error = getattr(msg, "error", False)
        label = f"{icon} tool result → {requestor}" + (" ⚠️ error" if error else "")
        with st.expander(label, expanded=bool(error)):
            st.code(content or "", language="json")
        return

    with st.container():
        header = f"{icon} **{role}**"
        st.markdown(header)
        if content:
            st.markdown(content)
        for tc in tool_calls or []:
            st.markdown(f"↳ calls `{tc.name}`")
            if tc.arguments:
                st.code(_fmt_args(tc.arguments), language="json")


def render_trace(run: str, sim_id: str, *, show_signals: bool = True) -> None:
    sims = state.simulations(run)
    sim = sims.get(sim_id)
    if sim is None:
        st.warning(f"Simulation `{sim_id}` not found in `{run}`.")
        return

    st.markdown(f"**`{sim_id}`** · task `{sim.task_id}` · trial {sim.trial}")
    if show_signals:
        feat = state.features_by_id(run).get(sim_id)
        signal_badges(feat)
        st.divider()

    messages = sim.get_messages()
    st.caption(f"{len(messages)} messages · termination: {sim.termination_reason}")
    for msg in messages:
        render_message(msg)


def render_trace_explorer(run: str) -> None:
    st.subheader("Trace explorer")
    feats = state.features(run).simulations
    options = {
        f"{f.simulation_id} · task {f.task_id} · {f.failure_type.value} · r={f.reward:.1f}": f.simulation_id
        for f in sorted(
            feats, key=lambda x: (x.failure_type.value != "pass", x.task_id)
        )
    }
    choice = st.selectbox("Simulation", list(options.keys()))
    if choice:
        render_trace(run, options[choice])


def render_trace_diff(run: str) -> None:
    st.subheader("Compare two traces")
    feats = state.features(run).simulations
    options = {
        f"{f.simulation_id} · task {f.task_id} · {f.failure_type.value}": f.simulation_id
        for f in sorted(
            feats, key=lambda x: (x.failure_type.value != "pass", x.task_id)
        )
    }
    keys = list(options.keys())
    if len(keys) < 2:
        st.info("Need at least two simulations to compare.")
        return
    c1, c2 = st.columns(2)
    with c1:
        left = st.selectbox("Left", keys, index=0, key="diff_left")
    with c2:
        right = st.selectbox(
            "Right", keys, index=min(1, len(keys) - 1), key="diff_right"
        )

    lcol, rcol = st.columns(2)
    with lcol:
        render_trace(run, options[left])
    with rcol:
        render_trace(run, options[right])


def render_cluster_gallery(run: str, cluster_id: str, *, max_reps: int = 3) -> None:
    """Show representative traces for a cluster side by side."""
    clusters = {c.id: c for c in state.clusters(run).clusters}
    cluster = clusters.get(cluster_id)
    if cluster is None:
        st.warning(f"Cluster `{cluster_id}` not found.")
        return

    label = state.label_by_cluster(run).get(cluster_id)
    title = label.display_name if label else cluster.name
    st.markdown(f"### {cluster_id} — {title}")
    st.caption(
        f"n={cluster.count} · failure_type={cluster.failure_type} · "
        f"signature=`{cluster.signature or '—'}`"
    )
    if label:
        st.markdown(f"**Blame:** {', '.join(f'`{b}`' for b in label.blame_tags)}")
        st.markdown(f"_{label.summary}_")

    reps = (
        label.representative_simulation_ids if label else []
    ) or cluster.simulation_ids
    reps = reps[:max_reps]
    cols = st.columns(len(reps)) if reps else []
    for col, sim_id in zip(cols, reps):
        with col:
            render_trace(run, sim_id, show_signals=True)
