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
DASHBOARD_V2 = HARNESS_OPT_ROOT / "dashboard_v2"


def _run_path(script_path: Path, *args: str, check: bool = True) -> int:
    cmd = [sys.executable, str(script_path), *args]
    env = {**os.environ, "PYTHONPATH": str(HARNESS_OPT_ROOT)}
    proc = subprocess.run(cmd, cwd=str(HARNESS_OPT_ROOT), check=check, env=env)
    return proc.returncode


def _run_script(script: str, *args: str) -> None:
    _run_path(SCRIPTS / script, *args)


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
def viewer(
    run: str = typer.Option(..., "--run"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Generate the v2 static HTML trace viewer (reports/<run>/trace_viewer.html)."""
    args = ["--run", run]
    if overwrite:
        args.append("--overwrite")
    _run_path(DASHBOARD_V2 / "generate.py", *args)


@app.command()
def dashboard(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8770, "--port"),
) -> None:
    """Launch the v3 dashboard (FastAPI backend + SPA) at http://host:port."""
    _run_path(
        HARNESS_OPT_ROOT / "dashboard_v3" / "server.py",
        "--host",
        host,
        "--port",
        str(port),
    )


@app.command()
def propose(
    run: str = typer.Option(..., "--run"),
    cluster: str = typer.Option(..., "--cluster"),
    lineage: str | None = typer.Option(
        None, "--lineage", help="Lineage id (default: run)"
    ),
    baseline: str | None = typer.Option(
        None, "--baseline", help="Generation baseline run"
    ),
    coder: str = typer.Option(
        "auto", "--coder", help="auto|openai|claude|cursor|manual"
    ),
    coder_model: str | None = typer.Option(
        None, "--coder-model", help="Proposer model (default gpt-4.1)"
    ),
    eval: bool = typer.Option(
        False, "--eval", help="Run subset eval (spends OpenAI budget)"
    ),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Create an auto-coded harness proposal from a cluster (lineage-isolated)."""
    args = ["--run", run, "--cluster", cluster, "--coder", coder]
    if coder_model:
        args.extend(["--coder-model", coder_model])
    if lineage:
        args.extend(["--lineage", lineage])
    if baseline:
        args.extend(["--baseline", baseline])
    if eval:
        args.append("--eval")
    if overwrite:
        args.append("--overwrite")
    _run_script("propose.py", *args)


@app.command()
def accept(
    run: str = typer.Option(..., "--run"),
    proposal: str = typer.Option(..., "--proposal"),
) -> None:
    """Squash-commit a proposal onto its lineage branch."""
    _run_script("manage_proposal.py", "accept", "--run", run, "--proposal", proposal)


@app.command()
def reject(
    run: str = typer.Option(..., "--run"),
    proposal: str = typer.Option(..., "--proposal"),
) -> None:
    """Discard a proposal's ephemeral branch (lineage untouched)."""
    _run_script("manage_proposal.py", "reject", "--run", run, "--proposal", proposal)


@app.command("list-proposals")
def list_proposals(
    run: str | None = typer.Option(None, "--run"),
) -> None:
    """Print the proposal table and lineage branches."""
    args = ["list"]
    if run:
        args.extend(["--run", run])
    _run_script("manage_proposal.py", *args)


@app.command()
def analyze(
    run: str = typer.Option(..., "--run"),
    baseline: str | None = typer.Option(None, "--baseline"),
    mock_label: bool = typer.Option(False, "--mock-label"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Full pipeline: extract → cluster → label → report → viewer."""
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
    # Best-effort: the static viewer is a convenience artifact; don't fail the
    # whole pipeline if it can't be generated.
    code = _run_path(DASHBOARD_V2 / "generate.py", "--run", run, *ow, check=False)
    if code != 0:
        typer.echo("Warning: trace_viewer.html generation failed (non-fatal).")
    typer.echo(f"Analysis complete: reports/{run}/")


if __name__ == "__main__":
    app()
