"""Cached, read-only loaders for Phase 0 report artifacts.

The dashboard is a pure consumer: it never recomputes analysis, it only reads
`reports/<run>/*` (and raw trajectories via `Results.load`). All loaders are
cached on the artifact's mtime so edits/re-analyze runs invalidate cleanly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from contracts.models import (
    ClusterLabelsArtifact,
    ClustersArtifact,
    FeaturesArtifact,
    ManifestArtifact,
    SimulationFeatures,
)
from lib.io import read_json_artifact
from lib.paths import REPO_ROOT, artifact_path, report_dir
from lib.paths import _reports_dir as reports_root


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def list_runs() -> list[str]:
    """Run names that have a manifest.json, newest first."""
    root = reports_root()
    if not root.exists():
        return []
    runs = [
        p.name for p in root.iterdir() if p.is_dir() and (p / "manifest.json").exists()
    ]
    return sorted(
        runs, key=lambda r: _mtime(report_dir(r) / "manifest.json"), reverse=True
    )


def has_artifact(run: str, filename: str) -> bool:
    return artifact_path(run, filename).exists()


@st.cache_data(show_spinner=False)
def load_manifest(run: str, _mtime: float) -> ManifestArtifact:
    return read_json_artifact(artifact_path(run, "manifest.json"), ManifestArtifact)


@st.cache_data(show_spinner=False)
def load_clusters(run: str, _mtime: float) -> ClustersArtifact:
    return read_json_artifact(artifact_path(run, "clusters.json"), ClustersArtifact)


@st.cache_data(show_spinner=False)
def load_l0(run: str, _mtime: float) -> ClustersArtifact:
    return read_json_artifact(artifact_path(run, "clusters_l0.json"), ClustersArtifact)


@st.cache_data(show_spinner=False)
def load_labels(run: str, _mtime: float) -> Optional[ClusterLabelsArtifact]:
    path = artifact_path(run, "cluster_labels.json")
    if not path.exists():
        return None
    return read_json_artifact(path, ClusterLabelsArtifact)


@st.cache_data(show_spinner=False)
def load_features(run: str, _mtime: float) -> FeaturesArtifact:
    return read_json_artifact(artifact_path(run, "features.json"), FeaturesArtifact)


@st.cache_data(show_spinner=False)
def load_task_summary(run: str, _mtime: float) -> pd.DataFrame:
    return pd.read_csv(artifact_path(run, "task_summary.csv"))


@st.cache_data(show_spinner=True)
def load_simulations(run: str, sim_path: str, _mtime: float) -> dict:
    """Load raw trajectories keyed by simulation id (heavy; cached per run)."""
    from tau2.data_model.simulation import Results

    path = Path(sim_path)
    if not path.is_absolute():
        path = REPO_ROOT / sim_path
    results = Results.load(str(path))
    return {s.id: s for s in results.simulations}


# ---- convenience wrappers (compute the mtime cache key for the caller) ----


def manifest(run: str) -> ManifestArtifact:
    return load_manifest(run, _mtime(artifact_path(run, "manifest.json")))


def clusters(run: str) -> ClustersArtifact:
    return load_clusters(run, _mtime(artifact_path(run, "clusters.json")))


def l0(run: str) -> ClustersArtifact:
    return load_l0(run, _mtime(artifact_path(run, "clusters_l0.json")))


def labels(run: str) -> Optional[ClusterLabelsArtifact]:
    return load_labels(run, _mtime(artifact_path(run, "cluster_labels.json")))


def features(run: str) -> FeaturesArtifact:
    return load_features(run, _mtime(artifact_path(run, "features.json")))


def task_summary(run: str) -> pd.DataFrame:
    return load_task_summary(run, _mtime(artifact_path(run, "task_summary.csv")))


def simulations(run: str) -> dict:
    man = manifest(run)
    return load_simulations(
        run, man.simulation_path, _mtime(artifact_path(run, "manifest.json"))
    )


def features_by_id(run: str) -> dict[str, SimulationFeatures]:
    return {s.simulation_id: s for s in features(run).simulations}


def label_by_cluster(run: str) -> dict:
    lb = labels(run)
    return {label.cluster_id: label for label in lb.labels} if lb else {}


def artifact_summary_path(run: str) -> Path:
    return artifact_path(run, "analysis_summary.md")
