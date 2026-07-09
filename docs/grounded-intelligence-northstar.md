# Grounded Intelligence Take-Home — Project Northstar

> **Purpose:** This document is the primary guide for every agent and contributor working in this repo on the Grounded Intelligence take-home. Read it before making changes, running experiments, or writing the final submission.

---

## Mission

**Maximize retail-domain task accuracy on τ2-bench by improving the agent harness** — prompts, policy handling, state tracking, tool validation, retries, routing — while staying inside hard constraints.

Grounded Intelligence cares about two deliverables equally:

1. **Tooling** — Scripts and workflows that make harness optimization *systematic* (trace analysis, failure clustering, rubrics, run comparisons, explore/exploit over harness variants). Fully automated loops are welcome; human-in-the-loop tools that speed up good decisions are equally valuable if you show evidence and explain reasoning.
2. **Intuition** — Taste in reading traces, diagnosing failures, and choosing what to try next. Document tradeoffs and reasoning, not just final scores.

The final benchmark number matters, but **how you got there** is part of the evaluation.

---

## Background: What τ2-bench Is

τ2-bench is a public benchmark for customer-service agents. Each task drops an agent into a support scenario where an **LLM-simulated user** asks for something (return an order, swap an item, update an address). The agent must resolve it by:

- Following a written **domain policy**
- Calling **tools** against a mock backend

A task **passes** only when the agent lands in the correct final state according to the scorer.

### Retail domain specifics

| Item | Value / location |
|------|----------------|
| Domain | `retail` only (scope of this project) |
| Base eval split | **114 tasks** (`train`: 74, `test`: 40 — do not optimize on test) |
| Policy | `data/tau2/domains/retail/policy.md` (read-only for harness — injected into agent prompt, not edited) |
| Tasks | `data/tau2/domains/retail/tasks.json` |
| Tools | `src/tau2/domains/retail/tools.py` |
| Default agent | `llm_agent` (`src/tau2/agent/llm_agent.py`) |

Key retail policy rules the harness must help the agent follow:

- Authenticate user via email or name + zip (even if user gives user id)
- One user per conversation
- Confirm before any DB-mutating action
- One tool call at a time; no message + tool call in same turn
- Transfer to human only when out of scope

### How scoring works (retail)

> **Ground truth is `data/tau2/domains/retail/tasks.json`, not prose docs.** An
> earlier version of this section (and `docs/evaluation.md`, which we do not
> own) claimed retail uses `reward_basis: ["DB", "COMMUNICATE"]`. That is
> **wrong for the current tasks.json.** Always trust the task data over any
> document, including this one.

Actual `reward_basis` distribution across the 114 retail tasks (from
`tasks.json`):

| `reward_basis` | # tasks | Effective gate |
|----------------|---------|----------------|
| `["DB", "NL_ASSERTION"]` | 112 | `DB × NL_ASSERTION` |
| `["DB"]` | 2 | `DB` only |

Of the 112 `DB + NL_ASSERTION` tasks, only **40** actually populate
`nl_assertions`; the other 72 have an empty list, so the NL evaluator returns
`1.0` automatically. Net effect:

- **~74 tasks are effectively DB-only.**
- **~40 tasks are gated by `DB × LLM-judge`.**
- **`COMMUNICATE` never gates any retail task.** `communicate_info` is present
  on ~36 tasks but runs as a **diagnostic only** — a communicate miss costs
  nothing on the scoreboard.

Final reward = **product** of the components in each task's `reward_basis`
(any `0` zeroes the task):

| Component | What fails | Evaluator | Gates retail? |
|-----------|------------|-----------|---------------|
| **DB** | Wrong final database state (hash mismatch, agent- or user-side) | `EnvironmentEvaluator` | **Yes (all tasks)** |
| **NL_ASSERTION** | An `nl_assertions` entry judged false by an LLM (`gpt-4.1`, temp 0; flagged WIP) | `NLAssertionsEvaluator` | **Yes (40 tasks)** |
| **COMMUNICATE** | Required substring not said to user | `CommunicateEvaluator` | No (diagnostic) |
| **ACTION** | Reference tool call not reproduced | `ActionEvaluator` | No (diagnostic; `partial_action_reward`) |

Implications for this project:

- Optimize for **DB correctness first** — it gates every task. Diagnose failures
  as DB mismatches and NL-assertion misses, **not** communicate misses.
- The NL judge is an LLM (`gpt-4.1`), independent of the agent/user model, so it
  injects **nondeterminism into ~35% of tasks** even with an unchanged harness.
  Budget multiple trials before trusting an NL-driven pass/fail delta.

Important nuance (see `docs/evaluation.md`): `evaluation_criteria.actions` is **one reference trajectory**, not the only correct path. The agent passes DB if any tool sequence produces an equivalent end state. **Do not** assume the agent must replay the listed actions exactly. `partial_action_reward` (read/write match rate vs that reference) is a diagnostic hint, never a correctness verdict.

Premature termination (max steps, max errors, etc.) → reward **0** before evaluators run.

---

## Hard Constraints (Do Not Violate)

These are non-negotiable. Violating them invalidates the submission.

| Constraint | Detail |
|------------|--------|
| **Domain** | Retail only |
| **Budget** | **$50** total on the provided API key (all runs + LLM-powered tooling). Reference: full retail run ≈ 6 min, ≈ **$8** with `gpt-5.5` at `--max-concurrency 40`. Text if blocked. |
| **Time** | 24 hours from receiving instructions + API key. Active coding should be a few hours; taste and problem-solving matter more than grind. |
| **Evaluation model** | Final submission evaluated with **`gpt-5.5`** for both agent and user. Report any model differences used during development. |
| **Do not touch** | Benchmark **tasks**, **scorer/evaluator**, **tool behavior**, or **simulated user** |
| **Only change** | **Agent-side harness** (prompts, agent logic, orchestration around the agent, analysis tooling you add) |
| **AI use** | AI assistance is fine; do not delegate the whole project to AI — it will do a bad job on taste and diagnosis |
| **Submission** | Private GitHub repo shared with `krinetic1234` and `connorff`; clean commit history |

### Red lines — files and systems to leave alone

```
data/tau2/domains/retail/tasks.json          # task definitions
data/tau2/domains/retail/db.json             # backend state
src/tau2/domains/retail/tools.py             # tool behavior
src/tau2/evaluator/                          # scoring logic
src/tau2/user/                               # user simulator
```

Policy text (`policy.md`) is domain data the agent sees; the take-home says not to change benchmark tasks/scorer/tools/user. Treat **policy.md** as fixed domain input unless you have explicit approval — harness changes should adapt *to* the policy, not rewrite it.

---

## Green Lines — What You May Change

Focus harness work here:

| Area | Primary files | Examples of improvements |
|------|---------------|--------------------------|
| **Agent prompts** | `src/tau2/agent/llm_agent.py` (`AGENT_INSTRUCTION`, `SYSTEM_PROMPT`) | Auth flow reminders, confirmation discipline, tool-call formatting |
| **Custom agents** | New agent under `src/tau2/agent/`, register in `src/tau2/registry.py` | ReAct-style reasoning, pre-flight tool validation, structured state |
| **LLM call wrapper** | `src/tau2/utils/llm_utils.py` | Retries on malformed JSON, argument repair |
| **Orchestrator (agent path)** | `src/tau2/orchestrator/orchestrator.py` | Agent-side error recovery, step limits (careful — affects fairness if asymmetric) |
| **Runner / batch** | `src/tau2/runner/` | Experiment harness, variant sweeps, checkpointing |
| **Analysis tooling** | `scripts/`, `src/tau2/scripts/`, new `src/experiments/` | Failure clustering, trace diff, cost tracking |

Default agent system prompt structure today:

```text
<instructions>{AGENT_INSTRUCTION}</instructions>
<policy>{domain_policy}</policy>
```

Any harness change should tie back to **observed failure modes** in traces, not speculation.

---

## Success Criteria

### Quantitative

- **Baseline** — Document accuracy on retail `base` split before changes (multiple trials; single trial is noisy).
- **Final** — Same setup after harness improvements.
- **Confidence** — Explain how much improvement is signal vs noise (trial count, task-level stability, cost).

### Qualitative (required in final writeup)

- Failure mode analysis with trace evidence
- Per-change rationale linked to failures
- What did not work and why
- Cost breakdown (runs + tooling → total)
- AI assistance disclosure
- What you would try next with more time/budget

---

## Recommended Workflow

### Phase 0 — Setup and smoke test

```bash
export OPENAI_API_KEY="provided-separately"

git clone https://github.com/sierra-research/tau2-bench
cd tau2-bench
uv sync
cp .env.example .env
uv run tau2 check-data
```

Smoke test (5 tasks):

```bash
uv run tau2 run --domain retail \
  --agent-llm gpt-5.5 --user-llm gpt-5.5 \
  --num-trials 1 --num-tasks 5
```

### Phase 1 — Baseline (budget: ~$8–16)

Run **multiple trials** on the full base split:

```bash
uv run tau2 run --domain retail \
  --task-split-name base \
  --agent-llm gpt-5.5 --user-llm gpt-5.5 \
  --num-trials 2 \
  --max-concurrency 40 \
  --save-to baseline-gpt55-t2
```

Results → `data/simulations/`. Inspect with:

```bash
uv run tau2 view
uv run python src/tau2/scripts/per_task_summary.py --domain retail <path-to-results>
```

Record: overall accuracy, per-task rewards, DB vs NL-assertion failures, termination reasons, **reported cost**.

### Phase 2 — Diagnose (mostly free)

Cluster failures before coding:

1. **DB failures** (gates every task) — Wrong tool args? Skipped confirmation? Wrong item/order id? Auth skipped?
2. **NL-assertion failures** (gates ~40 tasks) — DB is right but the LLM judge says a required `nl_assertions` statement was not made. Read the `justification`, but corroborate across trials — the judge is an LLM and can flip.
3. **Termination failures** — Max steps, max errors, agent stop issues?
4. **Tool errors** — Invalid JSON, wrong schema, multiple tool calls?

> Note: `COMMUNICATE` and `ACTION` checks are populated as **diagnostics** but
> do **not** gate retail rewards. Use them as hints, not as pass/fail signals.

Build or use tooling to make this repeatable. Existing starting points:

- `src/tau2/scripts/per_task_summary.py` — per-task reward tables
- `src/tau2/scripts/evaluate_trajectories.py` — re-evaluate saved runs
- `src/tau2/scripts/view_simulations.py` — trajectory browser

Aim for **failure taxonomy + frequency** before implementing fixes.

### Phase 3 — Hypothesize and implement (agent harness only)

For each change:

1. State the failure cluster it targets
2. Implement the smallest harness change that addresses it
3. Run a **targeted subset** of failing task IDs first (cheap)
4. Run full eval only when subset improves

Prefer changes that generalize across tasks over per-task hacks.

### Phase 4 — Final comparison

Mirror baseline settings (same model, split, concurrency, trial count):

```bash
uv run tau2 run --domain retail \
  --task-split-name base \
  --agent-llm gpt-5.5 --user-llm gpt-5.5 \
  --num-trials 2 \
  --max-concurrency 40 \
  --save-to final-gpt55-t2
```

Compare with tooling (not eyeballing JSON): task-level pass/fail deltas, component rewards, cost.

### Phase 5 — Writeup

Produce `writeup.md` (1–2 pages) at repo root for submission. Use the template in [Final deliverable: writeup.md](#final-deliverable-writeupmd) below.

---

## Budget Planning

| Activity | Approx. cost | Notes |
|----------|--------------|-------|
| Full base run (114 tasks, 1 trial) | ~$8 | `gpt-5.5`, concurrency 40 |
| Baseline 2 trials | ~$16 | Required for noise estimate |
| Final 2 trials | ~$16 | Same |
| Targeted debugging (5–20 tasks × many iter) | $5–15 | Keep tight; use failing task IDs |
| LLM-assisted trace labeling | variable | Count toward $50 cap |
| **Headroom** | ~$3–13 | Reserve for surprises |

**Rules:** Track cumulative spend from `tau2` run cost reports. Use cheaper models for development; confirm gains on `gpt-5.5`. Stop exploratory runs when marginal insight is low.

---

## Tooling Ideas (Build What Helps You Think)

Grounded Intelligence explicitly wants evidence of systematic optimization. Consider building:

| Tool | Purpose |
|------|---------|
| **Failure clusterer** | Group tasks by failure type (DB hash mismatch, NL-assertion miss, termination). NL-assertion checks emitted by the scorer are fair input for offline clustering. |
| **Trace diff viewer** | Baseline vs final trajectories for same task_id |
| **Component breakdown** | % failures from DB vs NL-assertion vs termination (COMMUNICATE/ACTION are non-gating diagnostics) |
| **Harness variant runner** | CLI to sweep prompt variants with `--save-to` naming convention |
| **Task regression set** | Frozen list of previously failing IDs for fast iteration |
| **Cost ledger** | Parse simulation metadata → running total toward $50 |
| **Rubric / LLM judge** | Optional: label trace quality for prioritization (not for changing scorer) |

Automated explore/exploit loops are welcome if they respect budget and only modify agent harness.

---

## Decision Principles for Agents

When choosing what to work on next:

1. **Evidence over intuition** — Read traces for the highest-frequency failure mode first.
2. **Tie changes to failures** — Every harness edit should reference a cluster you observed.
3. **Minimize scope** — Smallest diff that tests a hypothesis. No drive-by refactors.
4. **DB before NL-assertion** — DB gates every task and usually reflects wrong actions; NL-assertion misses (DB right, required statement missing) are often fixable with prompt nudges but are LLM-judged and noisier. Prioritize by frequency × fixability. (`COMMUNICATE` is non-gating in retail — don't spend budget chasing it.)
5. **Don't cheat the benchmark** — No task-specific lookup tables, no editing gold trajectories, no user/scorer/tool changes.
6. **Respect noise** — 114 tasks × 1 trial is noisy; don't declare victory on +2 tasks without multiple trials.
7. **Document negatives** — Failed experiments are valuable; include them in the writeup.
8. **Cost-aware iteration** — Subset runs before full runs; cheaper models for screening.

---

## Architecture Quick Reference

```
CLI (tau2 run)
  → runner/batch.py          # concurrency, checkpointing
  → runner/build.py          # wires agent + user + env
  → orchestrator/            # turn loop, tool execution
  → agent/llm_agent.py       # ★ primary harness surface
  → domains/retail/tools.py  # ✗ do not modify
  → user/user_simulator.py   # ✗ do not modify
  → evaluator/               # ✗ do not modify
```

Agent constructor contract: `__init__(self, tools, domain_policy, llm, llm_args)`. New agents need a factory + `registry.register_agent_factory(...)`.

---

## Progress Tracker (update as you work)

Use this section as a living log. Agents should update it after major milestones.

### Baseline

| Field | Value |
|-------|-------|
| Run name (`--save-to`) | _TBD_ |
| Model (agent / user) | gpt-5.5 / gpt-5.5 |
| Trials | _TBD_ |
| Accuracy (pass rate) | _TBD_ |
| DB fail count | _TBD_ |
| NL-assertion fail count (DB-pass only) | _TBD_ |
| Termination fail count | _TBD_ |
| Cost | _TBD_ |

### Top failure modes (from trace analysis)

1. _TBD_
2. _TBD_
3. _TBD_

### Harness changes

| Change | Targets failure mode | Result (subset / full) |
|--------|----------------------|-------------------------|
| _TBD_ | _TBD_ | _TBD_ |

### Final

| Field | Value |
|-------|-------|
| Run name | _TBD_ |
| Accuracy | _TBD_ |
| Δ vs baseline | _TBD_ |
| Confidence | _TBD_ |
| Total spend | _TBD_ |

---

## Final Deliverable: `writeup.md`

At submission, include `writeup.md` (1–2 pages) covering:

1. **Baseline results** and analysis of main failure modes
2. **What you built and changed, and why** — each change tied to observed failures
3. **Final results** vs baseline and confidence given noise
4. **Rough cost breakdown** (runs + tooling → total)
5. **What did not work** and why
6. **AI assistance** — tools used and for what
7. **What you would try next**

Share private repo with: `krinetic1234`, `connorff`.

---

## Related Docs

- [`docs/strategy.md`](strategy.md) — implementation plan, pipeline design, clustering, regression model
- [`docs/decision-log.md`](decision-log.md) — choices made and alternatives considered
- `AGENTS.md` — repo setup, commands, architecture
- `docs/evaluation.md` — scoring semantics (especially `actions` vs DB hash)
- `docs/running_simulations.md` — runner API and CLI patterns
- `src/tau2/agent/AGENTS.md` — agent implementation rules
- `data/tau2/domains/retail/policy.md` — domain policy the agent must follow

---

*Last updated: project start. Keep this document current as the single source of truth for goals, constraints, and progress.*
