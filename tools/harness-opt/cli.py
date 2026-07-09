#!/usr/bin/env python3
"""Harness-opt CLI — analyze, cluster, label, build subsets, eval."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import typer
from lib.bootstrap import bootstrap

bootstrap()

app = typer.Typer(help="Harness optimization tooling for tau2-bench retail domain")
HARNESS_OPT_ROOT = Path(__file__).resolve().parent
SCRIPTS = HARNESS_OPT_ROOT / "scripts"


def _run_script(script: str, *args: str) -> None:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    env = {**os.environ, "PYTHONPATH": str(HARNESS_OPT_ROOT)}
    subprocess.run(cmd, cwd=str(HARNESS_OPT_ROOT), check=True, env=env)


@app.command()
def extract(
    run: str = typer.Option(..., "--run", help="Simulation run name"),
    domain: str = typer.Option("retail", "--domain"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Extract features.json from a simulation run."""
    args = ["--run", run, "--domain", domain]
    if overwrite:
        args.append("--overwrite")
    _run_script("extract_features.py", *args)


@app.command()
def cluster(
    run: str = typer.Option(..., "--run"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Cluster failures into clusters_l0.json and clusters.json."""
    args = ["--run", run]
    if overwrite:
        args.append("--overwrite")
    _run_script("cluster.py", *args)


@app.command()
def label(
    run: str = typer.Option(..., "--run"),
    mock: bool = typer.Option(False, "--mock", help="Skip LLM API calls"),
    model: str = typer.Option("gpt-4.1-mini", "--model"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Label clusters (LLM on representatives, or --mock)."""
    args = ["--run", run]
    if mock:
        args.append("--mock")
    args.extend(["--model", model])
    if overwrite:
        args.append("--overwrite")
    _run_script("label_clusters.py", *args)


@app.command()
def report(
    run: str = typer.Option(..., "--run"),
    baseline: str | None = typer.Option(None, "--baseline"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Generate manifest, task_summary.csv, analysis_summary.md."""
    args = ["--run", run]
    if baseline:
        args.extend(["--baseline", baseline])
    if overwrite:
        args.append("--overwrite")
    _run_script("generate_report.py", *args)


@app.command("build-subset")
def build_subset(
    run: str = typer.Option(..., "--run"),
    mode: str = typer.Option(..., "--mode", help="oracle or cluster"),
    cluster: str | None = typer.Option(None, "--cluster"),
    baseline: str | None = typer.Option(None, "--baseline"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Build oracle.json or per-cluster subset_spec.json."""
    args = ["--run", run, "--mode", mode]
    if cluster:
        args.extend(["--cluster", cluster])
    if baseline:
        args.extend(["--baseline", baseline])
    if overwrite:
        args.append("--overwrite")
    _run_script("build_subset.py", *args)


@app.command("eval-subset")
def eval_subset(
    run: str = typer.Option(..., "--run"),
    proposal: str = typer.Option(..., "--proposal"),
    baseline: str | None = typer.Option(None, "--baseline"),
    candidate_run: str | None = typer.Option(None, "--candidate-run"),
    skip_tau2: bool = typer.Option(False, "--skip-tau2"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Run subset eval for a proposal vs baseline."""
    args = ["--run", run, "--proposal", proposal]
    if baseline:
        args.extend(["--baseline", baseline])
    if candidate_run:
        args.extend(["--candidate-run", candidate_run])
    if skip_tau2:
        args.append("--skip-tau2")
    if overwrite:
        args.append("--overwrite")
    _run_script("eval_subset.py", *args)


@app.command()
def analyze(
    run: str = typer.Option(..., "--run"),
    baseline: str | None = typer.Option(None, "--baseline"),
    mock_label: bool = typer.Option(False, "--mock-label"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Full pipeline: extract → cluster → label → report."""
    ow = ["--overwrite"] if overwrite else []
    _run_script("extract_features.py", "--run", run, *ow)
    _run_script("cluster.py", "--run", run, *ow)
    label_args = ["--run", run, *ow]
    if mock_label:
        label_args.append("--mock")
    _run_script("label_clusters.py", *label_args)
    report_args = ["--run", run]
    if baseline:
        report_args.extend(["--baseline", baseline])
    if overwrite:
        report_args.append("--overwrite")
    _run_script("generate_report.py", *report_args)
    typer.echo(f"Analysis complete: reports/{run}/")


if __name__ == "__main__":
    app()
