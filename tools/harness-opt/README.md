# Harness-opt

Systematic harness optimization tooling for the Grounded Intelligence take-home.

## Setup

```bash
uv sync --extra harness-opt --extra dev
```

## Quick start

```bash
# Full analysis after a tau2 run (--save-to my-run):
uv run python tools/harness-opt/cli.py analyze --run my-run --baseline my-run --mock-label

# Build frozen regression oracle (after baseline):
uv run python tools/harness-opt/cli.py build-subset --run my-run --mode oracle

# Per-cluster subset for a proposal:
uv run python tools/harness-opt/cli.py build-subset --run my-run --mode cluster --cluster c_000
```

## Clustering engine

Failures are clustered by the **embedding engine** (default): each failing trace
becomes a text document, embedded with neural `st` (offline all-MiniLM-L6-v2 via
`lib/minilm_numpy.py` — no torch/network needed), then clustered with
agglomerative cosine + an auto-selected distance threshold. Clusters are named
and bucketed by a deterministic **root-cause mechanism** (`bailed_transfer`,
`wrong_params`, `stalled_no_action`, …); the DB/NL `failure_type` is a secondary
attribute. The legacy exact-match engine is `--method signature`.

```bash
# Default (embedding); pick engine / embedder explicitly:
cli.py cluster --run my-run --method embedding --embedder st
cli.py cluster-compare --run my-run    # signature vs embedding agreement (ARI)
cli.py cluster-sweep --run my-run      # embedder × threshold sweep (silhouette)
```

Evaluation artifacts and hand-labeled ground truth live in
`tools/harness-opt/eval/` (`ablation.*.md`, `root_cause_labels.*.json`). Design
detail: [`docs/phases/phase-0/clustering-engine.md`](../../docs/phases/phase-0/clustering-engine.md).

## Baseline handoff

When `baseline-gpt55-t2` completes (2 trials):

```bash
uv run python tools/harness-opt/cli.py analyze \
  --run baseline-gpt55-t2 \
  --baseline baseline-gpt55-t2 \
  --mock-label   # omit for real LLM cluster labels

uv run python tools/harness-opt/cli.py build-subset \
  --run baseline-gpt55-t2 --mode oracle
```

Artifacts: `reports/<run-name>/` (gitignored, immutable per run).

## Tests

```bash
pytest tools/harness-opt/tests -v
```

## Docs

- [docs/phases/README.md](../../docs/phases/README.md) — phased plan & contracts
- [docs/phases/phase-0/README.md](../../docs/phases/phase-0/README.md) — Phase 0 spec
