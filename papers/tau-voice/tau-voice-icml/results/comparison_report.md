# τ-voice Results Comparison Report

Comparison of old results (`papers/tau-voice_submission/results/`) vs new results (`data/exp/final_voice_results_trial1_analysis_new/paper/`).

Both datasets cover 278 tasks across 3 domains (retail=114, airline=50, telecom=114) and 3 providers (Google, OpenAI, xAI).

## What changed

- **Different OpenAI model**: The old paper used `gpt-4o-realtime-preview` (later renamed `gpt-realtime-2025-08-28`). The new results use `gpt-realtime-1.5`, a newer and more capable model. OpenAI differences therefore reflect both the model upgrade and task changes.
- **Updated airline tasks**: Same 50-task count but the task set has been revised. This changes the text baselines for airline and therefore the "All" domain averages.
- **Updated retail tasks**: Same 114-task count but the task set has been revised (smaller change than airline). All providers were re-run. Retail text baselines shifted slightly (text\_sota: 81.6% → 81.0%, text\_nonthinking: 74.0% → 76.0%).
- **Telecom: Google re-run**: Google's telecom results were re-run due to a Gemini reconnection fix. Google Telecom Realistic improved (15.8%→17.5%), shifting aggregate Google numbers. xAI telecom data is unchanged. OpenAI has new telecom data (gpt-1.5 vs old gpt-4o-realtime-preview).
- **Google retail re-run** (vs intermediate results in `data/exp/tau_voice_new_analysis`): Google's retail results changed substantially from the intermediate analysis — Clean 38.6%→44.7%, Realistic 28.1%→29.8%. This also shifted all Google aggregate numbers and ablation results.
- **Full single-factor ablations available**: control, control\_audio, control\_accents, control\_behavior, and regular — for all 3 models.
- **Text baselines changed** due to updated airline and retail tasks:
  - text\_sota (GPT-5): All 80.0% → 84.7%, airline 62.5% → 83.0%, retail 81.6% → 81.0%, telecom 95.8% → 90.0%
  - text\_nonthinking (GPT-4.1): All 54.7% → 54.3%, airline 56.0% → 53.0%, retail 74.0% → 76.0%, telecom 34.0% → 34.0%

### Changes from previous final results (`final_voice_results_trial1_analysis`)

Google Telecom was re-run due to a Gemini reconnection fix, and 2 retail tasks were fixed (affecting all providers). Changes:

| Metric | Previous Final | Updated Final | Δ |
|--------|---------------|---------------|---|
| Google Retail Clean | 43.9% | **44.7%** | +0.9pp |
| OpenAI Retail Clean | 69.3% | **71.1%** | +1.8pp |
| OpenAI Retail Realistic | 43.9% | **44.7%** | +0.9pp |
| xAI Retail Realistic | 36.8% | **38.6%** | +1.8pp |
| Google Telecom Realistic | 15.8% | **17.5%** | +1.8pp |
| Google All Realistic | 25.2% | **25.8%** | +0.6pp |
| OpenAI All Clean | 48.5% | **49.0%** | +0.6pp |
| xAI All Realistic | 37.7% | **38.3%** | +0.6pp |

Key impact: Retail task fix improved all providers' retail scores. xAI's All-domain degradation narrowed from -13pp to -12pp. Google's Telecom robustness improved. OpenAI Retail Clean rose from 69% to 71%. Voice quality metrics unchanged.

### Changes from intermediate results (`tau_voice_new_analysis`)

Only Google changed (OpenAI and xAI are identical):

| Metric | Intermediate | Final | Δ |
|--------|-------------|-------|---|
| Google Retail Clean | 38.6% | **44.7%** | +6.1pp |
| Google Retail Realistic | 28.1% | **29.8%** | +1.7pp |
| Google All Clean | 28.9% | **31.0%** | +2.1pp |
| Google All Realistic | 24.6% | **25.8%** | +1.2pp |
| Ablation: Google accents | **+7.0pp** | **-0.9pp** | Flipped |
| Ablation: Google behavior | **+2.6pp** | **-11.4pp** | Flipped |

---

## 1. Main Results (Pass@1)

### Overall (All domains)

| Provider | Model | Old Clean | New Clean | Δ | Old Realistic | New Realistic | Δ | Old Gap | New Gap | Δ |
|----------|-------|-----------|----------|---|---------------|--------------|---|---------|--------|---|
| Google | gemini-live-2.5-flash | 29.2% | **31.0%** | **+1.8pp** | 24.5% | 25.8% | +1.3pp | -4.8pp | -4.9pp | -0.1pp |
| OpenAI | gpt-1.5 (was gpt-4o-rt) | 33.1% | **49.0%** | **+15.9pp** | 19.3% | **35.3%** | **+16.0pp** | -13.8pp | -13.7pp | +0.1pp |
| xAI | xai-realtime | 42.3% | **50.7%** | **+8.4pp** | 30.3% | **38.3%** | **+8.0pp** | -12.0pp | -12.4pp | -0.4pp |

### Rankings

**Clean (control):**
1. xAI: 50.7% (was 42.3%, still #1)
2. OpenAI gpt-1.5: 49.0% (was 33.1% with old model)
3. Google: 31.0% (was 29.2%)

**Realistic (regular):**
1. xAI: 38.3% (was 30.3%, still #1)
2. OpenAI gpt-1.5: 35.3% (was 19.3% with old model)
3. Google: 25.8% (was 24.5%)

### Per-domain breakdown

| Domain | Provider | Old Clean | New Clean | Δ | Old Realistic | New Realistic | Δ |
|--------|----------|-----------|----------|---|---------------|--------------|---|
| Retail | Google | 39.5% | **44.7%** | **+5.2** | 28.1% | 29.8% | +1.7 |
| Retail | OpenAI gpt-1.5 | 39.5% | **71.1%** | **+31.6** | 15.8% | **44.7%** | **+28.9** |
| Retail | xAI | 42.1% | 48.2% | +6.1 | 20.2% | **38.6%** | **+18.4** |
| Airline | Google | 28.0% | 28.0% | = | 26.0% | 30.0% | +4.0 |
| Airline | OpenAI gpt-1.5 | 36.0% | **48.0%** | **+12.0** | 28.0% | **40.0%** | **+12.0** |
| Airline | xAI | 26.0% | **46.0%** | **+20.0** | 34.0% | 36.0% | +2.0 |
| Telecom | Google | 20.2% | 20.2% | = | 19.3% | 17.5% | -1.8 |
| Telecom | OpenAI gpt-1.5 | 23.7% | 28.1% | +4.4 | 14.0% | **21.1%** | **+7.1** |
| Telecom | xAI | 58.8% | 57.9% | -0.9 | 36.6% | 40.4% | +3.8 |

**Clean > Realistic pattern by domain:**

The aggregate result (Clean > Realistic for all providers) masks a per-domain exception:

| Domain | Pattern | Details |
|--------|---------|---------|
| **Retail** | **Holds for all models** | Largest degradations in the benchmark. Deltas range from -9.6pp (xAI) to -26.3pp (gpt-1.5). Google's delta is -14.9pp. Retail is the domain where speech complexity most reliably hurts performance. |
| **Airline** | **Breaks for Google** | Google: Realistic *exceeds* Clean by +2.0pp. gpt-1.5 (-8.0pp) and xAI (-10.0pp) follow the expected pattern. The small task count (n=50) means Google's reversal could be noise. |
| **Telecom** | **Holds for all models** | All providers show the expected pattern. xAI has the largest drop (-17.5pp), while Google and gpt-1.5 show smaller degradations (-2.6pp and -7.0pp). |

In the old paper, airline/xAI was also an exception (Realistic exceeded Clean by +8.0pp), but with the updated tasks this has flipped to -10.0pp. The only remaining exception is Google on airline (+2.0pp).

**Key findings:**
- **All providers show higher scores**, driven by updated retail and airline tasks plus the new OpenAI model.
- **OpenAI gpt-1.5 is a major upgrade**: 71.1% retail Clean is the single best per-domain score, and 49.0% aggregate Clean is close to xAI's 50.7%.
- **xAI leads in Realistic** at 38.3%, followed by OpenAI gpt-1.5 at 35.3%.
- **Google improved in retail** (Clean 39.5%→44.7%) and telecom Realistic (15.8%→17.5%), but remains last overall at 31.0% Clean / 25.8% Realistic.
- **The competitive gap has tightened**: All three providers now cluster between 26–38% in Realistic (was 19–30%). The xAI lead has shrunk from 11pp to just 3pp.

---

## 2. Core Voice Metrics

| Provider | Metric | Old Clean | New Clean | Δ | Old Realistic | New Realistic | Δ |
|----------|--------|-----------|----------|---|---------------|--------------|---|
| Google | Resp. Latency | 1.36s | 1.37s | +0.01 | 1.44s | 1.43s | -0.01 |
| Google | Resp. Rate | 0.984 | 0.956 | -0.03 | 0.866 | 0.806 | -0.06 |
| Google | Interrupt Rate | 0.095 | 0.074 | -0.02 | 0.244 | 0.206 | -0.04 |
| **OpenAI gpt-1.5** | **Resp. Latency** | **3.65s** | **1.69s** | **-1.96** | **3.24s** | **1.39s** | **-1.85** |
| **OpenAI gpt-1.5** | **Resp. Rate** | **0.892** | **0.993** | **+0.10** | **0.779** | **0.999** | **+0.22** |
| **OpenAI gpt-1.5** | **Interrupt Rate** | **0.407** | **0.010** | **-0.40** | **0.340** | **0.135** | **-0.21** |
| xAI | Resp. Latency | 0.90s | 1.05s | +0.15 | 0.99s | 1.15s | +0.16 |
| xAI | Resp. Rate | 0.952 | 0.921 | -0.03 | 0.907 | 0.913 | +0.01 |
| xAI | Interrupt Rate | 0.490 | 0.435 | -0.06 | 1.046 | 0.843 | **-0.20** |

**Key findings:**
- **OpenAI gpt-1.5 shows dramatically improved conversational dynamics** vs the old model: latency roughly halved (3.65s → 1.69s Clean), response rate near-perfect (99.3%), and Clean interrupt rate dropped from 41% to 1.0%.
- **xAI interruption rate improved** substantially (1.05 → 0.84 Realistic, -0.20). Still the highest of all providers.
- **Google slightly improved** vs intermediate: interrupt rate down (0.22→0.21). Telecom rerun shifted aggregate latency slightly (1.38→1.43s Realistic).

---

## 3. Voice Quality (Realistic condition)

### Aggregated metrics

| Metric | Google (old→new) | OpenAI gpt-1.5 (old→new) | xAI (old→new) |
|--------|-----------------|--------------------------|--------------|
| Latency | 1.13 → 1.14 | **2.22 → 0.90** | 0.99 → 1.15 |
| Responsiveness | 72% → **69%** | **69% → 100%** | 85% → 83% |
| Interrupt Rate | 24% → **21%** | **34% → 14%** | 105% → **84%** |
| Selectivity | 52% → **54%** | **75% → 6%** | 52% → 57% |

### Detailed voice quality (Realistic, All domains)

| Metric | Google (old→new) | OpenAI gpt-1.5 (old→new) | xAI (old→new) |
|--------|-----------------|--------------------------|--------------|
| Response Rate | 0.87 → 0.81 | **0.78 → 1.00** | 0.91 → 0.91 |
| Response Latency | 1.44s → 1.43s | **3.24s → 1.39s** | 0.99s → 1.15s |
| Yield Rate | 0.57 → 0.56 | **0.60 → 1.00** | 0.80 → 0.75 |
| Yield Latency | 0.82s → 0.86s | **1.20s → 0.42s** | 1.00s → 1.15s |
| Backchannel Err | 0.10 → 0.15 | **0.04 → 0.98** | 0.19 → 0.07 |
| Vocal Tic Err | 0.66 → 0.66 | **0.28 → 0.95** | 0.47 → 0.42 |
| Non-Directed Err | 0.70 → 0.55 | **0.42 → 0.90** | 0.79 → 0.79 |

**Key findings:**
- **OpenAI gpt-1.5 is a completely different profile from the old model**: near-perfect responsiveness (100%) but near-zero selectivity (6%). It responds to almost everything — backchannels, vocal tics, non-directed speech. The old model was the opposite: selective (75%) but slow (2.22s latency) and unresponsive (69%).
- **xAI selectivity improved**: backchannel error rate dropped from 0.19 to 0.07, and overall interrupt rate dropped from 1.05 to 0.84.
- **Google non-directed speech handling improved**: error rate dropped from 0.70 to 0.55. Backchannel error worsened slightly (0.10 → 0.15) due to telecom rerun. Overall selectivity dropped from 57% to 54%.

---

## 4. Voice vs Text Gap

The voice\_vs\_text table compares against `text_sota` (GPT-5 reasoning), which changed for airline (62.5% → 83.0%) and slightly for retail (81.6% → 81.0%) and telecom (95.8% → 90.0%).

### Against text\_nonthinking (GPT-4.1) — comparable to old paper

| Provider | Text (old→new) | New Realistic | Gap (old→new) |
|----------|---------------|--------------|--------------|
| Google | 54.7% → 54.3% | 25.8% | -30.2pp → -28.5pp |
| OpenAI gpt-1.5 | 54.7% → 54.3% | 35.3% | -35.4pp → **-19.0pp** |
| xAI | 54.7% → 54.3% | 38.3% | -24.4pp → **-16.0pp** |

### Against text\_sota (GPT-5 reasoning)

| Provider | Text (old→new) | New Realistic | Gap (old→new) |
|----------|---------------|--------------|--------------|
| Google | 80.0% → 84.7% | 25.8% | -55.5pp → -58.9pp |
| OpenAI gpt-1.5 | 80.0% → 84.7% | 35.3% | -60.7pp → **-49.4pp** |
| xAI | 80.0% → 84.7% | 38.3% | -49.7pp → **-46.4pp** |

**Key findings:**
- **Against GPT-4.1 (non-thinking), the gap narrowed dramatically** for OpenAI and xAI. xAI's gap is now only 16.0pp (was 24.4pp). OpenAI's gap nearly halved from 35.4pp to 19.0pp. Google improved slightly (-30.2pp → -28.5pp).
- **Against GPT-5 (reasoning), the picture is mixed**: OpenAI's gap narrowed substantially (60.7pp → 49.4pp) and xAI's narrowed slightly (49.7pp → 46.4pp), but Google's widened (55.5pp → 58.9pp). Overall range went from 50–61pp to 46–59pp.
- **xAI telecom still exceeds the non-thinking text baseline** (40.4% vs 34.0%), confirming this as the only domain where voice outperforms text.

---

## 5. Ablation (Retail domain, single-factor)

### Pass@1 values by condition

| Condition | Google | gpt-1.5 | xAI | All Avg |
|-----------|--------|---------|-----|---------|
| Control | **44.7%** | **71.1%** | 48.2% | 54.7% |
| +Audio | 40.4% (-4.4pp) | **66.7%** (-4.4pp) | 46.5% (-1.8pp) | 51.2% (-3.5pp) |
| +Accents | 43.9% (-0.9pp) | **59.7%** (-11.4pp) | 29.8% (-18.4pp) | 44.4% (-10.2pp) |
| +Behavior | 33.3% (-11.4pp) | **57.0%** (-14.0pp) | 51.8% (+3.5pp) | 47.4% (-7.3pp) |
| Realistic | 29.8% (-14.9pp) | **44.7%** (-26.3pp) | 38.6% (-9.6pp) | 37.7% (-17.0pp) |

### Comparison of single-factor deltas (old → new)

| Factor | Google (old→new) | OpenAI (old model → gpt-1.5) | xAI (old→new) | Avg (old→new) |
|--------|-----------------|------------------------------|--------------|--------------|
| Audio | -1.8pp → **-4.4pp** | -13.2pp → **-4.4pp** | -12.3pp → **-1.8pp** | -9.1pp → -3.5pp |
| Accents | -2.6pp → **-0.9pp** | -18.4pp → **-11.4pp** | -18.4pp → **-18.4pp** | -13.2pp → **-10.2pp** |
| Behavior | -0.9pp → **-11.4pp** | -8.8pp → **-14.0pp** | -5.3pp → **+3.5pp** | -5.0pp → **-7.3pp** |
| Realistic | -11.4pp → **-14.9pp** | -23.7pp → **-26.3pp** | -21.9pp → **-9.6pp** | -19.0pp → -17.0pp |

### Changes from intermediate results (Google only)

The Google ablation results changed dramatically from the intermediate analysis:

| Condition | Intermediate Google | Final Google | Δ |
|-----------|-------------------|-------------|---|
| Control | 38.6% | **44.7%** | +6.1pp |
| +Audio delta | -3.5pp | -4.4pp | -0.9pp worse |
| **+Accents delta** | **+7.0pp** | **-0.9pp** | **Flipped from positive to negative** |
| **+Behavior delta** | **+2.6pp** | **-11.4pp** | **Flipped from positive to large negative** |
| Realistic delta | -10.5pp | -14.9pp | -4.4pp worse |

The intermediate result had Google *improving* with accents (+7pp) and behaviors (+2.6pp), which was a striking anomaly. In the final data, Google is hurt by both — especially behavior (-11.4pp), which is now Google's worst single factor.

### Expected vs actual ordering

The intuitive expectation is **control ≥ single-factor ablations ≥ realistic** (adding complexity should only hurt). This holds on average, but breaks down for individual models:

| Model | Monotonic? | Violations |
|-------|-----------|------------|
| **gpt-1.5** | **Yes** | None. Clean ordering: control (71.1%) > audio (66.7%) > accents (59.7%) > behavior (57.0%) > realistic (44.7%) |
| **Google** | **Mostly yes** | Accents is nearly flat (-0.9pp). All three individual factors degrade performance, but **behavior (-11.4pp) is disproportionately damaging**. |
| **xAI** | **No** | **Behavior exceeds control** (+3.5pp). Also **realistic (38.6%) > accents-only (29.8%)** — the full combination of all factors produces *better* results than accents alone. |

Counter-intuitive patterns in detail:
- **xAI: realistic > accents-only**: Accents alone devastate xAI (-18.4pp), but adding audio and behavior factors on top partially *compensates*, bringing realistic (38.6%) well above accents-only (29.8%). This suggests audio degradation and user behaviors may mask or soften the accent effect for xAI.
- **xAI with behavior**: xAI improves with user behaviors (+3.5pp). Interruptions, backchannels, and non-directed speech may paradoxically give the agent more time or contextual cues.
- **Google behavior vulnerability**: Google is now severely hurt by behaviors (-11.4pp), making it the most vulnerable provider to user behaviors — a reversal from the intermediate data where Google improved.

### Additivity analysis

Are the combined effects of all factors equal to the sum of individual effects?

| Model | Sum of individual deltas | Actual realistic delta | Interaction |
|-------|-------------------------|----------------------|-------------|
| Google | **-16.7pp** | **-14.9pp** | Slightly sub-additive — combined is 1.8pp less bad than sum |
| gpt-1.5 | -29.8pp | -26.3pp | Slightly sub-additive — combined is 3.5pp less bad than sum |
| xAI | -16.7pp | -9.6pp | **Massively sub-additive** — combined is 7.1pp less bad than sum (accents damage partially offset by other factors) |
| **All avg** | -21.0pp | -17.0pp | Sub-additive on average |

The extreme case is **xAI** (factors individually devastate via accents, but combine more mildly). Google is now slightly sub-additive (was massively super-additive in the intermediate data where factors individually helped but combined they hurt).

**Key findings:**
- **Accents are the worst single factor on average** (-10.2pp), driven overwhelmingly by xAI (-18.4pp). Google is nearly unaffected (-0.9pp) and gpt-1.5 loses moderately (-11.4pp).
- **Behavior is the second most damaging factor** (-7.3pp average), with Google (-11.4pp) and gpt-1.5 (-14.0pp) severely hurt while xAI improves (+3.5pp).
- **Audio is the smallest and most uniform factor** (-3.5pp average, 1.8–4.4pp range). xAI is least affected by noise (-1.8pp).
- **gpt-1.5 has the largest Realistic degradation** (-26.3pp) despite having the highest absolute scores. This suggests the model's exceptional Clean performance is particularly vulnerable to speech complexity.
- **xAI's Realistic degradation halved** (-21.9pp → -9.6pp), mainly from improved audio robustness. Accent vulnerability persists (-18.4pp).
- **Only gpt-1.5 follows the expected monotonic pattern**; Google and xAI do not. The non-monotonicity is model-specific, not universal.
- **Google's ablation profile changed dramatically** from the intermediate results: accents and behavior effects both flipped sign. The "Google benefits from accents" finding did not replicate.

---

## 6. Impact on Paper Narrative

### Claims that still hold
- **A large voice-text gap remains**: Against GPT-5, the gap is 46–59pp. Against GPT-4.1, it is 16–29pp. Either way, voice substantially lags text.
- **Realistic conditions degrade performance**: Clean→Realistic drops range from 5pp (Google) to 14pp (gpt-1.5). Google's degradation is now -4.9pp (-16% relative), with a 1.7× robustness advantage over others.
- **No provider masters both task completion and conversational dynamics**: True — OpenAI gpt-1.5 has the best dynamics but worst selectivity (6%).
- **xAI leads in both Clean and Realistic**: 50.7% Clean, 38.3% Realistic.
- **xAI dominates Telecom**: 57.9% Clean, 40.4% Realistic vs 20–28% for others.
- **Accents are the most damaging single factor on average** (-10.2pp), overwhelmingly an xAI problem (-18pp).

### Claims that need significant revision

| Old Claim | New Reality |
|-----------|-------------|
| "19–30% under realistic conditions" | Now **26–38%** (wider range, higher ceiling) |
| "50–61pp gap from text [SOTA]" | Against GPT-5: **46–59pp** (narrowed for OpenAI/xAI, widened for Google). |
| "OpenAI at 19% Realistic (worst)" | gpt-1.5 now at **35.3%** — second best, near xAI. |
| "Google shows smallest Clean→Realistic degradation (-4pp)" | Still smallest but larger: **-4.9pp** (was -4.8pp old paper, -4.3pp intermediate). Relative: -16%. |
| "Google benefits from accents (+7pp)" | **No longer true.** Google accents delta is -0.9pp (essentially flat). This was an artifact of the intermediate data. |
| "Google and xAI improve with behaviors" | **Only xAI improves (+3.5pp)**. Google is now *severely hurt* by behaviors (-11.4pp). |
| "Google individual factors sum to +6pp (super-additive)" | Sum is now **-16.7pp** (slightly sub-additive). The "striking super-additive" story is gone. |
| "OpenAI slowest latency (2.22s)" | Now **fastest at 0.90s** |
| "OpenAI highest selectivity (75%)" | Now **worst selectivity (6%)** — responds to everything |
| "Accents -8pp on average" | Now **-10pp on average** |
| "Behavior -3pp on average" | Now **-7pp on average** |

### Provider characterization

- **Google** = lowest absolute scores (~26–31%) but most robust to degradation (-4.9pp, -16% relative). Neutral to accents (-0.9pp), severely hurt by user behaviors (-11.4pp). Balanced conversational dynamics: lowest interrupt (21%), reasonable latency (1.14s), moderate selectivity (54%), but lowest responsiveness (69%).
- **OpenAI gpt-1.5** = near-perfect responsiveness (100%), sub-1s latency, 49.0% Clean (near-xAI), but near-zero selectivity (6%). Responds to essentially all audio input. The complete inversion of the old model's cautious/selective behavior. Highest Clean in retail (71.1%) but also largest degradation (-26.3pp).
- **xAI** = best task completion (50.7% Clean, 38.3% Realistic) but extreme accent vulnerability (-18.4pp, -38% relative). Improved audio/behavior robustness. Highest interrupt rate (84%). Dominates telecom; exceeds text baseline there.

### Key tensions for the paper

1. **The OpenAI selectivity paradox**: gpt-1.5 responds to nearly everything (98% backchannels, 95% vocal tics, 90% non-directed speech) yet achieves top-tier task completion. This "respond to everything" strategy appears surprisingly effective for task completion while being poor conversational behavior.

2. **Accent vulnerability is provider-specific**: xAI is devastated (-18pp, -38% relative), Google is nearly unaffected (-0.9pp), gpt-1.5 is moderate (-11.4pp). Cannot frame accents as a universal problem.

3. **gpt-1.5's vulnerability paradox**: The strongest model in Clean (71.1% retail) has the largest degradation (-26.3pp retail). Being better at Clean doesn't protect against — and may amplify — speech complexity effects.

4. **Google's behavior vulnerability**: Google is now the provider most hurt by user behaviors (-11.4pp, -26% relative). This is a notable finding since Google is otherwise the most robust provider.

5. **Behavior is more damaging than previously thought**: Average -7pp (was -3pp in intermediate). User behaviors (interruptions, backchannels, non-directed speech) are the second most damaging factor, approaching accents (-10pp) in severity.
