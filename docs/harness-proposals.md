# Harness Improvement Proposals — Retail

> Agent-side harness proposals for τ2-bench **retail**, derived from trace
> analysis of the `gpt-5.5 / gpt-5.5` baseline. **No eval has been run on these
> yet** — this document is the "propose" step. Each proposal names the failure
> cluster it targets, the exact change, the tasks it should move, and its risk.
>
> Constraints honored (see [northstar](grounded-intelligence-northstar.md)):
> agent-side only (`src/tau2/agent/llm_agent.py` prompts + optional new agent).
> No changes to tasks, scorer, tools, user simulator, or `policy.md`.

## Baseline under analysis

Run: `data/simulations/baseline-gpt55-t2` (agent+user = `gpt-5.5`, 2 trials, 114 tasks).

| Metric | Value |
|--------|-------|
| Sim-level pass | **192 / 228 = 84.2%** |
| pass^2 (both trials pass) | **87 / 114 = 76.3%** |
| pass@1 (any trial passes) | **105 / 114 = 92.1%** |
| Avg sim reward | 0.842 |
| Termination reasons | 228 / 228 `user_stop` (no premature termination, no max-error) |

**Failure decomposition (36 failing sims):** 31 DB mismatches, 5 NL-assertion
misses. Zero terminations, zero tool/JSON errors. Per the northstar, DB is the
gate — so proposals target DB correctness first.

## Failure taxonomy (grounded in traces)

| # | Cluster | Failing sims | Tasks | Mechanism |
|---|---------|--------------|-------|-----------|
| C1 | **Premature `transfer_to_human_agents`** | **15 / 36** | 19, 27, 28, 30, 31, 32, 36, 37, 46, 67, 68, 78 | Agent transfers (which ends the episode via `###TRANSFER###`) at first friction, abandoning remaining **in-scope** work or refusing a best-effort answer. 12 of these did **zero writes**. |
| C2 | **Cancellation-reason mismatch** | 5 | 38, 66, 88 | Agent presents `"no longer needed"` / `"ordered by mistake"` as a neutral menu; the recorded reason (DB-hashed) ends up wrong. |
| C3 | **Variant/`new_item_id` resolution** | ~5 | 0, 20, 60, 79 | Agent unilaterally picks one matching variant (often mirroring the original item's unspecified options) instead of surfacing choices; picks the wrong `new_item_id`. |
| C4 | **Incomplete multi-step / implied action** | ~6 | 104, 108, 111, 41, 78, 30 | Agent stops after partial completion (user discloses sub-tasks progressively) or answers an informational question without completing the implied write. |
| C5 | NL-assertion misses (noisy, low-priority) | 5 | 46, 67, 68, 105 | DB often fine; LLM judge flags a missing required statement. Overlaps C1. `task 46` is only item-*ordering* (set-equal) — a non-issue for DB. |

Evidence highlights:

- **task 32** (`0.0`, both trials): user wants a lost-tablet refund (out of scope) *then* "cancel the charger… also cancel the boot and kettle, and return the sneaker." Agent transferred on the refund and never did the four in-scope actions.
- **task 27** (both trials): return + exchange on one order. Agent decided it "can only do one" and **transferred**, instead of telling the user and doing the exchange (the user's stated fallback: "you prefer to do the exchange").
- **task 68** (both trials): "how much did I pay for my most recent order?" Agent had all order totals but transferred rather than answering.
- **task 38 / 66**: agent cancelled with `"ordered by mistake"`; gold stores `"no longer needed"`. The user only said "ordered by mistake" because the agent offered it as a menu; the actual situation (can't afford / wants a different product) maps to "no longer needed".
- **task 88** (the tension case): the task *explicitly instructs* the user to say "ordered by mistake" and gold = `"ordered by mistake"`; agent used `"no longer needed"`.
- **task 60**: user said "if several options, the one without water resistance"; agent silently picked the blue variant that mirrored the original's IPX4 rather than surfacing the blue variants → wrong `new_item_id`.
- **task 108**: user asked "how much would I get back?"; agent answered and the user stopped — the required `return_delivered_order_items` never happened because the agent didn't offer to process it.

## Proposals

All proposals are additions to `AGENT_INSTRUCTION` in
`src/tau2/agent/llm_agent.py` unless noted. Recommended implementation: a **new
registered agent** (e.g. `retail_llm_agent`) subclassing `LLMAgent` with the
augmented prompt, so the baseline agent stays byte-identical for a fair A/B.
"One proposal = one branch" per the decision log.

### P1 — Transfer discipline *(targets C1; highest leverage: ~15 sims)*

The policy already says transfer "**if and only if** the request cannot be
handled within the scope of your actions" (`policy.md:24`). The agent violates
this. Add explicit operating rules:

```text
## Finishing the whole request
- The user may reveal requests one at a time. Do not end or transfer until every
  part of what they came for has been handled. Before finishing, ask whether
  there is anything else.
- Transfer to a human ONLY when the entire remaining request is outside your
  tools/policy. If only part of a request is out of scope, clearly decline that
  part and continue with everything you can do. Never transfer while any
  in-scope action remains.
- When a tool/policy limitation blocks the user's preferred option, explain the
  limitation and offer the alternatives you CAN perform; let the user choose. Do
  not transfer on their behalf.
- For informational questions, give your best answer from the data available
  rather than transferring.
```

- **Risk:** 9 *passing* sims transfer legitimately; the wording restricts only
  *premature* transfer (remaining in-scope work / best-effort answers), so
  legitimate end-of-conversation transfers should survive. Verify no regression
  on those 9 in the subset eval.
- **Confidence:** High. Deterministic double-trial failures (27, 32, 68) should
  flip; some (30, 78) also need C3/C4.

### P2 — Cancellation-reason inference, not a menu *(targets C2; ~5 sims)*

```text
## Cancellation reason
- When cancelling a pending order, do not present the two allowed reasons as a
  menu. Ask the user, in their own words, why they want to cancel, then map to
  the closest allowed reason: use "ordered by mistake" only if they indicate the
  order/item was placed in error or by accident; otherwise use "no longer
  needed" (changed mind, cannot afford, wants a different product, etc.).
  Confirm the single mapped reason before cancelling.
```

- **Why it can win all three:** not offering the menu removes the artifact that
  made 38/66's users echo "ordered by mistake" → they'd state their situation →
  "no longer needed" (gold). 88's user proactively says "ordered by mistake"
  regardless → maps to "ordered by mistake" (gold).
- **Risk / caveat:** genuine tension exists — the tasks are inconsistent about
  whether the reason follows the user's words or their situation. Medium
  confidence; expect net-positive, not a guaranteed sweep. Flag in writeup.

### P3 — Surface variant choices before writing *(targets C3; ~5 sims)*

```text
## Choosing item variants
- When modifying or exchanging to a new item, if more than one available variant
  matches everything the user explicitly asked for, list those variants (showing
  the differing options and prices) and ask which one. Do not fill unspecified
  options by copying the original item's values.
```

- **Risk:** adds a clarifying turn on some already-passing tasks; the user
  simulator generally answers, so low regression risk. Confidence: medium.

### P4 — Drive implied actions to completion *(targets C4; ~5 sims)*

```text
- If the user's reason for contacting you implies an action (return, cancel,
  modify, exchange) but they only ask an informational question about it, answer
  it and then proactively offer to carry out the action, confirming before any
  change. Do not passively wait after answering.
```

- **Risk:** must remain "offer + confirm," never auto-write, to preserve the
  policy's confirmation gate. Confidence: medium (task 108 is a clean win;
  progressive-disclosure tasks also need P1).

### Considered and rejected (no trace evidence)

- **JSON / argument-repair retries in `llm_utils.py`** — zero tool/JSON errors
  observed; all 228 sims ended in `user_stop`. Not grounded → skip.
- **Auth-flow prompt reminders** — no authentication failures in any trace; the
  current prompt already handles auth correctly. Not grounded → skip.

## Expected combined impact

Proposals target ~30 of 36 failing sims (heavy overlap between C1 and C4/C3).
Conservatively, flipping the deterministic double-trial failures alone (27, 32,
38, 60, 66, 68 = 12 sims) would move pass^2 from 76.3% toward ~82–86%. Real lift
must be confirmed with a multi-trial subset eval (deferred per instructions),
because the NL judge and user simulator inject noise into ~35% of tasks.

## Next step (not yet executed)

Per the northstar workflow: implement P1 first (biggest lever), build a
per-cluster subset from the failing task IDs, run a targeted subset eval vs
baseline, and only promote to a full `gpt-5.5` run if the subset improves.
