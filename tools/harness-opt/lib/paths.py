"""Path helpers for harness-opt artifacts."""

from __future__ import annotations

import os
from pathlib import Path

# tools/harness-opt/lib/paths.py -> repo root is 3 levels up
REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS_OPT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
SIMULATIONS_DIR = DATA_DIR / "simulations"


def _reports_dir() -> Path:
    env = os.environ.get("HARNESS_OPT_REPORTS_DIR")
    if env:
        return Path(env)
    return REPO_ROOT / "reports"


REPORTS_DIR = _reports_dir()
FIXTURES_DIR = HARNESS_OPT_ROOT / "fixtures"


def simulation_run_path(run_name: str) -> Path:
    """Path to a tau2 simulation run directory or results file."""
    run_dir = SIMULATIONS_DIR / run_name
    if run_dir.is_dir():
        results_json = run_dir / "results.json"
        if results_json.exists():
            return results_json
        return run_dir
    if run_dir.with_suffix(".json").exists():
        return run_dir.with_suffix(".json")
    return run_dir


def report_dir(run_name: str) -> Path:
    return _reports_dir() / run_name


def artifact_path(run_name: str, filename: str) -> Path:
    return report_dir(run_name) / filename


def proposal_dir(run_name: str, proposal_id: str) -> Path:
    return report_dir(run_name) / "proposals" / proposal_id


def proposals_dir(run_name: str) -> Path:
    return report_dir(run_name) / "proposals"


def lineages_dir() -> Path:
    return _reports_dir() / "lineages"


def lineage_state_path(lineage_id: str) -> Path:
    return lineages_dir() / f"{lineage_id}.json"


def _worktrees_dir() -> Path:
    env = os.environ.get("HARNESS_OPT_WORKTREES_DIR")
    if env:
        return Path(env)
    return REPO_ROOT / ".harness-opt-worktrees"


def lineage_worktree_dir(lineage_id: str) -> Path:
    return _worktrees_dir() / lineage_id


def _locks_dir() -> Path:
    return _reports_dir() / ".locks"


def lineage_lock(lineage_id: str) -> Path:
    return _locks_dir() / f"{lineage_id}.lock"
