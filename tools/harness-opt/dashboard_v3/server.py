"""v3 dashboard backend: FastAPI JSON API + static SPA serving.

Run:
    uv run python tools/harness-opt/cli.py dashboard          # or:
    uv run python tools/harness-opt/dashboard_v3/server.py --port 8770
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Allow running this file directly (python dashboard_v3/server.py): the harness
# -opt root (parent of this dir) must be on sys.path before importing lib.*.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.bootstrap import bootstrap  # noqa: E402

bootstrap()

from dashboard_v3 import data  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

CLIENT_DIR = Path(__file__).parent / "client"
HARNESS_OPT_ROOT = Path(__file__).resolve().parents[1]
CLI = HARNESS_OPT_ROOT / "cli.py"


class ProposeRequest(BaseModel):
    cluster: str
    coder: str = "auto"
    coder_model: str | None = None
    lineage: str | None = None
    baseline: str | None = None
    do_eval: bool = False


class EditRequest(BaseModel):
    files: dict[str, str]


def _run_cli(args: list[str], timeout_s: int) -> dict:
    """Shell the harness-opt CLI (propose/accept/reject) and capture output."""
    cmd = [sys.executable, str(CLI), *args]
    env = {**os.environ, "PYTHONPATH": str(HARNESS_OPT_ROOT)}
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(HARNESS_OPT_ROOT),
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"timed out after {timeout_s}s",
        }
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-8000:],
    }


def create_app() -> FastAPI:
    app = FastAPI(title="harness-opt dashboard v3")

    @app.middleware("http")
    async def _no_cache(request, call_next):
        # Dev tool: never let the browser serve stale JS/CSS modules or API data.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/runs")
    def api_runs():
        return data.list_runs()

    @app.get("/api/runs/{run}/summary")
    def api_summary(run: str):
        if not data.report_exists(run):
            raise HTTPException(404, f"run not found: {run}")
        return data.run_summary(run)

    @app.get("/api/runs/{run}/summary_md")
    def api_summary_md(run: str):
        return JSONResponse({"markdown": data.summary_markdown(run)})

    @app.get("/api/runs/{run}/tasks")
    def api_tasks(run: str):
        if not data.report_exists(run):
            raise HTTPException(404, f"run not found: {run}")
        return data.task_rows(run)

    @app.get("/api/runs/{run}/embedding")
    def api_embedding(run: str):
        if not data.report_exists(run):
            raise HTTPException(404, f"run not found: {run}")
        return data.embedding(run)

    # ---- Phase 2: proposals + lineages ----

    @app.get("/api/lineages")
    def api_lineages():
        return data.list_lineages()

    @app.get("/api/runs/{run}/proposals")
    def api_proposals(run: str):
        return data.proposals_index(run)

    @app.get("/api/runs/{run}/proposals/{proposal_id}")
    def api_proposal(run: str, proposal_id: str):
        detail = data.proposal_detail(run, proposal_id)
        if detail is None:
            raise HTTPException(404, f"proposal not found: {proposal_id}")
        return detail

    @app.post("/api/runs/{run}/propose")
    def api_propose(run: str, req: ProposeRequest):
        args = ["propose", "--run", run, "--cluster", req.cluster, "--coder", req.coder]
        if req.coder_model:
            args += ["--coder-model", req.coder_model]
        if req.lineage:
            args += ["--lineage", req.lineage]
        if req.baseline:
            args += ["--baseline", req.baseline]
        if req.do_eval:
            args += ["--eval"]
        # draft (no eval) is quick; --eval runs tau2 and can take minutes.
        return _run_cli(args, timeout_s=2400 if req.do_eval else 420)

    @app.post("/api/runs/{run}/proposals/{proposal_id}/accept")
    def api_accept(run: str, proposal_id: str):
        return _run_cli(
            ["accept", "--run", run, "--proposal", proposal_id], timeout_s=120
        )

    @app.post("/api/runs/{run}/proposals/{proposal_id}/reject")
    def api_reject(run: str, proposal_id: str):
        return _run_cli(
            ["reject", "--run", run, "--proposal", proposal_id], timeout_s=120
        )

    @app.get("/api/runs/{run}/proposals/{proposal_id}/files")
    def api_proposal_files(run: str, proposal_id: str):
        files = data.proposal_files(run, proposal_id)
        if files is None:
            raise HTTPException(404, f"proposal not found: {proposal_id}")
        return files

    @app.post("/api/runs/{run}/proposals/{proposal_id}/files")
    def api_edit_files(run: str, proposal_id: str, req: EditRequest):
        try:
            return data.apply_proposal_files(run, proposal_id, req.files)
        except PermissionError as exc:
            raise HTTPException(400, str(exc))
        except ValueError as exc:
            raise HTTPException(404, str(exc))

    @app.post("/api/runs/{run}/proposals/{proposal_id}/eval")
    def api_eval_proposal(run: str, proposal_id: str):
        # Runs tau2 on the subset against the edited branch — minutes, spends budget.
        return _run_cli(
            ["eval-proposal", "--run", run, "--proposal", proposal_id], timeout_s=2400
        )

    @app.post("/api/runs/{run}/proposals/{proposal_id}/delete")
    def api_delete_proposal(run: str, proposal_id: str):
        return _run_cli(
            ["delete-proposal", "--run", run, "--proposal", proposal_id], timeout_s=120
        )

    @app.get("/api/runs/{run}/sims/{sim_id}")
    def api_sim(run: str, sim_id: str):
        detail = data.sim_detail(run, sim_id)
        if detail is None:
            raise HTTPException(404, f"simulation not found: {sim_id}")
        return detail

    # Serve the SPA. index.html at root; static assets under their paths.
    @app.get("/")
    def index():
        return FileResponse(CLIENT_DIR / "index.html")

    if CLIENT_DIR.exists():
        app.mount("/", StaticFiles(directory=str(CLIENT_DIR), html=True), name="client")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="harness-opt dashboard v3 server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
