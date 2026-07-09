# Phase 0 — Clustering Engine: Current State

> Living design note. Describes how the failure-clustering engine works **today**
> and how we validated it. Read alongside the code — it points at functions
> rather than repeating them (line numbers are intentionally omitted; they drift).
>
> **Status:** the original 4-layer "L0/L1/L2/L3 signature" plan (see
> [`strategy.md`](../../strategy.md) and the 2026-07-08 "Clustering stack"
> decision) has been **superseded**. The default engine is now
> **embedding-based clustering over a text document, using neural (`st`)
> embeddings, an auto-selected distance threshold, and a deterministic
> *root-cause mechanism* as the primary axis.** The signature engine still
> exists as a selectable, secondary strategy. History is in
> [`docs/decision-log.md`](../../decision-log.md).

---

## 1. Pipeline overview (trace → cluster)

`analyze` is an orchestrator that shells out to stage scripts in sequence; each
reads and writes typed JSON under `reports/<run>/` and only talks to the next
stage through those files (`cli.py::analyze`, `_run_script`). Contracts:
`docs/phases/contracts/*.schema.json`, mirrored as Pydantic in
`contracts/models.py`.

```
data/simulations/<run>/results.json          raw tau2 trajectories (input)
        │  scripts/extract_features.py   → lib/trace_parser.py (+ lib/db_diff.py)
        ▼
reports/<run>/features.json                   one SimulationFeatures record per sim
        │  scripts/cluster.py            → lib/clustering.py | lib/embedding_cluster.py
        ▼
reports/<run>/clusters_l0.json  +  clusters.json   (clusters.json has method=embedding|signature)
        │  scripts/label_clusters.py
        ▼
reports/<run>/cluster_labels.json
        │  scripts/generate_report.py
        ▼
reports/<run>/{manifest.json, task_summary.csv, analysis_summary.md}
```

The **label** stage (`scripts/label_clusters.py`) writes `cluster_labels.json`
with a per-cluster `ClusterLabel` whose `summary` is a concise (1-2 sentence)
LLM description of the shared root cause — read at a glance, and what the
dashboard should render instead of deterministic gloss text. It aggregates the
structured signals over *all* members (mechanism, top DB-diff signatures, failed
NL assertions, tool chains, escalation rate) plus a few sampled final agent
messages into one small LLM call; `--mock` produces a deterministic fallback.
`summary` is an existing contract field (`cluster_labels.schema.json`) — no
schema change.

Auxiliary (evaluation / tuning, not part of `analyze`):

- `scripts/compare_clusterings.py` (`cluster-compare`) — signature vs embedding
  agreement (ARI / homogeneity) → `clusters_comparison.{json,md}`.
- `scripts/sweep_clusterings.py` (`cluster-sweep`) — embedder × scope × algo ×
  threshold sweep with silhouette → `clusters_sweep.{json,md}`.
- `scripts/ablate_document.py` — scores document field-subsets × embedders
  against hand labels → `eval/ablation.<run>.{json,md}`.

Consequence unchanged: **after feature extraction the clustering never re-reads
raw messages.** Every signal must be materialized in Stage 1.

---

## 2. Signal extraction (what each trace becomes)

`trace_parser.py::extract_simulation_features` reduces each sim to one
`SimulationFeatures`. For retail, `extract_features.py::_load_retail_context`
loads the task set + a base `RetailDB` once so the P1 replay doesn't re-parse the
2.7 MB DB per sim.

| Signal | Field(s) | Produced by | Notes |
|--------|----------|-------------|-------|
| **Mechanism (PRIMARY axis)** | `mechanism_class` | `classify_mechanism` | Deterministic root cause; see §4. ~91% vs hand labels |
| Reward-basis taxonomy (secondary) | `failure_type` | `classify_failure` | `pass`/`db_only`/`nl_only`/`mixed`/`communicate_only`/`termination`; retail gates `DB`+`NL_ASSERTION` |
| Reward components | `db_reward`, `nl_reward`, `communicate_reward` | `_reward_components` | From `reward_breakdown` |
| Tool calls | `tool_sequence` | `extract_tool_sequence` | Names + turn + error flag; args dropped |
| Normalized chain | `normalized_tool_chain`, `write_tool_sequence` | `normalize_tool_chain`, `extract_write_sequence` | Consecutive dupes collapsed |
| DB divergence | `db_diff_signature`, `db_diff_kinds`, `db_diff_entities` | `db_diff.py::compute_db_diff` | Offline gold/predicted replay; `missed`/`wrong`/`extra`; only for `db_only`/`mixed` |
| NL divergence | `nl_failure_signature`, `nl_failed_assertions` | `build_nl_signature`, `denoise_nl` | Denoised text of *failed* assertions only |
| Escalation | `escalated_to_human` | in `extract_simulation_features` | `transfer_to_human_agents` called |
| Last agent message | `last_agent_message` | `extract_last_agent_message` | JSON-unwrapped, denoised, capped — **the key embedding signal** |
| Tool errors | `tool_error_messages` | `extract_tool_errors` | Denoised, deduped |
| Policy heuristics | `policy_flags` | `compute_policy_flags` | `auth_before_mutate`, `confirm_before_write`, `single_tool_per_turn`, `num_env_errors` |
| Legacy summary | `embedding_text` | `build_embedding_text` | Used by the labeler only |

### DB-diff signature in one paragraph

`compute_db_diff` reconstructs three DB states on fresh retail envs — `initial`
(post-init), `gold` (initial + the task's reference actions), `predicted`
(initial + the agent's trajectory) — then `diff_dbs` classifies each divergent
leaf relative to `initial` as `missed` / `wrong` / `extra` and abstracts paths
(record IDs → `*`, list indices → `[]`). Result e.g.
`missed:orders.*.return_items;wrong:orders.*.cancel_reason`.

---

## 3. The clustering algorithm (default = embedding)

`cluster.py::run_cluster` always writes `clusters_l0.json` (deterministic
taxonomy) and `clusters.json` (final). `--method` selects the engine.

### Default: embedding engine (`lib/embedding_cluster.py::cluster_embeddings`)

1. **Document** — `build_cluster_document(sim, fields=...)` turns each failing
   trace into a text document: a **core spine** (failure type, tool chain,
   write chain, DB-diff tokens, entities, flags) always present, plus optional
   `WHY_FIELDS` (`nl`, `escalation`, `last_message`, `tool_errors`, `mechanism`).
   The ablation-validated default is **core + `last_message`**.
2. **Embed** — a pluggable `Embedder`. Default **`st`** = neural
   all-MiniLM-L6-v2. On this torch-less / offline box it runs via a pure-NumPy
   forward pass over the HF-cached weights (`lib/minilm_numpy.py`); if a real
   `sentence-transformers` install exists it uses that. Offline fallbacks:
   `tfidf`, `char`, `lsa` (sklearn-only). If `st` is unavailable it degrades to
   `tfidf`.
3. **Cluster** — agglomerative, cosine, average linkage, **auto-selected
   distance threshold**: scan a loose→tight ladder and take the loosest
   threshold whose largest cluster's share ≤ `max_cluster_share` (default
   **0.45**); `_auto_select_labels`. A fixed threshold is available (positive
   `--distance-threshold`); `--algo hdbscan` is also selectable.
   Default `--scope global` (cluster all failures together); `l0` scopes within
   each mechanism bucket.
4. **Materialize** — each group becomes a `Cluster`, named
   `"<dominant_mechanism> | <dominant_signature>"`, carrying `mechanism`,
   `signature`, `failure_type`, `failure_rate`, flag summary.

Membership is embedding-driven — **no decision tree decides which cluster a
trace joins.** The document is still ~80% rule-derived signals; `last_message`
is the one free-text field, which is why neural embeddings help.

### Secondary: signature engine (`lib/clustering.py::cluster_l1_l2`)

The original hand-authored decision tree, kept as `--method signature`: group by
`(l0_parent, _primary_signature)` where the signature is the DB-diff signature
(db failures) / denoised NL signature (nl failures) / write-chain (else), with a
guarded agglomerative refine on large groups. Exact-match keys, over-splits
(20 clusters / 60% singletons on the baseline vs embedding's 6 / 1).

### L0 taxonomy — now mechanism-based

`cluster_l0` buckets all sims by `mechanism_class` (`pass` for non-failures) — no
longer by `failure_type`. This is the primary reporting axis.

---

## 4. Primary axis: root-cause mechanism

`classify_mechanism` (`trace_parser.py`) deterministically assigns each failure a
cause from the extracted signals. Precedence encodes what drove the failure:

```
pass/termination → pass / premature_termination
nl_only/comm_only → bailed_transfer (if escalated) else comm_miss
db-gated & no writes → identification_failure (not-found + escalated)
                      / bailed_transfer (escalated) / stalled_no_action
db-gated & wrote     → bailed_transfer (escalated)
                      / wrong_params (diff has wrong|extra)
                      / incomplete_multitask (diff has missed) / other
```

Classes: `bailed_transfer`, `wrong_params`, `incomplete_multitask`,
`stalled_no_action`, `identification_failure`, `comm_miss`,
`premature_termination`, `other`.

**Why this replaced `db_only/nl_only/mixed`:** the symptom axis is scorer-exact
but cross-cuts real causes — the dominant `bailed_transfer` cause was scattered
across all three symptom buckets, and `mixed` was largely an artifact of task
composition (DB+NL both fail because the agent did nothing on a task that
happens to have NL assertions). `failure_type` is retained as a secondary
"where reward was lost" attribute; `mechanism_class` is the actionable axis used
for L0 buckets and cluster names.

**Validity:** deterministic, and **91% (33/36)** agreement with hand-labeled
root causes on `baseline-gpt55-t2` (perfect on the two dominant classes,
`wrong_params` 15/15 and `bailed_transfer` 13/13). It's a heuristic — appropriate
for a *taxonomy/naming* axis (clustering membership stays embedding-driven) — and
should be re-validated as labeled data grows. The 3 residual misses (an
incomplete-with-a-wrong-value; a refusal reading as comm-miss) are accepted.

Ground truth: `tools/harness-opt/eval/root_cause_labels.baseline-gpt55-t2.json`.

---

## 5. How we chose the defaults (evaluation)

All three defaults were tuned against the hand labels, not by taste.

- **Embedder + document (`ablate_document.py`).** Scored document field-subsets ×
  embedders by ARI/V-measure vs the 36 labels. Winner: **`st` + core+last_message**
  — ARI **0.697**, V-measure 0.769, and it recovers exactly the **6** root-cause
  classes (vs tfidf 0.467, char 0.29, and the signature engine 0.20). Neural
  embeddings unlock the free-text signals (marginal V-measure: `last_message`
  +0.33, `nl` +0.10, `escalation` +0.08); bag-of-words got ~0 from them. Adding
  `mechanism` to the document did **not** beat core+last_message, so it stays a
  labeling axis only.
- **Auto-threshold cap (0.45).** A fixed threshold didn't transfer across runs
  (a weak model collapsed 74% of failures into one blob at 0.3). The share-cap
  ladder with cap **0.45** was tuned on the labeled run: it reproduces the
  ARI-optimal 6-cluster result there *and* fixes the weak-model run (74% blob →
  30 clusters, 22% largest). See §6.
- **Metric note.** ARI is the target (rewards correct grouping, penalizes
  over-splitting); V-measure's homogeneity term rewards pure-but-fragmented
  clusterings, so we don't optimize it alone. Thresholds are tuned against the
  same labels (no held-out split, N=36), so absolute numbers are optimistic —
  the *ranking* (`st` ≫ tfidf ≫ signature) is the trustworthy result.

---

## 6. Cross-run generalization

Run on all `data/simulations/` runs with the default engine:

| Run | Model | Failures | Clusters | Largest | Note |
|-----|-------|----------|----------|---------|------|
| `baseline-gpt55-t2` | gpt-5.5 | 36 | 6 | 41% | tuning run (ARI 0.70) |
| `baseline-gpt55-t2XXXXXXXX` | gpt-5.5 | 32 | 10 | 34% | near-dup; transfers |
| `baseline-gpt54mini-t2` | gpt-5.4-mini | 167 | 30 | 22% | blob avoided by auto-threshold |
| `ccand-gpt54mini-t2` | gpt-5.4-mini | ~119 | 16 | 42% | candidate run |

Two honest findings: (1) the **method** generalizes (same-regime runs need no
retuning), but a **fixed threshold does not** — hence auto-threshold. (2) The
weak model's failures are intrinsically fuzzier (silhouette ~0.18 at any
threshold vs ~0.4 for gpt-5.5); auto-threshold prevents the blob but can't
manufacture clean separation. The mechanism L0 makes this legible: `gpt54mini`
is **66% `stalled_no_action`** — a single harness-fixable story the symptom axis
would have hidden inside `db_only`.

---

## 7. Known issues & remaining work

- **`failure_rate` is ~1.0 in final clusters.** `_failure_rate_for_tasks`
  computes each task's pass fraction over sims *in the cluster*, but final
  clusters contain only failures → rate ≈ 1.0. Meaningful only in L0. True
  per-task flakiness (trial 0 passes, trial 1 fails) needs the pass sims — the
  P5 signal.
- **Thresholds/cap tuned on one labeled run (N=36).** Re-validate as more
  labels/runs arrive; the cap is robust across caps 0.35–0.6 on the weak run but
  the labeled run is the only ground truth.
- **`st` requires a cached MiniLM (or torch).** Present on this box; elsewhere it
  falls back to `tfidf` (auto-threshold still applies) with a printed warning.
- **Mechanism is heuristic (91%).** The rare classes (`identification_failure`,
  `comm_miss`, `wrong_decision_refused`) are fuzzy; the two dominant ones are
  exact.
- **Legacy naming.** `clustering.py`'s "L1/L2" vocabulary predates the current
  structure; the signature engine is legacy-but-supported.

---

## 8. Pointers

- Engine code: `tools/harness-opt/lib/{embedding_cluster,minilm_numpy,clustering,trace_parser,db_diff}.py`
- Stage scripts: `tools/harness-opt/scripts/{extract_features,cluster,label_clusters,generate_report}.py`
- Eval/tuning: `tools/harness-opt/scripts/{ablate_document,compare_clusterings,sweep_clusterings}.py`; artifacts in `tools/harness-opt/eval/`
- Contracts: `docs/phases/contracts/{features,clusters}.schema.json`
- Ground-truth labels: `tools/harness-opt/eval/root_cause_labels.*.json`
- History & rationale: `docs/decision-log.md`, `docs/strategy.md`
- Latest artifacts: `reports/<run>/`
```
