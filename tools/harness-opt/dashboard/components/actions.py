"""Actions: trigger the Phase 0 CLI (re-analyze) as a subprocess.

The dashboard never reimplements analysis; it shells out to `cli.py` exactly
like a human would, then clears caches so the new artifacts are picked up.
"""

from __future__ import annotations

import subprocess
import sys

import streamlit as st
from lib.paths import HARNESS_OPT_ROOT

_CLI = HARNESS_OPT_ROOT / "cli.py"


def _run_analyze(run: str, baseline: str | None, mock_label: bool) -> tuple[int, str]:
    cmd = [sys.executable, str(_CLI), "analyze", "--run", run, "--overwrite"]
    if baseline:
        cmd += ["--baseline", baseline]
    if mock_label:
        cmd += ["--mock-label"]
    proc = subprocess.run(
        cmd,
        cwd=str(HARNESS_OPT_ROOT),
        capture_output=True,
        text=True,
    )
    return proc.returncode, (proc.stdout + "\n" + proc.stderr)


def render_actions(run: str) -> None:
    st.subheader("Re-analyze")
    st.caption(
        "Runs `cli.py analyze --overwrite` for this run (extract → cluster → "
        "label → report), then refreshes cached artifacts."
    )
    baseline = st.text_input("Baseline run (optional)", value=run)
    mock = st.checkbox("Mock labels (no LLM calls)", value=True)
    if st.button("Run analyze", type="primary"):
        with st.spinner(f"Analyzing {run}…"):
            code, output = _run_analyze(run, baseline or None, mock)
        if code == 0:
            st.success("Analyze complete. Caches cleared.")
            st.cache_data.clear()
        else:
            st.error(f"Analyze failed (exit {code}).")
        with st.expander("CLI output", expanded=code != 0):
            st.code(output)
