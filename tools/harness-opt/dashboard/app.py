"""Harness-opt dashboard (Phase 1).

Read-only Streamlit explorer over Phase 0 report artifacts.

Run with:
    uv run streamlit run tools/harness-opt/dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `lib`, `contracts`, `dashboard`, and `tau2` importable regardless of CWD.
_HARNESS_OPT_ROOT = Path(__file__).resolve().parents[1]
if str(_HARNESS_OPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_HARNESS_OPT_ROOT))

from lib.bootstrap import bootstrap  # noqa: E402

bootstrap()

import dashboard.state as state  # noqa: E402
import streamlit as st  # noqa: E402
from dashboard.components import actions, clusters, metrics  # noqa: E402
from dashboard.components import traces as traces_ui  # noqa: E402

st.set_page_config(page_title="harness-opt", layout="wide")


def main() -> None:
    st.sidebar.title("harness-opt")

    runs = state.list_runs()
    if not runs:
        st.title("No analyzed runs found")
        st.info(
            "No `reports/<run>/manifest.json` found. Run the pipeline first:\n\n"
            "```\nuv run python tools/harness-opt/cli.py analyze "
            "--run <name> --mock-label\n```"
        )
        return

    run = st.sidebar.selectbox("Run", runs)
    page = st.sidebar.radio(
        "Page",
        [
            "Overview",
            "Clusters",
            "Trace explorer",
            "Compare traces",
            "Compare runs",
            "Proposals",
            "Actions",
        ],
    )

    man = state.manifest(run)
    st.sidebar.caption(
        f"domain: {man.domain}\n\n"
        f"sims: {man.num_simulations}\n\n"
        f"baseline: {man.baseline_run or '—'}\n\n"
        f"git: {(man.git_sha or '')[:8] or '—'}"
    )

    if page == "Overview":
        metrics.render_overview(run)
    elif page == "Clusters":
        clusters.render_clusters_page(run)
    elif page == "Trace explorer":
        traces_ui.render_trace_explorer(run)
    elif page == "Compare traces":
        traces_ui.render_trace_diff(run)
    elif page == "Compare runs":
        others = [r for r in runs if r != run]
        if not others:
            st.info("Need at least two analyzed runs to compare.")
        else:
            baseline_default = (
                man.baseline_run if man.baseline_run in others else others[0]
            )
            other = st.selectbox(
                "Compare against (baseline)",
                others,
                index=others.index(baseline_default)
                if baseline_default in others
                else 0,
            )
            metrics.render_comparison(other, run)
    elif page == "Proposals":
        st.header("Proposals")
        st.info("Proposal workflow is wired in Phase 2. (Placeholder.)")
    elif page == "Actions":
        actions.render_actions(run)


if __name__ == "__main__":
    main()
