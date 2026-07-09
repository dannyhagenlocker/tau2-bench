# Phase 0 — Foundation Scripts

**Status:** Implemented; tuning ongoing  
**Agents:** P0-Contracts, P0-Ingest, P0-Cluster, P0-Label, P0-Subset, P0-Orchestrate

## Goal

Script-first pipeline from `data/simulations/<run>/` → `reports/<run>/` with typed artifacts. No dashboard in this phase.

> **Deep dive:** [`clustering-engine.md`](clustering-engine.md) — end-to-end
> state of the clustering engine (trace → cluster), known issues, and the open
> roadmap toward a less-bucketed, embedding-based approach. Read that before
> tuning Phase 0.

## CLI commands

| Command | Script | Output |
|---------|--------|--------|
| `harness-opt extract --run NAME` | `extract_features.py` | `features.json` |
| `harness-opt cluster --run NAME [--method embedding\|signature]` | `cluster.py` | `clusters_l0.json`, `clusters.json` |
| `harness-opt label --run NAME [--mock]` | `label_clusters.py` | `cluster_labels.json` |
| `harness-opt report --run NAME [--baseline NAME]` | `generate_report.py` | `manifest.json`, `task_summary.csv`, `analysis_summary.md` |
| `harness-opt analyze --run NAME [--baseline NAME] [--method ...] [--mock-label]` | orchestrates all above | full report dir |
| `harness-opt cluster-compare --run NAME` | `compare_clusterings.py` | `clusters_comparison.{json,md}` |
| `harness-opt cluster-sweep --run NAME` | `sweep_clusterings.py` | `clusters_sweep.{json,md}` |
| `harness-opt build-subset --run NAME --mode oracle` | `build_subset.py` | `oracle.json` |
| `harness-opt build-subset --run NAME --mode cluster --cluster ID` | `build_subset.py` | `proposals/<id>/subset_spec.json` |
| `harness-opt eval-subset --run NAME --proposal ID [--baseline NAME]` | `eval_subset.py` | `subset_results.json` |

Default clustering is the **embedding engine** (`--method embedding`: neural `st`
document embeddings, auto-selected threshold, root-cause mechanism as the primary
axis). `--method signature` is the legacy exact-match engine. See
[`clustering-engine.md`](clustering-engine.md).

Entry point: `uv run python tools/harness-opt/cli.py <command>`

## Agent briefs

### P0-Contracts

- **Owns:** `contracts/models.py`, `lib/io.py`, `lib/paths.py`, `fixtures/smoke_results.json`
- **Acceptance:** Pydantic round-trip on fixtures; `write_artifact` refuses overwrite

### P0-Ingest

- **Owns:** `lib/trace_parser.py`, `scripts/extract_features.py`
- **Input:** `data/simulations/<run>/results.json` (via `Results.load`)
- **Output:** `reports/<run>/features.json`
- **Rules:** Trace-only; use `break_down_metrics.get_write_tools("retail")` for write-tool detection
- **Acceptance:** Smoke fixture produces valid `features.json`; policy flags populated

### P0-Cluster

- **Owns:** `lib/embedding_cluster.py`, `lib/clustering.py`, `lib/minilm_numpy.py`,
  `lib/db_diff.py`, `scripts/cluster.py`
- **Input:** `features.json`
- **Output:** `clusters_l0.json` (layer=l0, bucketed by mechanism),
  `clusters.json` (layer=final, `method=embedding|signature`)
- **Algorithm (current, default `embedding`):** each failing trace → text
  document (core spine + denoised `last_message`) → neural `st` embedding
  (offline MiniLM) → agglomerative cosine clustering with an **auto-selected
  distance threshold** (largest-cluster-share cap 0.45). Clusters are named and
  L0-bucketed by a deterministic **root-cause mechanism** (`classify_mechanism`);
  `failure_type` (db/nl/mixed) is a secondary attribute. `--method signature` is
  the legacy exact-match engine. See [`clustering-engine.md`](clustering-engine.md).
- **Acceptance:** Clusters ranked by failure_rate; deterministic L0; embedding
  membership is not rule-decided

### P0-Label

- **Owns:** `scripts/label_clusters.py`
- **Input:** `clusters.json`, `features.json`
- **Output:** `cluster_labels.json`
- **Rules:** For each cluster, aggregate structured signals over **all** members
  (dominant mechanism, top DB-diff signatures, failed NL assertions, common tool
  chains, escalation rate) + sample ~4 deduped final agent messages → one LLM
  call → concise `summary` (1-2 sentences), `display_name`, `cohesion`,
  `blame_tags`. `--mock` yields a deterministic summary (tests/no-API).
- **Acceptance:** One label per cluster; `summary` is a readable 1-2 sentence
  root-cause description; cohesion 1-5. The dashboard shows `summary` (replaces
  deterministic gloss text).

### P0-Subset

- **Owns:** `scripts/build_subset.py`, `scripts/eval_subset.py`
- **Input:** `task_summary.csv`, `clusters.json`, `oracle.json`
- **Output:** `oracle.json`, `proposals/*/subset_spec.json`, `subset_results.json`
- **Acceptance:** Oracle frozen; eval_subset subprocesses `tau2 run` on task subset

### P0-Orchestrate

- **Owns:** `cli.py`, `scripts/generate_report.py`, `tests/`
- **Acceptance:** `pytest tools/harness-opt/tests` passes; `analyze` on fixture produces full artifact set

## task_summary.csv columns

| Column | Type | Description |
|--------|------|-------------|
| `task_id` | str | Task identifier |
| `trial` | int | Trial index |
| `simulation_id` | str | Unique sim id |
| `reward` | float | Final reward |
| `db_reward` | float | DB component |
| `nl_reward` | float | NL_ASSERTION component |
| `communicate_reward` | float | COMMUNICATE component (diagnostic; non-gating in retail) |
| `mechanism_class` | str | **Primary axis** — root cause: bailed_transfer / wrong_params / incomplete_multitask / stalled_no_action / identification_failure / comm_miss / premature_termination / other |
| `failure_type` | str | Secondary — reward basis: pass / db_only / nl_only / mixed / communicate_only / termination |
| `termination_reason` | str | From SimulationRun |
| `db_diff_signature` | str | P1 abstracted DB divergence (db/mixed failures) |
| `nl_failure_signature` | str | P3 denoised failed-assertion signature (nl/mixed failures) |
| `cluster_id` | str | Assigned cluster (final layer) |
| `agent_cost` | float | Agent LLM cost |
| `num_steps` | int | Message count |

## Baseline handoff

When `baseline-gpt55-t2` completes (2 trials, user-run):

```bash
uv run python tools/harness-opt/cli.py analyze \
  --run baseline-gpt55-t2 \
  --baseline baseline-gpt55-t2

# Omit --mock-label to use LLM cluster labels (small cost, cluster reps only)

uv run python tools/harness-opt/cli.py build-subset \
  --run baseline-gpt55-t2 --mode oracle
```

Output: `reports/baseline-gpt55-t2/` with full artifact set + `oracle.json`.

## Tests

```bash
pytest tools/harness-opt/tests -v
```

Uses `fixtures/smoke_results.json` — no API keys required when `--mock-label`.
