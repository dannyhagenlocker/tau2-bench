# Agent Boundaries — Harness-Opt

Rules for parallel subagents implementing harness-opt phases.

## Golden rules

1. **Contract-first:** No agent changes another agent's output schema. Propose changes in `docs/phases/contracts/` first.
2. **Immutable outputs:** Never overwrite `reports/<run>/` or `data/simulations/<run>/`.
3. **Trace-only analysis:** P0-Ingest, P0-Cluster, P0-Label must not read harness source, `tasks.json`, or `policy.md`.
4. **Read-only dashboard:** Phase 1 agents consume artifacts; they do not reimplement analysis logic.
5. **One failure mode per proposal:** Phase 2 proposals target a single cluster / failure mode.

## Phase 0 ownership

| Agent ID | Owns (write) | Reads | Must NOT touch |
|----------|--------------|-------|----------------|
| **P0-Contracts** | `tools/harness-opt/contracts/`, `lib/io.py`, `lib/paths.py`, `fixtures/` | τ2 models | `scripts/`, clustering logic |
| **P0-Ingest** | `lib/trace_parser.py`, `scripts/extract_features.py` | `Results`, contracts | clustering, subset, CLI orchestration |
| **P0-Cluster** | `lib/clustering.py`, `scripts/cluster.py` | `features.json` | LLM, subset, trace_parser internals |
| **P0-Label** | `scripts/label_clusters.py` | `clusters.json`, `features.json` | harness code, clustering algo |
| **P0-Subset** | `scripts/build_subset.py`, `scripts/eval_subset.py` | `clusters.json`, `task_summary.csv`, oracle | clustering internals |
| **P0-Orchestrate** | `cli.py`, `scripts/generate_report.py`, `tests/` | all artifacts | other agents' core logic |

### Dependency order

```
P0-Contracts
    ├── P0-Ingest ──► P0-Cluster ──► P0-Label
    └── P0-Orchestrate (skeleton)
P0-Cluster + task_summary ──► P0-Subset
All ──► P0-Orchestrate (wire analyze)
```

## Phase 1 ownership

| Agent ID | Owns | Reads only |
|----------|------|------------|
| **P1-Shell** | `dashboard/app.py`, navigation | `manifest.json` |
| **P1-VizCore** | `dashboard/components/metrics.py` | `task_summary.csv`, `clusters.json` |
| **P1-Traces** | `dashboard/components/traces.py` | `features.json`, simulation paths |
| **P1-Actions** | subprocess hooks to `cli.py` | N/A |

## Phase 2 ownership

| Agent ID | Owns | Boundary |
|----------|------|----------|
| **P2-Propose** | `scripts/propose.py`, `proposals/<id>/*` | May edit `src/tau2/agent/**` on proposal branch only |
| **P2-EvalHook** | calls `eval_subset.py` | writes `subset_results.json` only |
| **P2-ReviewUI** | `dashboard/pages/proposals.py` | writes `proposal_status.json` |
| **P2-Git** | merge scripts | git only |

## Phase 3 ownership

| Agent ID | Owns |
|----------|------|
| **P3-Harness** | harness changes via proposal branches |
| **P3-Stats** | `lib/stats.py`, `scripts/compare_runs.py` |
| **P3-Writeup** | `writeup.md` generator |

## Visibility matrix

| Data | Analysis | Proposal agent | Dashboard | Human |
|------|:--------:|:--------------:|:---------:|:-----:|
| Trajectories | ✓ | ✓ | ✓ | ✓ |
| reward_info | ✓ | ✓ | ✓ | ✓ |
| Harness code | ✗ | ✓ | ✓ | ✓ |
| policy.md | ✗ | ✓ | ✓ | ✓ |
| tasks.json | ✗ | ✗ | optional | ✓ |
