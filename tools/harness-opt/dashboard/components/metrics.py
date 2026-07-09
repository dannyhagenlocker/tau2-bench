"""Run overview metrics and baseline-vs-candidate comparison."""

from __future__ import annotations

import dashboard.state as state
import pandas as pd
import plotly.express as px
import streamlit as st


def _task_reward(df: pd.DataFrame) -> pd.DataFrame:
    """Mean reward and pass fraction per task (averaged over trials)."""
    agg = (
        df.groupby("task_id")
        .agg(reward=("reward", "mean"), trials=("reward", "size"))
        .reset_index()
    )
    return agg


def render_overview(run: str) -> None:
    man = state.manifest(run)
    df = state.task_summary(run)

    st.header(f"Overview — {run}")
    c = st.columns(5)
    c[0].metric("Simulations", man.num_simulations)
    c[1].metric("Pass rate", f"{(df['reward'] >= 0.999).mean():.1%}")
    c[2].metric("Trials", man.num_trials or "—")
    c[3].metric("Agent LLM", man.agent_llm or "—")
    c[4].metric("User LLM", man.user_llm or "—")

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("Failure taxonomy (L0)")
        l0 = state.l0(run).clusters
        l0_df = pd.DataFrame(
            [{"bucket": c.name, "count": c.count} for c in l0]
        ).sort_values("count", ascending=False)
        fig = px.bar(l0_df, x="count", y="bucket", orientation="h", height=280)
        fig.update_layout(margin=dict(t=10, l=0, r=0, b=0), yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Task × trial reward heatmap")
        pivot = df.pivot_table(
            index="task_id", columns="trial", values="reward", aggfunc="mean"
        )
        fig = px.imshow(
            pivot,
            color_continuous_scale="RdYlGn",
            zmin=0,
            zmax=1,
            aspect="auto",
            height=280,
        )
        fig.update_layout(margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("analysis_summary.md"):
        summary_path = state.artifact_summary_path(run)
        if summary_path.exists():
            st.markdown(summary_path.read_text())


def render_comparison(run_a: str, run_b: str) -> None:
    st.header("Run comparison")
    st.caption(f"Baseline **{run_a}** → candidate **{run_b}** (mean reward per task)")

    a = _task_reward(state.task_summary(run_a)).rename(columns={"reward": "reward_a"})
    b = _task_reward(state.task_summary(run_b)).rename(columns={"reward": "reward_b"})
    merged = a.merge(b, on="task_id", how="outer", suffixes=("_a", "_b"))
    merged["delta"] = merged["reward_b"].fillna(0) - merged["reward_a"].fillna(0)

    def _flip(row) -> str:
        pa = (row.get("reward_a") or 0) >= 0.999
        pb = (row.get("reward_b") or 0) >= 0.999
        if pa and not pb:
            return "regressed"
        if pb and not pa:
            return "improved"
        return "same"

    merged["flip"] = merged.apply(_flip, axis=1)

    c = st.columns(3)
    c[0].metric("Improved", int((merged["flip"] == "improved").sum()))
    c[1].metric("Regressed", int((merged["flip"] == "regressed").sum()))
    c[2].metric("Mean Δ reward", f"{merged['delta'].mean():+.3f}")

    changed = merged[merged["delta"].abs() > 1e-9].sort_values("delta")
    if changed.empty:
        st.info("No per-task reward changes between the two runs.")
        return
    fig = px.bar(
        changed,
        x="delta",
        y="task_id",
        color="flip",
        orientation="h",
        color_discrete_map={
            "improved": "#2ca02c",
            "regressed": "#d62728",
            "same": "#999999",
        },
        height=max(300, 22 * len(changed)),
    )
    fig.update_layout(margin=dict(t=10, l=0, r=0, b=0), yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        changed[["task_id", "reward_a", "reward_b", "delta", "flip"]],
        use_container_width=True,
        hide_index=True,
    )
