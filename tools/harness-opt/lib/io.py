"""I/O helpers: load simulations, write immutable report artifacts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TypeVar

from lib.paths import artifact_path, report_dir, simulation_run_path
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ArtifactExistsError(FileExistsError):
    """Raised when attempting to overwrite an existing artifact."""


def get_git_sha(repo_root: Path | None = None) -> str | None:
    root = repo_root or Path(__file__).resolve().parents[3]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def ensure_report_dir(run_name: str) -> Path:
    path = report_dir(run_name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json_artifact(
    run_name: str,
    filename: str,
    model: BaseModel,
    *,
    overwrite: bool = False,
) -> Path:
    """Write a Pydantic model to reports/<run>/<filename>."""
    ensure_report_dir(run_name)
    path = artifact_path(run_name, filename)
    if path.exists() and not overwrite:
        raise ArtifactExistsError(f"Refusing to overwrite existing artifact: {path}")
    path.write_text(model.model_dump_json(indent=2))
    return path


def read_json_artifact(path: Path, model: type[T]) -> T:
    data = json.loads(path.read_text())
    return model.model_validate(data)


def load_simulation_path(run_name: str) -> Path:
    path = simulation_run_path(run_name)
    if not path.exists():
        raise FileNotFoundError(
            f"Simulation run not found: {run_name} (looked at {path})"
        )
    return path


def write_text_artifact(
    run_name: str,
    filename: str,
    content: str,
    *,
    overwrite: bool = False,
) -> Path:
    ensure_report_dir(run_name)
    path = artifact_path(run_name, filename)
    if path.exists() and not overwrite:
        raise ArtifactExistsError(f"Refusing to overwrite existing artifact: {path}")
    path.write_text(content)
    return path
