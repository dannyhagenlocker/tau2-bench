# Harness Optimization Strategy

> **Companion docs:** [Northstar](grounded-intelligence-northstar.md) (constraints & goals) · [Decision log](decision-log.md) (choices & rationale as we go)
>
> **Submission framing:** Headline **"+X% on retail"**, story grounded in **systematic tooling** for harness engineering. 50/50 weight on accuracy vs process/tooling quality.

---

## Executive summary

We will build **`tools/harness-opt/`** — a script-first, dashboard-wrapped pipeline that turns τ2 simulation outputs into **actionable, isolated harness proposals** with evidence. Humans stay in the loop at every stage boundary; only **accept/reject** and **full benchmark runs** require explicit human initiation.

**Core loop (one “generation”):**

```
Full rollout (human-triggered)
    → Analyze & cluster (automatic)
    → Human reviews clusters in dashboard
    → Propose fixes, one failure mode each (automatic)
    → Subset eval per proposal (automatic)
    → Human accepts/rejects in dashboard
    → Merge accepted proposals (one branch/commit each)
    → Next generation
```

**What we are NOT building (documented in [decision-log](decision-log.md)):** fully closed auto-merge loops, bandit variant search, offline trajectory replay, proposal auto-revision until pass, critic-as-separate-agent, cost-tracker gate.

---

## Goals & constraints (recap)

| Dimension | Choice |
|-----------|--------|
| Time split | 50% tooling · 25% trace reading · 25% harness + benchmarks |
| Automation ceiling | **3/5** — agents draft changes; human merges with regression evidence |
| Process priority | Crisp, defensible, systematic — even over aggressive score chasing |
| Audience | Engineer end-user; UI should be intuitive for other humans |
| Budget | ~$50 total; no cost-tracker app, but budget-conscious by design |
| Harness scope | Agent-side only — prompts **and** code (retries, validation, state tracking) |

---

## Chosen architecture

### Design principles

1. **Scripts first, dashboard second** — every stage is a CLI with stable I/O contracts; the web app orchestrates and visualizes, not replaces.
2. **Never overwrite runs** — `data/simulations/<run>/` and `reports/<run>/` are immutable snapshots.
3. **Trace-only analysis** — clustering/attribution sees trajectories + `reward_info`, not harness code or `tasks.json`.
4. **One proposal = one failure mode** — may touch multiple files; tested in isolation on a dedicated subset.
5. **Independence assumption** — failure-mode fixes are treated as composable; document when this breaks.

### Pipeline stages

| Stage | Trigger | Input | Output | Human gate |
|-------|---------|-------|--------|------------|
| **Rollout** | Human | harness git ref, run config | `data/simulations/<run>/` | Start full run |
| **Analyze** | Auto after rollout | simulation results | `reports/<run>/` artifacts | Review clusters |
| **Propose** | Human picks cluster | cluster id, harness ref | `proposals/<id>/` | — |
| **Subset eval** | Auto per proposal | proposal branch, subset spec | `proposals/<id>/subset_results.json` | — |
| **Review** | Human | proposal package | accept / reject | **Accept/reject** |
| **Merge** | Human | accepted proposal | git branch → main | Merge commit |

Out of scope for v1 but noted: **proposal revision loop** (iterate on a proposal until subset passes) — adds complexity; async human edit + re-run is enough for now.

---

## Regression testing model

Two complementary test sets address different questions:

### 1. Global regression oracle (~15–20 tasks)

**Purpose:** “Did we break anything unrelated?”

- Frozen after **baseline** rollout — never changes across generations.
- Composition:
  - **~8–10 stable passes** — tasks that pass in ≥2/2 baseline trials (low flake).
  - **~8–10 representative failures** — span major failure families (not all from one cluster).
- **Gate:** Every accepted proposal must show **zero regressions** on stable passes and must not increase failures on oracle failures beyond baseline (those are allowed to stay failing).

**Cost:** ~15 tasks × 1 trial × ~$0.07/task ≈ **$1 per proposal eval** (order-of-magnitude; tune after first smoke run).

### 2. Per-failure-mode subset (~8–12 tasks)

**Purpose:** “Did we fix *this* failure mode?”

- Built automatically when a cluster is selected for proposal:
  - **~6–8 tasks** from the cluster with highest failure rate in the source run.
  - **~2–4 control tasks** — stable passes from unrelated clusters (sanity check).
- **Gate:** Net improvement on cluster tasks (fewer failures than baseline on same task_ids) **and** no control regressions.

### Subset vs full suite — tradeoff (document in writeup)

| | Subset (~15–20 tasks) | Full base (114 tasks) |
|--|----------------------|----------------------|
| Cost per eval | ~$1–2 | ~$8 |
| Variance | **High** — a swing of ±2 tasks is ±10–13% on subset | Lower — ±2 tasks is ±1.7% |
| Use | Proposal accept/reject | Generation boundaries only |
| Trials | 1 (speed) | 2 (noise reduction) |

**Rule:** Subset results are **necessary but not sufficient** for confidence. Full runs happen only at generation boundaries (after batch of accepts) and for final submission comparison.

### Greedy isolation vs variant sweep

**Question:** Can greedy one-failure-mode-at-a-time match exploring many harness variants?

**Answer:** Often yes for *localized* failures (prompt gap, missing retry, auth ordering), which are the bulk of retail harness issues. It fails when:

- **Interactions** — fix A enables fix B only together (violates independence).
- **Global prompt rewrites** — one change helps cluster 1 but hurts cluster 2 (subset controls catch some of this; full run catches rest).
- **Capacity limits** — context-length / instruction-following ceiling; many small adds accumulate.

**Mitigation without full variant sweep:**

- Global oracle + per-cluster controls limit cross-cluster regressions.
- **Generation full rollouts** reset the picture after compositing accepted fixes.
- If generation N shows cluster X *reappear* after fixing Y, log as **interaction** in decision-log and consider merged proposal (exception to one-mode rule, documented).

Variant sweep (interest 4, feasibility 2) stays in considerations — viable if greedy plateaus after 2 generations.

---

## Clustering & analysis engine

### Layered approach (always run all layers)

```
Layer 0: Deterministic taxonomy (free, reproducible)
    ↓
Layer 1: Structured feature extraction (call graph, policy flags)
    ↓
Layer 2: Embedding similarity (structured text, not raw chat)
    ↓
Layer 3: LLM judge on cluster representatives only (cohesion label)
```

### Layer 0 — Deterministic baseline

Partition every simulation by:

- `reward_info` components: `db_reward`, `communicate_reward`, termination
- `termination_reason` if reward = 0
- **Mixed failure** = own category when both DB and COMMUNICATE fail

Output: `clusters_l0.json` — canonical buckets every other layer refines.

### Layer 1 — Structured features

Per trajectory, extract:

| Feature | Example |
|---------|---------|
| Tool call sequence | `find_user → get_order → modify_order` |
| Policy flags | `auth_before_mutate`, `confirm_before_write`, `single_tool_per_turn` |
| Error count | env tool errors, protocol violations |
| Steps to termination | integer |
| Mutating tools called | list |

Output: `features.json` + optional call-graph fingerprint for clustering.

### Layer 2 — Embeddings (failure-mode signal)

**Do not embed** raw user chit-chat. Embed a **structured summary**:

```text
failure_type=DB | tools=find_user,get_order,modify_pending_order |
flags=auth_ok,confirm_missing | last_error=... | termination=AGENT_STOP
```

This clusters by *mechanism*, not by “customer wanted blue shirt.”

Method: cheap embedding model; HDBSCAN or agglomerative clustering within L0 buckets.

Output: `clusters.json` (flat list with optional `parent` field for tree view).

### Layer 3 — LLM judge (representatives only)

For each cluster, sample 2–3 representatives → one batched LLM call:

- Human-readable cluster name
- Cohesion score (1–5)
- Dynamic blame tags (prompt gap, validation missing, model error, etc.)

Output: `cluster_labels.json` — **frozen** when analysis completes (writeup references this snapshot).

**Non-determinism:** New analysis run = new labels file under new `reports/<run>/`. Old labels are never overwritten.

### Ranking

1. **Frequency** in source run (fail count / trials).
2. **Manual override** in dashboard always wins.
3. Flaky tasks (pass in some trials, fail in others) — rank by **failure rate**, tag as `flaky` in UI.

### Attribution boundary

| Actor | Sees |
|-------|------|
| Analysis engine | Trajectories, `reward_info`, termination, extracted features |
| Analysis engine | **Does NOT see:** harness code, `policy.md`, `tasks.json` |
| Proposal / coder agent | Full codebase + cluster context + example task IDs |
| Human reviewer | Everything in dashboard |

Rationale: trace-only analysis avoids hindsight bias (“obviously the prompt is wrong”); proposal agent does code attribution.

**On critic vs coder:** Skip separate critic agent — coder with cluster summary + example traces + codebase access is sufficient for v1. Critic adds latency and overlapping context.

---

## Proposal format

Each proposal lives in `reports/<run>/proposals/<proposal-id>/`:

| File | Contents |
|------|----------|
| `proposal.md` | LLM summary: failure mode, description, risk, recommendation |
| `diff.patch` | Harness-only changes |
| `metadata.json` | `cluster_id`, example `task_ids`, branch name, parent run |
| `subset_spec.json` | Oracle + cluster task ids |
| `subset_results.json` | Before/after table |
| `subset_results.md` | Human-readable benchmark table |

**Strict rule:** One failure mode per proposal. Multi-file diffs OK if they serve one mode (e.g. prompt + validation hook for “confirm before write”).

**Git:** `proposal/<id>-<short-name>` branch, one commit, merge on accept.

---

## Metrics & confidence

### Primary (optimization target)

- **Task pass rate** on retail `base`, `gpt-5.5` agent + user, reward = 1.0

### Secondary (dashboard + writeup)

| Metric | Why |
|--------|-----|
| DB pass rate / COMMUNICATE pass rate | Tells us *what* to fix |
| Termination rate | Harness stability |
| Mean steps / mean agent cost | Efficiency story (not optimized) |
| Per-task flip table | Baseline vs current |

### Confidence methodology

| When | Method |
|------|--------|
| **Generation comparison** | 2 trials full base; report mean pass rate + Wilson 95% CI |
| **Paired significance** | McNemar on task-level pass/fail across paired runs (same task_ids) |
| **Stable pass** | Pass in ≥2/2 trials → highlight regressions in red |
| **Subset proposals** | Report raw delta only; disclaimer on high variance |

### Regression policy

- **Zero tolerance** on global oracle stable passes.
- Cluster control passes: zero tolerance.
- Net improvement required on cluster target tasks.
- Full-run regressions after merge → revert or document interaction in decision-log.

### Budget allocation (planned)

| Item | Est. cost |
|------|-----------|
| Baseline 2× full | ~$16 |
| Final 2× full | ~$16 |
| ~5–8 proposal subset evals | ~$8–12 |
| Cluster LLM labels + proposal summaries | ~$2–4 |
| Buffer | ~$2–6 |

---

## Visualization & dashboard

### Priority (build order)

1. **Run comparison delta** — task × pass/fail flip baseline → current
2. **Failure mode treemap** — area = frequency
3. **Tool-call timeline** — swimlane per trajectory
4. **Cluster gallery** — 3 rep traces per cluster
5. **Task × trial heatmap**
6. **Side-by-side trajectory diff**
7. **Cost/steps scatter**
8. **Failure label confusion matrix** (stretch)

### Architecture

```
tools/harness-opt/
├── cli.py                 # entry: analyze, propose, eval-subset, serve
├── lib/                   # shared parsing, features, clustering
├── scripts/               # thin wrappers callable independently
│   ├── extract_features.py
│   ├── cluster.py
│   ├── label_clusters.py
│   ├── build_subset.py
│   ├── eval_subset.py
│   └── generate_report.py
└── dashboard/             # Streamlit or similar
    ├── app.py
    └── components/        # heatmap, timeline, proposal review, ...
```

**Data flow:** Scripts write artifacts → dashboard reads artifacts → dashboard triggers scripts via subprocess/CLI.

**Comparison unit:** Primarily **task_id** (did this task flip pass/fail?) with cluster and run as grouping dimensions.

### Report folders (immutable)

```
reports/
└── <run-name>/
    ├── manifest.json           # run metadata, git sha, timestamps
    ├── task_summary.csv
    ├── features.json
    ├── clusters_l0.json
    ├── clusters.json
    ├── cluster_labels.json
    ├── analysis_summary.md     # auto-generated narrative
    └── proposals/
        └── <proposal-id>/...
```

---

## Harness change strategy (failure-driven)

No fixed recipe upfront — proposals follow cluster diagnosis. Expected intervention types:

| Failure signal | Likely harness intervention |
|----------------|----------------------------|
| `confirm_missing` | Prompt + optional pre-mutation guard in custom agent |
| `auth_before_mutate` violated | State tracker; block write tools until auth tool success |
| COMMUNICATE-only fail | Prompt nudge on required phrases; post-action checklist |
| Tool JSON / protocol errors | `llm_utils` retry + repair |
| Max errors / bad args | Pre-flight schema validation before env call |
| Premature stop | Step budget awareness in prompt (careful — weak fix) |

**Harness-level assertions** (agent-side guards derived from traces) are in bounds — e.g. “do not call `cancel_order` until `find_user` succeeded this session.” Not the same as changing the scorer.

Register a **retail-tuned agent** in `registry.py` when changes outgrow `llm_agent` patches.

---

## Implementation plan

### Phase 0 — Foundation (tooling week, ~50% of time)

| # | Deliverable | Done when |
|---|-------------|-----------|
| 0.1 | `tools/harness-opt/` scaffold + `manifest.json` contract | dirs exist, README in tools |
| 0.2 | `extract_features.py` — parse `results.json` → `features.json` | runs on smoke test |
| 0.3 | `cluster.py` — L0 + L1 + L2 | `clusters.json` emitted |
| 0.4 | `label_clusters.py` — L3 representatives | `cluster_labels.json` |
| 0.5 | `task_summary.csv` + `analysis_summary.md` generator | one command |
| 0.6 | `build_subset.py` — oracle + per-cluster specs | JSON specs |
| 0.7 | `eval_subset.py` — run tau2 on subset, diff vs baseline | `subset_results.json` |
| 0.8 | Baseline rollout (2 trials) + first full analysis | `reports/baseline-*/` |

### Phase 1 — Dashboard MVP

| # | Deliverable |
|---|-------------|
| 1.1 | Run selector + task summary table |
| 1.2 | Cluster list + treemap + gallery |
| 1.3 | Trajectory timeline viewer |
| 1.4 | Baseline vs run delta chart |
| 1.5 | “Propose fix” button → triggers propose pipeline |

### Phase 2 — Proposal pipeline

| # | Deliverable |
|---|-------------|
| 2.1 | Coder agent template: cluster → branch → diff |
| 2.2 | Auto subset eval on proposal branch |
| 2.3 | Proposal review page (summary, diff, table, accept/reject) |
| 2.4 | Accept → merge workflow |

### Phase 3 — Generations & harness work (~25% + ~25% time)

| # | Deliverable |
|---|-------------|
| 3.1 | Generation 1: top 2–3 clusters → proposals → accept |
| 3.2 | Full rollout generation 1 |
| 3.3 | Generation 2 if budget allows |
| 3.4 | Final 2-trial full run + McNemar vs baseline |
| 3.5 | `writeup.md` |

### Stretch goals

- Accepted proposal → auto-open GitHub PR
- Cluster tree visualization (if L0/L2 nesting is clean)
- Proposal revision UI (re-run subset after manual edit)

---

## Generation workflow (operational)

```
Generation 0 (baseline)
├── git: main @ harness-v0
├── rollout: baseline-gpt55-t2  (human, 2 trials, full 114)
├── analyze: automatic
└── human: review clusters, pick 2–3 to address

For each selected cluster:
├── propose: automatic → branch proposal/<id>
├── subset eval: automatic
└── human: accept/reject in dashboard

Generation 1
├── merge accepted proposals to main (one commit each)
├── rollout: gen1-gpt55-t2  (human, 2 trials, full 114)
├── analyze → compare vs baseline in dashboard
└── repeat or stop if budget/low marginal gain

Final
├── rollout: final-gpt55-t2
├── stats: McNemar, CI, flip table
└── writeup.md
```

---

## Considered alternatives (not chosen)

| Approach | Why not (for now) |
|----------|-------------------|
| Manual hypothesis queue only | Low automation; doesn’t demo systematic harness engineering |
| Variant sweep / bandit | Cost explodes; hard to attribute; bandit is inexplainable — note for writeup |
| Separate critic agent | Overlaps with coder + good prompting |
| Offline trajectory replay | Hard to validate as proxy; out of scope |
| Proposal auto-revision loop | Async human + re-propose is enough |
| Edit `policy.md` | Benchmark input; harness should adapt to fixed policy |
| `tau2 view` extension only | Parallel UI allows richer comparison UX |
| Automated accept on subset pass | Subset noise too high; human gate required |
| Cost tracker app | Budget-conscious manually; tracker is overhead |

---

## Open questions (resolve during execution)

- [ ] Exact oracle task ids after baseline (depends on flake distribution)
- [ ] Streamlit vs FastAPI+React (default: **Streamlit** for speed)
- [ ] Embedding model choice (local sentence-transformers vs API)
- [ ] Custom agent name and registration path
- [ ] Whether generation 2 fits in $50 after seeing gen 0 costs

Track resolutions in [decision-log.md](decision-log.md).

---

## Implementation phases

Detailed per-phase specs, contracts, and agent boundaries: [`docs/phases/README.md`](phases/README.md).

---

## Success criteria for the tooling itself

The tooling succeeds if a reviewer can:

1. Open the dashboard, pick a run, see **why** tasks failed (clusters + timelines).
2. Open a proposal, see **evidence** (subset table, trace gallery, diff).
3. Understand **what we considered** and **why we chose this process** (this doc + decision log).
4. Re-run `tools/harness-opt/cli.py analyze --run <name>` and reproduce artifacts.

The harness succeeds if final pass rate beats baseline with documented confidence, and every merged change traces to a named failure cluster.
