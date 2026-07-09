# Phase 0 — Clustering Engine: Current State & Roadmap

> Living design note. Captures how the failure-clustering engine works today,
> what is deliberately provisional, and the open question we most want to keep
> alive: **moving from today's hand-authored, domain-specific decision tree
> toward a more generalizable representation-and-distance approach.**
>
> Read this alongside the code — it points at functions and line ranges rather
> than repeating them. Line numbers are accurate as of the P1–P4 work
> (see [`docs/decision-log.md`](../../decision-log.md)).

---

## 1. Pipeline overview (trace → cluster)

`analyze` is an orchestrator that shells out to four scripts in sequence; each
reads and writes typed JSON under `reports/<run>/` and never talks to the next
stage except through those files.

- Orchestration: `cli.py::analyze` (L125–146). Stage scripts are invoked as
  subprocesses with `PYTHONPATH` set (`cli.py::_run_script`, L21–24).
- Contracts for every artifact: `docs/phases/contracts/*.schema.json`, mirrored
  as Pydantic models in `contracts/models.py`.

```
data/simulations/<run>/results.json          raw tau2 trajectories (input)
        │  scripts/extract_features.py   → lib/trace_parser.py (+ lib/db_diff.py)
        ▼
reports/<run>/features.json                   one SimulationFeatures record per sim
        │  scripts/cluster.py            → lib/clustering.py
        ▼
reports/<run>/clusters_l0.json  +  clusters.json
        │  scripts/label_clusters.py
        ▼
reports/<run>/cluster_labels.json
        │  scripts/generate_report.py
        ▼
reports/<run>/{manifest.json, task_summary.csv, analysis_summary.md}
```

The important consequence: **after feature extraction, the clustering code never
re-reads raw messages.** Everything downstream operates on the flat
`SimulationFeatures` record. Any signal the clustering can use must first be
materialized in Stage 1.

---

## 2. Signal extraction (what each trace becomes)

`extract_features.py::run_extract` (L29+) loads `Results`, and for the retail
domain also loads the task set + a base `RetailDB` once
(`_load_retail_context`, L18–27) so the P1 replay does not re-parse the 2.7 MB
DB per simulation. Each simulation is reduced to one `SimulationFeatures` object
by `trace_parser.py::extract_simulation_features` (L267+).

| Signal | Field(s) | Produced by | Notes |
|--------|----------|-------------|-------|
| Failure taxonomy (P0) | `failure_type` | `classify_failure` (L63–88), `_component_failed` (L41–61) | Retail gates on `DB` + `NL_ASSERTION`; buckets: `pass` / `db_only` / `nl_only` / `mixed` / `communicate_only` / `termination` |
| Reward components | `db_reward`, `nl_reward`, `communicate_reward` | `_reward_components` (L91+) | Straight from `reward_breakdown` |
| Raw tool calls | `tool_sequence` | `extract_tool_sequence` (L111+) | Names + turn + error flag, args dropped |
| Normalized chain (P2) | `normalized_tool_chain`, `write_tool_sequence` | `normalize_tool_chain` (L205+), `extract_write_sequence` (L214+) | Consecutive dupes collapsed; write set from `break_down_metrics.get_write_tools` |
| DB divergence (P1) | `db_diff_signature`, `db_diff_kinds`, `db_diff_entities` | `db_diff.py::compute_db_diff` (L163+) | Offline gold/predicted replay; only for `db_only`/`mixed` |
| NL divergence (P3) | `nl_failure_signature`, `nl_failed_assertions` | `build_nl_signature` (L192+), `denoise_nl` (L186+) | Denoised text of *failed* assertions only |
| Policy heuristics | `policy_flags` | `compute_policy_flags` (L147+) | `auth_before_mutate`, `confirm_before_write`, `single_tool_per_turn`, `num_env_errors` |
| Human/LLM text | `embedding_text` | `build_embedding_text` (L226+) | **Not consumed by clustering today** — only by the labeler |

### The P1 DB-diff signature in one paragraph

`compute_db_diff` reconstructs three DB states on fresh retail envs — `initial`
(post-task-init), `gold` (initial + the task's reference actions), and
`predicted` (initial + the agent's trajectory) — then `diff_dbs` (L137+) walks
gold vs predicted, classifying each divergent leaf relative to `initial` as
`missed` / `wrong` / `extra` (`_classify`, L83–91) and abstracting concrete
paths (record IDs → `*`, list indices → `[]`) via `_abstract` (L124–134). The
result is a value-free string like
`missed:orders.*.return_items;wrong:orders.*.cancel_reason`.

---

## 3. The clustering algorithm (today = a decision tree)

`cluster.py::run_cluster` calls two functions in `lib/clustering.py`.

### Layer 0 — deterministic taxonomy partition

`cluster_l0` (L107–139) partitions **all** sims (passes included) by the string
`f"{failure_type}:{termination_reason}"`. Pure dict bucketing, no ML, fully
reproducible. On `baseline-gpt55-t2`: `pass` (192), `db_only:user_stop` (26),
`mixed:user_stop` (5), `nl_only:user_stop` (5). This layer's only job is to make
sure the finer layer never merges across failure types.

### Final layer — signature grouping + guarded similarity split

`cluster_l1_l2` (L142–196):

1. Drop passes; map each failing sim to its L0 parent (L149–158).
2. Group by the tuple **`(l0_parent_id, primary_signature)`** (L160–163).
3. Optionally split large groups (`_refine_group`, L38–75).
4. Emit `Cluster` objects, ID by size rank, then re-sort by
   `(-failure_rate, -count, id)` (L170–196).

The routing that decides a trace's signature is `_primary_signature` (L19–35).
Rendered as the decision tree it literally is:

```
                        ┌─ failure_type == pass ──────────────► excluded (not clustered)
trace ─ failure_type ───┤
                        ├─ db_only  ─► key = "db=<db_diff_signature>"
                        ├─ nl_only  ─► key = "nl=<nl_failure_signature>"
                        ├─ mixed    ─► key = "db=<...> | nl=<...>"   (both, strict)
                        └─ else     ─► key = "chain=<write_tool_sequence or normalized_chain>"
                                        (termination / communicate_only)

group  = (L0 parent, key)               # exact-string match → same group
refine = if len(group) >= 6:            # TF-IDF(normalized_chain) + agglomerative,
             cosine distance_threshold=0.5   #   n_clusters=None (threshold, not k)
         else: keep as one cluster
```

Two mechanics worth remembering:

- The refinement path is **guarded and rarely fires today** — the biggest
  signature group on the baseline is n=6, and its chains are similar enough not
  to split. So current final clusters are effectively *pure signature groups*.
- `_refine_group` degrades gracefully: missing sklearn, trivial vocabulary, or
  any exception returns the group unsplit (L50–70).

`assign_cluster_to_simulations` (L199–211) inverts cluster→sims into a
sim→cluster_id map (passes → `"pass"`) for `task_summary.csv`.

---

## 4. Why this is "bucketed" — the core limitation

Everything above is a **symbolic, hand-authored decision tree** whose leaves are
exact-match string keys. It works well right now (28→20 clusters, 79%→60%
singletons) precisely *because* we injected a lot of retail domain knowledge:

- **Retail DB schema** drives ID-vs-field abstraction — `db_diff.py::retail_field_names`
  (L31–66) introspects `RetailDB`; `_abstract` (L124) keys off it.
- **Retail write-tool set** defines `write_tool_sequence` (`get_write_tools("retail")`).
- **Retail reward basis** (`DB` + `NL_ASSERTION`) is hard-coded into the taxonomy.
- **NL denoise regex** (`_NL_NOISE`, `trace_parser.py` L183) is tuned to strip
  `$amounts` / `#W...` IDs / quantities.

This yields interpretable clusters but has structural weaknesses:

1. **Exact-match, no notion of distance.** Two DB signatures that differ by a
   single path do not merge (e.g. the two `orders.*.address.*` clusters — one
   includes `country`, one does not). There is no "these mechanisms are 90%
   similar" — it is identical-or-not.
2. **`mixed` is maximally strict.** Concatenating db + nl signatures means a
   mixed failure only merges with another that diverged identically on *both*
   axes; realistically most mixed sims become singletons.
3. **Does not generalize across domains.** Point it at airline/telecom and the
   field-name introspection still works, but the taxonomy assumptions, write-tool
   semantics, and NL denoise heuristics would need re-authoring.
4. **Brittle to schema/policy drift.** New order fields or a changed reward basis
   silently change signatures.
5. **Singleton ambiguity.** A 60% singleton rate mixes *genuinely unique*
   mechanisms with *under-clustered near-duplicates*, and today we can't tell
   them apart without eyeballing (hence Phase 1).

**We explicitly want to keep the door open to replacing the leaves (and possibly
the whole tree) with a representation + distance + density-based approach** — see
§6. The taxonomy (L0) is worth keeping as a hard constraint or a feature; the
brittle part is the exact-match signature leaves.

---

## 5. Known issues & short-term Phase 0 tweaks

These are concrete, mostly-local fixes to revisit *after* Phase 1 gives us a
way to see their effect.

- **`failure_rate` is always 1.0 in final clusters.** `_failure_rate_for_tasks`
  (L93–104) computes each task's pass fraction over the sims *in the cluster*,
  but final clusters contain only failures (passes filtered at L149). So the
  numerator is always 0 → rate 1.0 everywhere. It is meaningful only in L0.
  True per-task flakiness (trial 0 passes, trial 1 fails) needs the pass sims and
  is exactly the P5 signal — fixing this is a prerequisite for flaky-task work.
- **Stale naming.** Module docstring (`clustering.py` L1) and the "L1/L2"
  vocabulary predate P4; the real structure is L0-taxonomy → signature-group →
  threshold-split. Rename to reduce confusion.
- **`embedding_text` is computed but unused by clustering** (only the labeler
  reads it). Either wire it in or stop implying it drives clustering.
- **Refinement is untuned.** `min_size=6` and `distance_threshold=0.5`
  (`_refine_group` L41–42) are guesses; no run has stress-tested them.
- **P1 replay caveats.** Half-duplex only (uses `simulation.get_messages()`);
  failures are swallowed and return `None` (L205–206) → sim silently falls back
  to `db=unknown` and can over-merge. Consider surfacing replay-failure as its
  own signal.
- **Cross-tab confidence.** `analysis_summary.md` reports singleton %, but we
  lack an automated cluster-cohesion metric.

---

## 6. Open direction — a less-bucketed, generalizable engine

The goal is to preserve interpretability while removing the exact-match brittleness
and the domain-specific authoring. Sketch of the target shape:

### 6.1 Representation (embed each trace)
Move each `SimulationFeatures` record to a vector (or a set of typed sub-vectors)
so we can measure *distance* between failures:

- **Structured-signal features** — one-hot / multi-hot over abstracted DB-diff
  paths × kind (`missed`/`wrong`/`extra`), policy flags, failure type. Cheap,
  interpretable, already 90% available from P1/P2/P3 outputs.
- **Tool-chain sequence** — n-gram TF-IDF over `normalized_tool_chain` (already
  used inside `_refine_group`), or a learned sequence embedding.
- **Text / LLM embeddings** — embed a natural-language trace summary or the
  existing `embedding_text` with a sentence/LLM embedder. This is the most
  domain-agnostic option and the clearest "leave the door open" lever.
- **DB-diff as a vector** — bag-of-abstracted-paths so two signatures differing
  by one path are *close* rather than disjoint (directly fixes the address-cluster
  split in §4.1).

### 6.2 Distance & fusion
Combine sub-vector distances (e.g. weighted cosine over structured + chain +
text). Fusion weights become the tunable knob instead of hand-authored keys.

### 6.3 Clustering method (no fixed k)
- **HDBSCAN** — density-based, no `k`, and it labels true outliers as noise —
  which is exactly the right model for "genuinely unique mechanism vs
  under-clustered near-duplicate."
- **Agglomerative with a distance threshold** — already prototyped in
  `_refine_group`; generalize it from "refine large buckets" to "cluster the
  whole L0 partition."
- **Graph community detection** on a kNN similarity graph — interpretable,
  handles varying densities.

### 6.4 Keep interpretability
Even with embedding-based clustering, keep the P1/P3 signatures as **cluster
metadata/labels** (most common signature per cluster), so a human still reads
"this cluster ≈ wrong cancel_reason." The symbolic signatures become descriptors,
not the partition function.

### 6.5 Migration path (low-risk)
- Put the current logic behind a strategy interface: `cluster_failures(features,
  strategy=...)` where `strategy ∈ {signature (today), embedding, hybrid}`.
- `_primary_signature` + `_refine_group` become the `signature` strategy.
- Keep L0 taxonomy as a hard pre-partition (or feed `failure_type` in as a
  feature) so we never merge a DB failure with an NL failure regardless of
  strategy.
- Gate the switch on measured cohesion + the Phase 1 visual review, not vibes.

### 6.6 Evaluation (what "better" means)
We currently have no ground-truth partition. Options: intra/inter-cluster cohesion
(silhouette on the chosen distance), stability under resampling/trials, and
human agreement via the Phase 1 gallery. Phase 1 is the enabler — we cannot
responsibly tune §6 without being able to *look* at the clusters.

---

## 7. What Phase 1 must expose to unblock Phase 0 tuning

Concrete asks from the dashboard so we can judge and iterate on clustering:

- **Cluster gallery**: for each cluster, list member sims with their
  `signature`, `db_diff_signature`, `nl_failure_signature`, `normalized_tool_chain`,
  `policy_flags`, reward components.
- **Side-by-side trace diff**: compare two traces (esp. across singletons) to
  answer "why didn't these merge?" — ideally show the signature delta.
- **Cluster × actual-reward cross-tab**: confirm the taxonomy is faithful.
- **Singleton inspector**: surface all singletons and their nearest neighbor by
  signature/chain similarity, to estimate how many are truly unique vs
  under-clustered.
- **(Forward-looking)** a trace-distance heatmap once §6 embeddings exist.

See [`../phase-1/README.md`](../phase-1/README.md) for the page/agent breakdown;
the TraceExplorer + ClusterGallery + RunComparison pages cover most of the above.

---

## 8. Pointers

- Engine code: `tools/harness-opt/lib/{clustering,trace_parser,db_diff}.py`
- Stage scripts: `tools/harness-opt/scripts/{extract_features,cluster,label_clusters,generate_report}.py`
- Contracts: `docs/phases/contracts/{features,clusters}.schema.json`
- History & rationale: `docs/decision-log.md`, `docs/strategy.md`
- Latest baseline artifacts: `reports/baseline-gpt55-t2/`
