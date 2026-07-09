"""v3 dashboard backend: FastAPI JSON API + static SPA serving.

Run:
    uv run python tools/harness-opt/cli.py dashboard          # or:
    uv run python tools/harness-opt/dashboard_v3/server.py --port 8770
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lib.bootstrap import bootstrap

bootstrap()

from dashboard_v3 import data  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

CLIENT_DIR = Path(__file__).parent / "client"


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
