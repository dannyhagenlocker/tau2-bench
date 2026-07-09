# Phase 1 — Dashboard

**Status:** Implemented. The current UI is **v3** (FastAPI + no-build SPA).

> **Current UI doc → [`dashboard.md`](dashboard.md).** That is the source of
> truth for the frontend. Everything below the divider is **historical** (the
> original Streamlit-oriented plan and the superseded v1/v2 implementations),
> kept for context only.

## Goal

Interactive app for engineers to explore runs, clusters, traces, the embedding
space, run comparisons, and (Phase 2) proposals. Read-mostly consumer of Phase 0
artifacts; a few actions shell the CLI.

## Entry

```bash
uv sync --extra harness-opt        # fastapi/uvicorn (already deps) + plotly/sklearn
uv run python tools/harness-opt/cli.py dashboard   # → http://127.0.0.1:8770
```

---

## History (superseded)

### v3 — FastAPI + SPA (CURRENT)
See [`dashboard.md`](dashboard.md). `tools/harness-opt/dashboard_v3/`.

### v2 — static HTML trace viewer (SUPERSEDED by v3; generator still exists)
`tools/harness-opt/dashboard_v2/generate.py` emits a self-contained
`reports/<run>/trace_viewer.html` (SVG swimlane + LCS diff, data inlined). Still
produced best-effort at the end of `analyze` and via `cli.py viewer`, but the v3
Traces page is the maintained path.

### v1 — Streamlit (SUPERSEDED)
`tools/harness-opt/dashboard/` (`streamlit run … dashboard/app.py`). Hit a soft
ceiling on dense trace comparison; replaced by v3. Retained but not maintained.

### Original MVP plan (HISTORICAL — do not use as spec)
The initial Phase 1 plan targeted a Streamlit MVP with pages RunOverview /
RunComparison / Clusters / TraceExplorer / ClusterGallery / Proposals and agent
briefs P1-Shell/VizCore/Traces/Actions. That plan is **obsolete** — the shipped
v3 app reorganizes and extends it (Embedding page, mechanism taxonomy, proposal
ReviewUI, etc.). Refer to [`dashboard.md`](dashboard.md) instead.
