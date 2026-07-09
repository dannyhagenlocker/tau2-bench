# Phase 3 — Generations, Stats & Writeup

**Status:** Docs only (implement after Phase 2)  
**Agents:** P3-Harness, P3-Stats, P3-Writeup

## Goal

Run discrete **generations** of harness improvement, measure confidence vs baseline, produce submission `writeup.md`.

## Generation loop

```
Generation N:
  1. (Human) Full rollout: tau2 run --save-to genN-gpt55-t2 --num-trials 2
  2. harness-opt analyze --run genN --baseline baseline-gpt55-t2
  3. (Human) Review clusters in dashboard
  4. Propose + accept 2-3 clusters (Phase 2)
  5. Merge accepted proposals
Generation N+1:
  Repeat from step 1
```

Full benchmark runs are **human-triggered** at generation boundaries only.

## CLI (planned)

| Command | Description |
|---------|-------------|
| `harness-opt compare --baseline A --candidate B` | McNemar, Wilson CI, flip table |
| `harness-opt writeup --baseline A --final B --reports-dir reports/` | Generate `writeup.md` |

## Metrics (P3-Stats)

| Metric | Use |
|--------|-----|
| Task pass rate | Primary headline |
| DB / COMMUNICATE pass rate | Failure attribution |
| McNemar p-value | Paired significance baseline vs final |
| Wilson 95% CI | Pass rate uncertainty |
| Task flip table | Regressions highlighted |
| Mean cost / steps | Writeup secondary |

**Subset eval:** report raw delta only; not used for final confidence claims.

## Agent briefs

### P3-Harness

- Harness changes only via Phase 2 proposals (not ad-hoc)
- Register retail-tuned agent in `registry.py` when needed

### P3-Stats

- **Owns:** `lib/stats.py`, `scripts/compare_runs.py`
- **Input:** two `task_summary.csv` or two run names
- **Output:** `reports/comparisons/<baseline>-vs-<candidate>.json` + markdown summary

### P3-Writeup

- **Owns:** `scripts/generate_writeup.py`
- **Input:** `reports/` artifacts, decision-log, strategy
- **Output:** `writeup.md` at repo root

## writeup.md sections (auto-populated where possible)

1. Baseline results + failure mode analysis
2. Tooling built + harness changes (linked to clusters)
3. Final results vs baseline + confidence (McNemar, CI)
4. Cost breakdown
5. What did not work
6. AI assistance disclosure
7. What we would try next

## Acceptance criteria

- `compare` produces flip table + McNemar for baseline vs final
- `writeup.md` includes cluster names, proposal summaries, and cost from manifest metadata
- Generation history traceable via immutable `reports/` dirs

## Budget guidance

| Item | ~Cost |
|------|-------|
| Baseline 2× full | $16 |
| Final 2× full | $16 |
| 5-8 subset evals | $8-12 |
| LLM labeling + proposals | $2-4 |

Reserve headroom for one extra generation full run if budget allows.
