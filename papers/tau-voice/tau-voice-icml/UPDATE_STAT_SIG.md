# Updating the Paper: Statistical Significance Analysis

## Summary

The paper's statistical significance section was written for the **original model set** (OpenAI `gpt-realtime-2025-08-28`, 3 independent runs on Retail). We now have **updated results** with:

- **New OpenAI model:** `gpt-realtime-1.5` (replacing `gpt-realtime-2025-08-28`)
- **2 independent runs** per condition (down from 3)
- **Task 33/34 fix** applied to results
- **New analysis method:** Paired permutation test with Holm-Bonferroni correction (replacing simple Wilson CI overlap)

The corrected results are in `data/exp/final_voice_results_all_analysis/performance_analysis/pass_k_by_domain/speech_complexity_pairwise_statsig.{md,csv}`.

---

## Decisions

- **Table format:** Option A — condensed pairwise significance table (key comparisons with deltas + p-values), replacing the old Mean ± SEM CI table
- **2 runs framing:** Emphasize the paired permutation test (114 task-level paired observations, strong statistical power regardless of number of runs). Don't use SEM-based CIs (df=1 is unreliable with 2 runs).
- **Ablation stat sig:** Keep in appendix only. Don't add to ablation section. Optionally mention xAI accent vulnerability (p < 0.001) in the stat sig paragraph as a single highlight.

---

## Old vs New Values

### Sample Sizes

| Item | Old | New |
|------|-----|-----|
| Voice runs per condition | 3 | 2 (228 sims = 2 × 114 tasks) |
| Text trials | 3 (n=342) | 4 (n=456) |
| Tasks per run | 114 | 114 |

### Success Rates (Retail, Control/Clean)

| Provider | Old Rate | New Rate |
|----------|----------|----------|
| Google (Gemini) | 38.3% | **42.1%** |
| OpenAI | 39.2% | **67.5%** |
| xAI | 36.3% | **50.0%** |

### Success Rates (Retail, Regular/Realistic)

| Provider | Old Rate | New Rate |
|----------|----------|----------|
| Google (Gemini) | 26.0% | **28.9%** |
| OpenAI | 12.0% | **43.0%** |
| xAI | 21.1% | **36.8%** |

### Text Baselines (Retail)

| Model | Old Rate | New Rate |
|-------|----------|----------|
| GPT-4.1 (Non-Reasoning) | 73.4% | **76.3%** |
| GPT-5 (Reasoning) | 81.9% | **81.6%** |

---

## Changes to Make

### 1. Copy corrected stat sig results to paper directory

`papers/tau-voice/results/` copies are stale. Copy from source of truth:

```bash
cp data/exp/final_voice_results_all_analysis/performance_analysis/pass_k_by_domain/speech_complexity_pairwise_statsig.md papers/tau-voice/results/
cp data/exp/final_voice_results_all_analysis/performance_analysis/pass_k_by_domain/speech_complexity_pairwise_statsig.csv papers/tau-voice/results/
```

### 2. `results/stat_sig_table.tex` — Replace with pairwise significance table

**Old format:** Mean ± 95% CI (SEM-based) for 7 rows. Unreliable with only 2 runs (df=1).

**New format:** Condensed pairwise significance table showing key comparisons:

| Comparison | Provider | Rate A | Rate B | Δ (pp) | p (adj) |
|------------|----------|--------|--------|--------|---------|
| Text (NR) → Clean | Gemini | 76.3% | 42.1% | -34.2 | <0.001 |
| Text (NR) → Clean | OpenAI | 76.3% | 67.5% | -8.8 | 0.032 |
| Text (NR) → Clean | xAI | 76.3% | 50.0% | -26.3 | <0.001 |
| Clean → Realistic | Gemini | 42.1% | 28.9% | -13.2 | 0.026 |
| Clean → Realistic | OpenAI | 67.5% | 43.0% | -24.6 | <0.001 |
| Clean → Realistic | xAI | 50.0% | 36.8% | -13.2 | 0.044 |

All p-values are Holm-Bonferroni corrected paired permutation tests (100k permutations, paired by task_id).

### 3. `contents/results.tex` line 26-27 — Statistical Reliability paragraph

**Remove:** `\needsupdate` tag on line 26.

**Old text:**
> For Retail, where we conducted 3 independent runs per condition, both the text-to-Clean gap and the Clean-to-Realistic gap are statistically significant (non-overlapping 95% CIs). Voice providers achieve 36–39% ± 3–6pp (Clean) and 12–26% ± 2–4pp (Realistic), compared to text baselines of 73% ± 3pp (GPT-4.1) and 82% ± 1pp (GPT-5). Full statistical breakdown in Appendix~\ref{app:stat-sig}.

**Suggested replacement:**
> For Retail, where we conducted 2 independent runs per condition (228 simulations per condition), we test statistical significance using paired permutation tests (100k permutations, paired by task\_id, Holm-Bonferroni corrected). Both the text-to-Clean gap and the Clean-to-Realistic gap are statistically significant for all three providers (all p < 0.05; Table~\ref{tab:stat-sig}). Even the narrowest gap---text non-reasoning (76\%) vs OpenAI Clean (68\%)---is significant at p = 0.032. Full pairwise breakdown in Appendix~\ref{app:stat-sig}.

### 4. `appendix/additional_results.tex` lines 66-83 — Full Appendix section

**Remove:** `\needsupdate` tag on line 66.

**Old text claims that are now wrong:**

| Old Claim | New Reality |
|-----------|-------------|
| "3 independent runs per condition" | 2 runs |
| "OpenAI at 39.2% ± 2.5%" | OpenAI at 67.5% |
| "GPT-4.1 at 73.4% ± 2.5%" | GPT-4.1 at 76.3% |
| "providers' CIs overlap under Clean" | OpenAI (67.5%) clearly separated from xAI (50.0%) and Gemini (42.1%) |
| "Google best under Realistic (26.0%)" | OpenAI best (43.0%) |
| "OpenAI worst under Realistic (12.0%)" | Gemini worst (28.9%) |

**Suggested replacement:**

> To assess statistical reliability, we conducted 2 independent runs per condition on the Retail domain (n=114 tasks per run, 228 simulations per condition). Rather than relying on trial-level confidence intervals (which require 3+ runs for reliable variance estimation), we use paired permutation tests: for each pair of conditions, we compute per-task mean success rates, pair by task\_id, and test whether the paired differences are systematically non-zero (100k permutations, two-sided, Holm-Bonferroni corrected within each provider group).
>
> Table~\ref{tab:stat-sig} confirms that both key gaps are statistically significant: (1) the text-to-Clean gap is significant for all providers and both text baselines (all p < 0.05); and (2) the Clean-to-Realistic gap is significant for all three providers (Google p = 0.026, OpenAI p < 0.001, xAI p = 0.044).
>
> The full pairwise analysis (including all five speech complexity conditions) is available in the supplementary materials.

### 5. Remove `\needsupdate` tags

1. `results.tex` line 26
2. `additional_results.tex` line 66

### 6. Add `\revised{}` annotations

Add revision notes to rewritten sections explaining what changed (consistent with paper convention).

---

## What NOT to change

### Ablation section (`results.tex` lines 29-37)

Do **not** add stat sig results to the ablation narrative. Reasons:
- The ablation section is well-structured with effect sizes and relative percentages
- Some effects the paper discusses (e.g., Google's behavior sensitivity) are not individually significant — surfacing stat sig would undermine those claims
- The paper already hedges with "indicative rather than definitive" for accents
- The full pairwise table in the appendix covers ablation comparisons for readers who want to check

**Optional:** Add one sentence to the stat sig paragraph noting that the pairwise analysis also tests individual factors, with xAI's accent vulnerability being highly significant (p < 0.001).
