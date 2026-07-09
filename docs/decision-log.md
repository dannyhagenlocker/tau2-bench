# Decision Log

> Chronological record of strategic and implementation decisions.  
> Strategy overview: [strategy.md](strategy.md) · Constraints: [northstar](grounded-intelligence-northstar.md)

Format: **Date · Decision · Rationale · Alternatives considered**

---

## 2026-07-08 — Project framing

**Decision:** Submission weighted **50/50** accuracy vs tooling/process. Headline is "+X% retail"; narrative centers reusable harness-optimization tooling.

**Rationale:** Matches Grounded Intelligence’s explicit ask for both tooling and intuition.

**Alternatives:** Accuracy-first (70/30) or tooling-first (30/70).

---

## 2026-07-08 — Time allocation

**Decision:** 50% tooling · 25% trace analysis · 25% harness changes + benchmarks.

**Rationale:** User preference; tooling is the differentiator for the story.

---

## 2026-07-08 — Automation model

**Decision:** Automation level **3/5**. Pipeline stages run automatically; **human gates** between stages. Only **accept/reject** and **full benchmark rollouts** require explicit human initiation.

**Rationale:** Balances systematic throughput with taste; bad auto-merges would waste budget and corrupt harness.

**Alternatives:** Fully manual (level 1); auto-merge on subset pass (level 5) — rejected due to subset noise.

---

## 2026-07-08 — Proposal granularity & git workflow

**Decision:** **One proposal = one failure mode** (multi-file OK). Each proposal gets its own **branch + commit**. Independence of failure-mode fixes is an explicit assumption.

**Rationale:** Isolated attribution in writeup; subset eval stays interpretable.

**Alternatives:** Batched “fix packs” — rejected for muddy causality.

**Risk:** Interaction effects between modes — mitigated by global oracle, generation full runs, interaction notes in this log.

---

## 2026-07-08 — Subset vs full eval

**Decision:** Proposals validated on **small subset only** (~15–20 tasks). Full 114-task × 2-trial runs at **generation boundaries** only.

**Rationale:** ~10× cheaper per proposal; user accepts noise tradeoff with documentation.

**Tradeoff:** Subset ±2 tasks ≈ ±10–13% swing; full suite ±2 ≈ ±1.7%. Subset is screening, not proof.

---

## 2026-07-08 — Regression testing: dual oracle

**Decision:** Two test sets per proposal:

1. **Global regression oracle** (~15–20 tasks, frozen after baseline) — stable passes must not regress.
2. **Per-failure-mode subset** (~8–12 tasks from cluster + controls) — must show net improvement on cluster tasks.

**Rationale:** User asked how oracle pairs with per-mode sets; dual gate separates “fixed target” from “didn’t break unrelated.”

**Alternatives:** Single subset — insufficient cross-cluster regression signal.

---

## 2026-07-08 — Greedy isolation vs variant sweep

**Decision:** **Greedy one-failure-mode-at-a-time** with generation rollouts. No variant sweep in v1.

**Rationale:** Variant sweep (interest 4, feasibility 2) risks cost explosion and weak attribution. Greedy + oracle + full generations approximates sweep for localized failures.

**Alternatives:** Bandit over prompt variants — deferred; document in writeup as considered.

**When to revisit:** Plateau after gen 1 full run or interaction effects in decision log.

---

## 2026-07-08 — Critic agent

**Decision:** **No separate critic agent.** Coder agent gets codebase + cluster context + example traces.

**Rationale:** User skepticism; critic duplicates coder context with extra LLM cost.

**Alternatives:** Critic-before-coder pipeline — rejected for v1.

---

## 2026-07-08 — Analysis engine visibility

**Decision:** Analysis is **trace-only** — trajectories, `reward_info`, extracted features. No harness code, no `tasks.json`, no `policy.md`.

**Rationale:** Avoid hindsight bias in clustering; code attribution belongs to proposal stage.

| Stage | Trajectories | reward_info | harness code | policy.md | tasks.json |
|-------|:------------:|:-----------:|:------------:|:---------:|:----------:|
| Analysis | ✓ | ✓ | ✗ | ✗ | ✗ |
| Proposal agent | ✓ | ✓ | ✓ | ✓ | ✗ |
| Human (dashboard) | ✓ | ✓ | ✓ | ✓ | optional |

---

## 2026-07-08 — Clustering stack

**Decision:** Four layers — L0 deterministic, L1 structured features, L2 structured embeddings, L3 LLM labels on representatives only.

**Rationale:** Reproducible baseline + semantic grouping without embedding irrelevant item semantics.

**Alternatives:** LLM label every trace — too expensive. Embeddings on raw chat — clusters on product names not failure modes.

---

## 2026-07-08 — Ranking

**Decision:** Rank clusters by **frequency**; **manual override** in dashboard always wins. No fix-difficulty estimation.

**Rationale:** User preference; simplicity.

**Flaky tasks:** Tagged by cross-trial failure rate; not a separate priority tier.

---

## 2026-07-08 — Mixed failures

**Decision:** DB + COMMUNICATE failures are a **distinct cluster category** in L0.

**Rationale:** User input; fixes may differ from single-component failures.

---

## 2026-07-08 — Implementation shape

**Decision:** `tools/harness-opt/` — scripts first with stable artifacts, then Streamlit dashboard. Never overwrite prior runs/reports.

**Rationale:** User priority on script contracts; dashboard for engineer UX.

**Alternatives:** Notebook-first; extend `tau2 view` — parallel UI chosen for comparison features.

**Orchestration:** Single `cli.py` entry point wrapping scripts (decided by implementer).

---

## 2026-07-08 — Metrics & confidence

**Decision:**

- **Primary:** task pass rate (gpt-5.5, base split)
- **Confidence:** 2 trials at generation boundaries; Wilson CI + McNemar paired test; stable-pass regression highlights
- **Secondary (reporting):** DB/COMMUNICATE split, terminations, cost/steps — not optimization objectives

**Rationale:** Standard benchmark practice within budget; McNemar gives paired significance for submission.

**Regression tolerance:** Zero on oracle stable passes; case-by-case on full-run flips with revert option.

---

## 2026-07-08 — Harness intervention scope

**Decision:** Beyond prompts — agent-side code (retries, validation, state tracking, harness assertions) is fair game and expected.

**Rationale:** User view: prompt-only is DSPy territory; real harness engineering includes control flow.

**policy.md:** Do not edit (benchmark input). Policy handling = presentation in agent harness.

---

## 2026-07-08 — Out of scope (explicit)

| Item | Reason |
|------|--------|
| Offline trajectory replay | Hard to validate proxy |
| Proposal auto-revision until pass | Complexity; async human OK |
| Bandit variant search | Inexplainable; costly |
| Cost tracker app | Budget-conscious manually |
| Separate critic agent | Redundant with coder |
| Edit tasks/scorer/tools/user | Take-home red line |

---

## 2026-07-08 — Generation model

**Decision:** Discrete **generations** — full rollout → analyze → propose batch → accept → merge → next generation.

**Rationale:** User preference over continuous micro-loop; full runs reset compositional uncertainty.

**Deferred:** In-proposal revision loop until subset passes — note in writeup.

---

## 2026-07-08 — Documentation structure

**Decision:** `docs/strategy.md` (this plan) + `docs/decision-log.md` (ongoing). Northstar remains constraints reference.

---

## 2026-07-08 — Phase 0 implementation complete

**Decision:** Implemented `tools/harness-opt/` with contracts, CLI, scripts, tests, and phase docs (0–3).

**Rationale:** Script-first pipeline per phased plan; dashboard deferred to Phase 1.

**Outcome:** `pytest tools/harness-opt/tests` passes; `cli.py analyze` produces full `reports/<run>/` artifact set.

---

## 2026-07-09 — Phase 2 proposal pipeline: lineage-per-rollout git model

**Decision:** Refined the earlier "per-proposal branch, independent" workflow into a **lineage-per-rollout** model. A pinned base commit roots durable `lineage/<id>` branches; each accepted proposal is **one squashed commit** on the lineage (cumulative — `proposal/<id>` eval branches fork from the current lineage tip, not a fixed base). One git worktree per lineage; per-lineage lockfile serializes `propose`.

**Rationale:** User wants end viewers to browse different loop rollouts as branches, each showing the ordered commit history of accepted proposals that build on each other. Bounds disk (no per-proposal full checkouts) and keeps proposals git-discoverable.

**Alternatives:** Per-proposal worktree (disk blowup, orphaned worktrees); fixed-base independent proposals (rejected — proposals must stack); real branches on the current checkout (rejected — active `dashboard_v2` work must stay untouched).

**Outcome:** Implemented in `lib/lineage.py`, `scripts/propose.py`, `scripts/manage_proposal.py`. Accept advances the lineage by exactly one squashed commit; verified by `tests/test_proposals.py` and an end-to-end `--coder manual` smoke run.

---

## 2026-07-09 — Automated coder via local CLI + subset gating

**Decision:** The harness edit is produced by a **local coding-agent CLI** run headless in the worktree (`lib/coder.py`): Claude Code (`claude -p`) as the primary/default backend, Cursor (`cursor-agent`/`cursor-sdk`) optional, `manual` fallback. Each proposal is gated by a **subset run** vs the generation baseline (no per-proposal full rerun); full re-baseline only at generation boundaries. `--eval` is opt-in to protect the $50 OpenAI budget.

**Rationale:** User has a local coding subagent (Claude/Cursor) and wants option B (automated) plus artifacts recording what was proposed and what happened (`coder_log.json`, `diff.patch`, `proposal.md`). Coder cost is on the local subscription, separate from the benchmark budget.

**Alternatives:** Scaffold-only (no auto-edit); deterministic recipe/template library; full baseline rerun per proposal (rejected — wastes budget).

**Outcome:** Dashboard ReviewUI deferred to `dashboard_v2`; Phase 2 emits `reports/<run>/proposals/index.json` + `reports/lineages/index.json` for it to consume.

---

## 2026-07-09 — Proposal coder is self-contained on the OpenAI key (supersedes Claude-default)

**Decision:** The default proposer backend is now **`openai`** (`OpenAICoder` in `lib/coder.py`): it uses the provided OpenAI key via `tau2.utils.llm_utils.generate` to emit structured `{path, old_string, new_string}` edits, which we validate + apply ourselves. This supersedes the earlier "Claude Code default." `claude`/`cursor` remain opt-in, off-ledger dev conveniences. Proposer defaults to a cheap model (`gpt-4.1`); the change is still evaluated under `gpt-5.5`.

**Rationale:** The assignment scopes the $50 key to "all runs, experiments, and any LLM-powered tooling." Proposal generation is LLM-powered tooling, so it must be self-contained, reproducible from just the key, and counted in the single budget. Coder LLM cost is a rounding error vs eval `tau2 run`s, so this barely affects budget while making the loop reproducible. Cost + model are logged in `coder_log.json`.

**Alternatives:** Local Claude/Cursor CLI as default (rejected — off-ledger, not reproducible, extra provider provenance); OpenAI tool-use agent loop (deferred — more capable but more code/cost; single-shot structured edits fit "smallest change" + human gate).

**Outcome:** Implemented with a precise, northstar-grounded edit **allowlist** (`lib/allowlist.py`): only `src/tau2/agent/llm_agent.py`, `src/tau2/registry.py`, `src/tau2/utils/llm_utils.py`, `src/tau2/orchestrator/orchestrator.py`, and new `*.py` agent modules under `src/tau2/agent/` are editable; Red-line paths are hard-denied; runner/tooling surfaces excluded to shrink the search space. Verified by `tests/test_proposals.py` (allowlist + monkeypatched-`generate` apply tests). Full suite green.

---

## Template for future entries

```
## YYYY-MM-DD — [Short title]

**Decision:** ...

**Rationale:** ...

**Alternatives:** ...

**Outcome:** (fill after implementation)
```

---

## Pending decisions

| Question | Options | Target date |
|----------|---------|-------------|
| Dashboard framework | Streamlit (default) vs FastAPI+React | Phase 1 start |
| Embedding model | local vs API | Phase 0.3 |
| Oracle task ids | derived from baseline | After baseline run |
| Custom agent name | TBD | First harness change |
| Generation 2 budget | proceed if Δ gen1 > X% and spend < $40 | After gen 1 |
