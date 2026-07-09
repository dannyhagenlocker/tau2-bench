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
