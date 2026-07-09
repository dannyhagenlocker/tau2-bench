# Harness-Opt Phases

Phased implementation plan for `tools/harness-opt/`. Strategy context: [strategy.md](../strategy.md).

## Phase index

| Phase | Status | Doc | Scope |
|-------|--------|-----|-------|
| **0** | Implemented | [phase-0/README.md](phase-0/README.md) · [clustering-engine.md](phase-0/clustering-engine.md) | Scripts, contracts, CLI, tests, clustering engine |
| **1** | Implemented (v3) | [phase-1/dashboard.md](phase-1/dashboard.md) | Dashboard (FastAPI + SPA); [README](phase-1/README.md) = history |
| **2** | Implemented (CLI + ReviewUI) | [phase-2/README.md](phase-2/README.md) | Proposal pipeline; ReviewUI = v3 Proposals page |
| **3** | Docs only | [phase-3/README.md](phase-3/README.md) | Generations, stats, writeup |

Contracts (all phases): [contracts/README.md](contracts/README.md)

## Pipeline dependency graph

```mermaid
flowchart TB
  subgraph phase0 [Phase 0]
    Extract[extract_features]
    Cluster[cluster]
    Label[label_clusters]
    Report[generate_report]
    BuildSub[build_subset]
    EvalSub[eval_subset]
  end

  subgraph phase1 [Phase 1]
    Dashboard[Dashboard v3 - FastAPI + SPA]
  end

  subgraph phase2 [Phase 2]
    Propose[propose]
    Review[proposal review]
  end

  subgraph phase3 [Phase 3]
    Compare[compare_runs]
    Writeup[writeup.md]
  end

  SimResults[data/simulations/run] --> Extract
  Extract --> Cluster --> Label --> Report
  Report --> Dashboard
  Cluster --> BuildSub --> EvalSub
  Dashboard --> Propose --> EvalSub --> Review
  Review --> Compare --> Writeup
```

## Quick start (Phase 0)

```bash
uv sync --extra harness-opt --extra dev

# After a tau2 run (--save-to my-run):
uv run python tools/harness-opt/cli.py analyze --run my-run --baseline my-run

# Build frozen oracle (after baseline):
uv run python tools/harness-opt/cli.py build-subset --run my-run --mode oracle
```

## Baseline handoff

When baseline completes (`baseline-gpt55-t2`, 2 trials):

```bash
uv run python tools/harness-opt/cli.py analyze \
  --run baseline-gpt55-t2 \
  --baseline baseline-gpt55-t2

uv run python tools/harness-opt/cli.py build-subset \
  --run baseline-gpt55-t2 --mode oracle
```

Reports land in `reports/baseline-gpt55-t2/` (gitignored).
