# Dashboard (v3) — current UI

> Source of truth for the harness-opt frontend as it stands today. Supersedes
> the v1 (Streamlit) and v2 (static HTML) writeups in [`README.md`](README.md),
> which are kept only as history.

## What it is

`tools/harness-opt/dashboard_v3/` is a **FastAPI backend + a no-build vanilla
ES-module SPA**. It is a read-mostly consumer of the Phase 0/2 artifacts under
`reports/<run>/`, plus a few POST actions that shell the CLI (`propose`,
`accept`, `reject`). Charts use **Plotly.js** (vendored locally at
`client/vendor/plotly.min.js`; loaded before the module bundle).

Design constraints that still hold:
- **No build step, no framework.** A tiny hyperscript (`client/js/dom.js`: `h()`
  for HTML, `hs()` for SVG) keeps components as plain functions returning DOM.
- **`Cache-Control: no-store`** on every response (dev middleware) so a normal
  reload always gets fresh JS/CSS/data. (Only exception: after the vendored
  Plotly `<script>` changes you need one hard reload.)
- **Server restart is only needed for backend (`.py`) changes.** Client files
  (`client/**`) are served fresh from disk — just reload the tab.
- **Traces are lazy-loaded per sim** (`/sims/{id}`), so no multi-MB payload.

## Run

```bash
uv run python tools/harness-opt/cli.py dashboard        # → http://127.0.0.1:8770
# or: uv run python tools/harness-opt/dashboard_v3/server.py --port 8770
```

## Layout

```
tools/harness-opt/dashboard_v3/
├── data.py          # cached read layer over reports/ (+ raw sims, embedding, proposals)
├── server.py        # FastAPI: JSON API + serves client/ ; no-store middleware
└── client/
    ├── index.html · styles.css · vendor/plotly.min.js
    └── js/
        ├── app.js router.js api.js store.js dom.js
        ├── components/  widgets.js waterfall.js diff.js jsontree.js trace_util.js
        └── pages/       overview.js clusters.js embedding.js traces.js compare.js proposals.js
```

## API

| Endpoint | Returns |
|----------|---------|
| `GET /api/runs` | analyzed runs (manifest summary) |
| `GET /api/runs/{run}/summary` | manifest, pass rate, L0 (mechanism) buckets, clusters (+ mechanism/summary/gloss/signature), flaky pairs, per-sim index |
| `GET /api/runs/{run}/sims/{id}` | lazy trace: nodes (waterfall steps w/ timing), `failure_reason` (golden), signals |
| `GET /api/runs/{run}/tasks` | task_summary rows (compare) |
| `GET /api/runs/{run}/embedding` | PCA-2D centroids + per-sim points + centroid cosine matrix |
| `GET /api/lineages` · `GET /api/runs/{run}/proposals` · `.../proposals/{id}` | Phase 2 feeds |
| `POST /api/runs/{run}/propose` · `.../accept` · `.../reject` | shell the CLI |

## Taxonomy shown in the UI

- **Primary axis = `mechanism`** (deterministic root cause). Vocabulary + colors
  live in `components/widgets.js` (`mechanism()`, `mechanismColor()`,
  `MECH_ORDER`): `bailed_transfer`, `stalled_no_action`, `wrong_params`,
  `incomplete_multitask`, `identification_failure`, `comm_miss`,
  `premature_termination`, `other`, `pass`. Pills are outlined + light-fill.
- **`failure_type`** (db_only / nl_only / mixed — the reward-component symptom
  axis) is **no longer shown as a cluster/trace tag**. It survives only in the
  Compare page's "Failure-mode shift" panel (a deliberate symptom-distribution
  view).
- **`gloss`** (value-free "what changed", e.g. `missing: cancel order, return
  items`) and **`summary`** (prose root-cause description) are complementary to
  mechanism. The cluster views now lead with **`summary`**; gloss/signature are
  demoted/removed from headers.

## Pages

Left-nav order: Overview · Clusters · Embedding · Traces · Compare runs · Proposals.

### Overview
Metric cards (sims, pass rate, failures, trials, clusters, agent LLM); a **Root
cause (mechanism)** breakdown (bars **normalized by total traces**, dark
mechanism fill on a light same-hue track, count · %); and a top-cluster preview
(mechanism-led) linking into Clusters.

### Clusters
- Left: flat list **sorted by count**. Each item shows cluster id, count · % of
  failures, a **mechanism-composition importance bar** (segments colored by
  mechanism, widths ∝ member counts, **normalized by total failing traces**),
  and a 2-line **summary**. No single cluster-level mechanism tag (clusters are
  mechanism-mixed).
- Right (fills viewport height): fixed header = `Cluster <id>` + **summary** +
  member count + **mechanism-composition bar**; then a **sortable + filterable**
  member table (sticky header) — sort by task/trial/reward/mechanism, filter by
  task text and by mechanism; each member row has its own mechanism tag and an
  "open →" into Traces; "Diff first two shown →" respects sort/filter.

### Embedding
"Constructed feature-space" diagnostic (TF-IDF of signal tokens → PCA-2D;
**not** the live partition function). Three Plotly charts: **centroid map**
(bubbles sized by count, colored by mechanism), **sim scatter** (per-sim points,
one trace per mechanism, click → open trace), and a **similarity heatmap**
(centroid cosine; bright off-diagonal = near-duplicate clusters).

### Traces (the workspace)
- Left picker with a **Clusters / Tasks** segmented control + sticky
  filter/header:
  - **Clusters**: each cluster shows id + count · % and a **red-track
    mechanism-composition importance bar**; expanded → summary + members
    (sorted by task, each tagged with its mechanism).
  - **Tasks**: every task with all trials (incl. **passes**), a color-coded
    pass-count status pill (`1/2 passed`), flaky ⚡ badge, an outcome
    **filter (All/Passed/Flaky/Failed)**, and one-click **diff pass↔fail** /
    **diff trial 0↔1**.
- Selection is `+` / `✕` chips (max 2). Main area = **waterfall timing tree**
  (turn → tool calls → results; duration bars; subtree collapse; click a node
  for **pretty JSON collapsed by default**); pin a 2nd trace for side-by-side;
  **Diff** toggle (semantic LCS alignment, synchronized rows, word-level
  highlight) + **Hide equal**; **Failure reason** toggle shows the golden
  evaluator reason (reward breakdown, DB-diff gloss, failed NL-assertion
  justifications).

### Compare runs
Baseline selector, then: **Headline** table with a per-metric colored Δ
(green = improvement / red = regression, direction-aware); **Task outcome flow**
(improved / regressed / still-failing / still-passing); **Failure-mode shift**
(symptom-axis distribution between runs); and an actionable **Regressions** table
(was-pass→now-fail) annotated with **mechanism** pills + "open trace →".

### Proposals (Phase 2 ReviewUI)
- **New proposal** form: cluster dropdown (impact-sorted, truncated summary) that
  renders the **selected cluster's full summary**; coder backend
  (auto/openai/claude/cursor/manual), proposer model (default `gpt-4.1`),
  lineage, and an **eval toggle** with a budget warning.
- **Lineages** catalog + **proposals** table (status/verdict pills) → click a row
  (highlights + scrolls) for detail: coder log (**backend · model · cost**), diff,
  subset-eval table, and **Accept / Reject** actions.

## Conventions for future edits
- Client-only change → reload the tab. Backend change → restart the server.
- Reuse `widgets.js` (`mechanism`, `mechanismColor`, `importanceBar`, `bar`,
  `ftype`, `card`) rather than re-implementing badges/bars.
- Importance bars: **Clusters/Traces normalize by total failures**; **Overview
  normalizes by total traces**.
