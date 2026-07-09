# Phase 1 — Dashboard MVP

**Status:** MVP implemented  
**Agents:** P1-Shell, P1-VizCore, P1-Traces, P1-Actions

## Goal

Interactive Streamlit app for engineers to explore runs, clusters, and traces. **Read-only** consumer of Phase 0 artifacts; triggers CLI via subprocess.

## Entry

```bash
uv sync --extra harness-opt          # streamlit + plotly + scikit-learn
uv run streamlit run tools/harness-opt/dashboard/app.py
```

## Implemented layout

```
tools/harness-opt/dashboard/
├── app.py                     # P1-Shell: run selector + page nav (bootstraps sys.path)
├── state.py                   # P1-Shell: mtime-keyed cached artifact loaders
└── components/
    ├── metrics.py             # P1-VizCore: Overview (L0 bars, task×trial heatmap) + Compare runs (delta)
    ├── clusters.py            # P1-VizCore: treemap + cluster table + drill-down (member signals)
    ├── traces.py              # P1-Traces: trace timeline, signal badges, cluster gallery, side-by-side diff
    └── actions.py             # P1-Actions: "Run analyze" subprocess + cache clear
```

Pages: **Overview**, **Clusters** (treemap → member table → representative gallery),
**Trace explorer**, **Compare traces** (side-by-side), **Compare runs** (per-task delta,
pass↔fail flips), **Proposals** (Phase 2 stub), **Actions** (re-analyze).

## v2 — static HTML trace viewer

The Streamlit app is good for run/cluster overview but has a soft ceiling on
dense trace comparison. `dashboard_v2/` generates a **self-contained static HTML
viewer** (no server, no network — data inlined) purpose-built for inspecting and
diffing traces.

```
tools/harness-opt/dashboard_v2/
├── generate.py       # reads Phase 0 artifacts + raw sims → reports/<run>/trace_viewer.html
└── template.html     # vanilla-JS SPA (SVG swimlane, LCS aligner, sync diff)
```

Generate (also runs automatically at the end of `analyze`, best-effort):

```bash
uv run python tools/harness-opt/cli.py viewer --run <name> --overwrite
open reports/<name>/trace_viewer.html
```

Features:

- **Waterfall tree with timing** — each trace renders as an indented node tree
  (turn → tool calls → results) with duration bars on a shared time axis (from
  per-message `timestamp`), per-turn cost, and caret **collapse of subtrees**.
  Bars are dominated by LLM turn latency; local-DB tools are ~instant (faithful
  to the data — tau2 retail is a flat half-duplex conversation, not a deep
  multi-agent call graph).
- **Pretty JSON, collapsed by default** — tool-call args and tool results render
  as a native `<details>` JSON tree (objects/arrays collapsed beyond depth 1);
  click a node label to expand its detail.
- **Flaky pass↔fail selector** — sidebar lists tasks with both a passing and a
  failing trial; one click loads the pass into **A**, the fail into **B**, and
  turns on diff. (Precomputed in `generate.py`; 18 pairs on the baseline.)
- **Cluster browser** grouped by failure taxonomy; assign any member to **A**/**B**
  (open-cluster state persists across selections).
- **Unified explorer**: pin a second trace in-place — no separate page. Compare
  mode shows two waterfalls side by side.
- **Synchronized diff toggle**: semantic LCS alignment over step `key`s
  (value-free tokens: `C:<tool>`, `R:<tool>[:e]`, `A:text`, `U:text`) — so it's
  tool-aware, not raw-text. Rendered as a two-column table (locked scroll);
  word-level inline highlighting on replaced text turns; JSON payloads shown as
  pretty trees; "hide equal" collapses unchanged runs.

Node payload (depth + timing + content) is built by `generate.py::_steps_for_sim`
/ `_add_timing`; flaky pairs and per-sim `total_dur` are added in `build_payload`.

## Pages

| Page | Agent | Data sources | Priority |
|------|-------|--------------|----------|
| **RunOverview** | P1-Shell | `manifest.json`, `task_summary.csv` | P0 |
| **RunComparison** | P1-VizCore | two runs' `task_summary.csv` | P0 — delta chart |
| **Clusters** | P1-VizCore | `clusters.json`, `cluster_labels.json` | P0 — treemap |
| **TraceExplorer** | P1-Traces | `features.json`, simulation paths | P1 — timeline |
| **ClusterGallery** | P1-Traces | rep sim ids → load trajectories | P1 |
| **Proposals** | P1-Actions | stub; wired in Phase 2 | P2 |

## Viz build order

1. Run comparison delta chart (pass/fail flips)
2. Failure mode treemap
3. Tool-call timeline swimlane
4. Cluster gallery (3 reps per cluster)
5. Task × trial heatmap
6. Side-by-side trajectory diff
7. Cost/steps scatter (stretch)

## Agent briefs

### P1-Shell

- **Owns:** `dashboard/app.py`, `dashboard/state.py`, run selector
- **Reads:** `reports/*/manifest.json`
- **Must NOT:** duplicate analysis logic

### P1-VizCore

- **Owns:** `dashboard/components/metrics.py`, `dashboard/components/clusters.py`
- **Reads:** `task_summary.csv`, `clusters.json`, `cluster_labels.json`
- **Uses:** plotly

### P1-Traces

- **Owns:** `dashboard/components/traces.py`
- **Reads:** `features.json`, paths from `manifest.simulation_path`

### P1-Actions

- **Owns:** `dashboard/components/actions.py`
- **Calls:** `uv run python tools/harness-opt/cli.py analyze ...`

## Acceptance criteria

- Select any run with a `manifest.json` and view pass rate + cluster list
- Compare baseline vs candidate with task-level flip highlighting
- Click cluster → see gallery of representative traces
- "Re-analyze" button runs `cli.py analyze` subprocess and refreshes
