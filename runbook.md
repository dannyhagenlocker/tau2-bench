# Runbook — Retail Harness Optimization

How to run everything in this repo: the **tuned agent** (`retail_llm_agent`) and the
**harness-optimization loop** (`tools/harness-opt/`) that produced it.

- [1. Setup](#1-setup)
- [2. Run an evaluation](#2-run-an-evaluation)
- [3. Reproduce the headline result (A/B)](#3-reproduce-the-headline-result-ab)
- [4. The harness-opt optimization loop](#4-the-harness-opt-optimization-loop)
- [5. The dashboard](#5-the-dashboard)
- [6. Tests & linting](#6-tests--linting)
- [7. Reference](#7-reference)

---

## 1. Setup

```bash
# Core + the harness-opt tooling + dev tools
uv sync --extra harness-opt --extra dev

# Verify the install and data
uv run tau2 check-data
```

Copy `.env.example` to `.env` and set the keys you need:


| Key                 | Needed for                                                                              |
| ------------------- | --------------------------------------------------------------------------------------- |
| `OPENAI_API_KEY`    | LLM agent/user (`gpt-*`), cluster labeling (`gpt-4.1-mini`), proposal coder (`gpt-4.1`) |
| `ANTHROPIC_API_KEY` | Only if you point `--agent-llm` / `--user-llm` / review at Claude models                |


The whole harness-opt pipeline (extract, cluster, embed, report) runs offline except
two optional LLM steps: cluster **labeling** and the proposal **coder**. The embedder
is a pure-NumPy `all-MiniLM-L6-v2` forward pass — no torch, no network, no budget.

> **Note on run artifacts.** `data/simulations/`* and `reports/*` are gitignored, so a
> fresh clone has no prior runs. The specific runs named in the writeup
> (`baseline-gpt55-t2`, `cand-gpt55-full-t2`, …) are reproduced by re-running the
> commands below — the run *name* is just whatever you pass to `--save-to`.

---

## 2. Run an evaluation

Evaluations use the standard `tau2 run` CLI. Results are written to
`data/simulations/<save-to>/results.json` and browsable with `tau2 view`.

**Baseline** — the stock agent (`llm_agent`) that everything is compared against:

```bash
uv run tau2 run \
  --domain retail \
  --agent llm_agent \
  --agent-llm gpt-5.5 --user-llm gpt-5.5 \
  --num-trials 2 \
  --save-to baseline-gpt55-t2
```

**Tuned agent** — `retail_llm_agent`, the deliverable of the optimization loop. It is a
thin `LLMAgent` subclass that only swaps the operating-rules prompt, so `llm_agent`
stays byte-identical for a clean A/B:

```bash
uv run tau2 run \
  --domain retail \
  --agent retail_llm_agent \
  --agent-llm gpt-5.5 --user-llm gpt-5.5 \
  --num-trials 2 \
  --save-to cand-gpt55-full-t2
```

Useful flags: `--num-tasks N` (run the first N tasks), `--task-ids 32 68 108`
(specific tasks), `--verbose-logs` (save per-call LLM logs). Browse any run with:

```bash
uv run tau2 view
```

---

## 3. Reproduce the headline result (A/B)

The writeup's claim is `retail_llm_agent` lifts pass² from 76.3% → 89.5% on the full
retail suite (114 tasks × 2 trials, same `gpt-5.5` agent and user).

1. Run the **baseline** and **tuned** commands from §2 (each is a full 114×2 run).
2. Analyze the candidate against the baseline (this also computes the paired flips):

```bash
uv run python tools/harness-opt/cli.py analyze \
  --run cand-gpt55-full-t2 \
  --baseline baseline-gpt55-t2 \
  --method embedding --embedder st
```

1. Open the **dashboard → Compare** page (§5) and select
  `cand-gpt55-full-t2` vs `baseline-gpt55-t2` for the side-by-side pass²/pass@1
   numbers, task-outcome flow, and per-failure-mode shift.

A full 114×2 `gpt-5.5` run is ~$33–36. To sanity-check the pipeline cheaply, run a few
tasks against a smaller model first, e.g. `--num-tasks 5 --agent-llm gpt-5.4-mini`.

---

## 4. The harness-opt optimization loop

One generation = one trip around the loop below. All commands are subcommands of
`tools/harness-opt/cli.py`. Artifacts for a run land in `reports/<run>/` (gitignored,
immutable per run). Two steps are human-gated by design: **starting a rollout** and
**accepting/rejecting a proposal**.

```
1 Rollout ──▶ 2 Analyze ──▶ 3 Review & propose ──▶ 4 Accept? ──▶ 5 Merge ──▶ (next gen)
 (tau2 run)   (analyze)      (dashboard/propose)     (accept)     (lineage)
                                    ▲                    │
                                    └──── reject ────────┘
```

### Step 1 — Rollout

Produce an immutable `results.json` (see §2). This is the only step that spends eval
budget, so a human triggers it. Use full 114×2 runs at generation boundaries and cheap
subset runs while iterating.

### Step 2 — Analyze (extract → cluster → label → report)

One automatic pass that reads **traces only** (no harness code, no `tasks.json`) to
avoid hindsight bias:

```bash
uv run python tools/harness-opt/cli.py analyze \
  --run baseline-gpt55-t2 \
  --baseline baseline-gpt55-t2 \
  --method embedding --embedder st \
  --mock-label            # omit --mock-label to use real LLM cluster labels
```

This chains: `extract_features.py` → `cluster.py` → `label_clusters.py` →
`generate_report.py` → static viewer, writing `features.json`, `clusters.json`,
`cluster_labels.json`, `task_summary.csv`, `analysis_summary.md`, and `manifest.json`
into `reports/<run>/`.

Optional clustering diagnostics:

```bash
uv run python tools/harness-opt/cli.py cluster-compare --run baseline-gpt55-t2  # signature vs embedding (ARI)
uv run python tools/harness-opt/cli.py cluster-sweep   --run baseline-gpt55-t2  # embedder × threshold sweep (silhouette)
```

### Step 2b — Build the frozen regression oracle

A stable global oracle (passes that must not regress). Build it once per baseline:

```bash
uv run python tools/harness-opt/cli.py build-subset --run baseline-gpt55-t2 --mode oracle
```

### Step 3 — Review & propose

Review the clusters in the dashboard (§5), pick the highest-leverage failure mode, then
auto-code an isolated harness edit. `propose` forks a `proposal/<id>` branch off the
current lineage tip in a dedicated worktree (`.harness-opt-worktrees/`) and runs a
self-contained coder that emits allowlisted `{path, old_string, new_string}` edits:

```bash
# Build the per-cluster subset (oracle controls + the cluster's failing tasks)
uv run python tools/harness-opt/cli.py build-subset \
  --run baseline-gpt55-t2 --mode cluster --cluster c_000

# Propose an edit for that cluster (add --eval to run the subset eval immediately)
uv run python tools/harness-opt/cli.py propose \
  --run baseline-gpt55-t2 --cluster c_000 --coder auto
```

Run (or re-run) the subset eval for a proposal — ~10× cheaper than a full run, gates on
"no control regressions + net cluster improvement":

```bash
uv run python tools/harness-opt/cli.py eval-subset  --run baseline-gpt55-t2 --proposal <proposal-id>
# or, for an existing proposal:
uv run python tools/harness-opt/cli.py eval-proposal --run baseline-gpt55-t2 --proposal <proposal-id>
```

### Step 4 — Accept / reject

Subset noise is too high to auto-merge, so a human decides:

```bash
uv run python tools/harness-opt/cli.py list-proposals --run baseline-gpt55-t2
uv run python tools/harness-opt/cli.py accept --run baseline-gpt55-t2 --proposal <proposal-id>
uv run python tools/harness-opt/cli.py reject --run baseline-gpt55-t2 --proposal <proposal-id>
```

### Step 5 — Merge

**Accept** squash-commits the proposal onto its `lineage/<id>` branch, advancing the
lineage by one commit; the next generation runs from the new tip. The accepted rules
that make up the shipped agent live in
`[src/tau2/agent/retail_llm_agent.py](src/tau2/agent/retail_llm_agent.py)`.

---

## 5. The dashboard

The human surface for steps 3–4 (browse clusters, inspect traces, compare runs, create
and review proposals):

```bash
uv run python tools/harness-opt/cli.py dashboard --port 8770
# then open http://127.0.0.1:8770
```

Pages: **Overview** (headline metrics + root-cause mechanism breakdown), **Clusters**
(drill into a failure mode + per-trace tool chains), **Embedding** (cluster geometry),
**Traces** (side-by-side swimlane timelines + message diff), **Compare** (candidate vs
baseline flow used in §3), **Proposals** (create/eval/accept/reject).

There is also a static, no-server HTML trace viewer per run:

```bash
uv run python tools/harness-opt/cli.py viewer --run baseline-gpt55-t2
# writes reports/baseline-gpt55-t2/trace_viewer.html
```

---

## 6. Tests & linting

```bash
# Harness-opt pipeline tests
uv run pytest tools/harness-opt/tests -v

# Core tau2 tests
make test

# Lint + format (same as the pre-commit hook) — run before committing
make check-all
```

---

## 7. Reference


| Command                                                             | What it does                                  |
| ------------------------------------------------------------------- | --------------------------------------------- |
| `tau2 run --agent {llm_agent,retail_llm_agent} ...`                 | Rollout; writes `data/simulations/<save-to>/` |
| `tau2 view`                                                         | Browse simulation results                     |
| `cli.py analyze --run R --baseline B [--method embedding]`          | Full analysis pass → `reports/R/`             |
| `cli.py cluster / cluster-compare / cluster-sweep`                  | Clustering + diagnostics                      |
| `cli.py build-subset --run R --mode {oracle,cluster} [--cluster C]` | Frozen oracle or per-cluster subset           |
| `cli.py dashboard --port 8770`                                      | Launch the review dashboard                   |
| `cli.py propose --run R --cluster C [--eval]`                       | Auto-code a lineage-isolated proposal         |
| `cli.py eval-subset / eval-proposal --run R --proposal P`           | Gate a proposal on the subset eval            |
| `cli.py list-proposals / accept / reject / delete-proposal`         | Manage proposals & lineage                    |


Run any subcommand with `--help` for its full options. Deeper design docs:
`[tools/harness-opt/README.md](tools/harness-opt/README.md)`,
`[docs/phases/](docs/phases/)`, and `[docs/strategy.md](docs/strategy.md)`.