"""Cluster visualization: treemap, cluster table, and per-cluster drill-down."""

from __future__ import annotations

import dashboard.state as state
import pandas as pd
import plotly.express as px
import streamlit as st
from dashboard.components import traces as traces_ui


def _clusters_dataframe(run: str) -> pd.DataFrame:
    clusters = state.clusters(run).clusters
    label_map = state.label_by_cluster(run)
    rows = []
    for c in clusters:
        label = label_map.get(c.id)
        rows.append(
            {
                "cluster_id": c.id,
                "failure_type": c.failure_type,
                "label": label.display_name if label else c.name,
                "signature": c.signature or "",
                "count": c.count,
                "n_tasks": len(c.task_ids),
                "blame": ", ".join(label.blame_tags) if label else "",
                "cohesion": label.cohesion if label else None,
            }
        )
    return pd.DataFrame(rows)


def render_treemap(run: str) -> None:
    df = _clusters_dataframe(run)
    if df.empty:
        st.info("No failure clusters in this run.")
        return
    df = df.copy()
    df["display"] = df["cluster_id"] + " (" + df["count"].astype(str) + ")"
    fig = px.treemap(
        df,
        path=[px.Constant("failures"), "failure_type", "display"],
        values="count",
        color="failure_type",
        hover_data=["label", "signature", "n_tasks"],
    )
    fig.update_traces(root_color="lightgrey")
    fig.update_layout(margin=dict(t=20, l=0, r=0, b=0), height=420)
    st.plotly_chart(fig, use_container_width=True)


def render_cluster_table(run: str) -> None:
    df = _clusters_dataframe(run)
    if df.empty:
        return
    st.dataframe(
        df[
            [
                "cluster_id",
                "failure_type",
                "count",
                "n_tasks",
                "label",
                "blame",
                "signature",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_singleton_note(run: str) -> None:
    df = _clusters_dataframe(run)
    if df.empty:
        return
    n = len(df)
    singletons = int((df["count"] == 1).sum())
    pct = 100 * singletons / n if n else 0
    st.caption(
        f"{n} clusters · {singletons} singletons ({pct:.0f}%). "
        "High singleton rate mixes genuinely-unique mechanisms with "
        "under-clustered near-duplicates — inspect below."
    )


def render_cluster_drilldown(run: str) -> None:
    st.subheader("Cluster drill-down")
    clusters = state.clusters(run).clusters
    if not clusters:
        st.info("No clusters.")
        return
    label_map = state.label_by_cluster(run)

    def _fmt(c):
        label = label_map.get(c.id)
        title = label.display_name if label else c.name
        return f"{c.id} · n={c.count} · {title}"

    options = {_fmt(c): c.id for c in clusters}
    choice = st.selectbox("Cluster", list(options.keys()))
    if not choice:
        return
    cluster_id = options[choice]
    cluster = {c.id: c for c in clusters}[cluster_id]

    # Member table with per-sim signals.
    feats = state.features_by_id(run)
    member_rows = []
    for sid in cluster.simulation_ids:
        f = feats.get(sid)
        if f is None:
            continue
        member_rows.append(
            {
                "simulation_id": sid,
                "task_id": f.task_id,
                "trial": f.trial,
                "reward": f.reward,
                "tool_chain": " → ".join(
                    f.normalized_tool_chain or [t.name for t in f.tool_sequence]
                ),
                "db_diff_signature": f.db_diff_signature or "",
                "nl_failure_signature": f.nl_failure_signature or "",
            }
        )
    st.markdown(f"**Signature:** `{cluster.signature or '—'}`")
    st.dataframe(pd.DataFrame(member_rows), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Representative traces")
    traces_ui.render_cluster_gallery(run, cluster_id)


def render_clusters_page(run: str) -> None:
    st.header(f"Clusters — {run}")
    render_singleton_note(run)
    render_treemap(run)
    render_cluster_table(run)
    st.divider()
    render_cluster_drilldown(run)
