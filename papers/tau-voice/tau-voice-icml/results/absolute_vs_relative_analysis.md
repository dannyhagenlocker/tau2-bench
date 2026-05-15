# Absolute vs Relative Impact Analysis

This document examines how absolute (pp) and relative (%) deltas tell different stories about the impact of speech complexity on voice agent performance.

**Definitions:**
- **Absolute delta**: `regular − control` (in percentage points). How many raw percentage points are gained or lost.
- **Relative delta**: `(regular − control) / control` (as %). What fraction of the Clean score is lost. A model at 60% that drops to 45% has an absolute delta of -15pp but a relative delta of -25%.

Relative deltas correct for baseline differences: a 10pp drop from 20% (-50% relative) is proportionally far more severe than a 10pp drop from 60% (-17% relative).

---

## 1. Clean → Realistic Degradation

### Overall (All domains)

| Provider | Model | Clean | Realistic | Abs. Δ | **Rel. Δ** |
|----------|-------|-------|-----------|--------|------------|
| Google | gemini | 30.7% | 25.8% | -4.9pp | **-16.7%** |
| OpenAI | gpt-1.5 | 49.0% | 35.3% | -13.8pp | **-28.1%** |
| xAI | xai-realtime | 50.7% | 38.3% | -12.4pp | **-24.4%** |

**What absolute deltas say:** Google is the most robust (-4.9pp), with xAI and gpt-1.5 tied for worst (~-13pp). A 2.6× gap separates Google from the other two.

**What relative deltas say:** The gap narrows. Google still leads at -16.7%, but **the difference between Google and the others is a 1.5× factor, not 2.6×**. gpt-1.5 (-28.1%) and xAI (-24.4%) both lose about a quarter of their Clean performance — but relative to their higher baselines (49–51% vs Google's 31%), the proportional impact is less extreme than the absolute numbers suggest.

**Impact on the story:** Google is genuinely the most robust by both measures. But the absolute framing overstates the gap: Google's small absolute delta is partly an artifact of having less to lose. The more honest framing is "Google loses one-sixth, others lose one-quarter." The robustness advantage is real but is ~1.5× rather than ~2.6×.

**Change from intermediate:** Google's relative delta improved from -14.9% to -16.7% after the telecom rerun and retail fix (its Clean baseline rose from 29% to 31%, its Realistic delta grew from -4.3pp to -4.9pp). The robustness advantage narrowed slightly from 2× (15% vs 26–28%) to ~1.5× (17% vs 24–28%).

### Per domain

| Domain | Model | Clean | Abs. Δ | **Rel. Δ** | Abs. rank | **Rel. rank** |
|--------|-------|-------|--------|------------|-----------|---------------|
| **Retail** | Google | 44.7% | -14.9pp | -33.3% | 2nd | 2nd |
| | gpt-1.5 | 71.1% | -26.3pp | -37.0% | 3rd (worst) | 3rd (worst) |
| | xAI | 48.2% | -9.6pp | -20.0% | 1st (best) | 1st (best) |
| **Airline** | Google | 28.0% | +2.0pp | +7.1% | 1st | 1st |
| | gpt-1.5 | 48.0% | -8.0pp | -16.7% | 2nd | 2nd |
| | xAI | 46.0% | -10.0pp | -21.7% | 3rd | 3rd |
| **Telecom** | Google | 20.2% | -2.6pp | -13.0% | 1st (best) | 1st (best) |
| | gpt-1.5 | 28.1% | -7.0pp | -25.0% | 2nd | 2nd |
| | xAI | 57.9% | -17.5pp | -30.3% | 3rd (worst) | 3rd (worst) |

**Key observations:**

1. **Retail: rankings agree.** Both absolute and relative agree: xAI is most robust (-9.6pp, -20.0%), gpt-1.5 is worst (-26.3pp, -37.0%), Google is in the middle (-14.9pp, -33.3%). No ranking flip in retail after the fix.

2. **Retail: xAI is most robust by both measures** (-9.6pp absolute, -20.0% relative). gpt-1.5 is worst by both measures — its massive 26.3pp absolute drop is also the largest proportional loss (-37.0%), losing over a third of its Clean capability.

3. **Telecom: Google is genuinely robust.** Google's small absolute delta (-2.6pp) keeps it at #1 in robustness, and relatively (-13.0%) the gap to gpt-1.5 (-25.0%) is nearly 2×. Unlike the previous analysis where Google's 21.7% relative loss was "not far" from others, the telecom rerun shows Google's telecom robustness is genuine, not merely an artifact of having little to lose.

4. **Google's retail vulnerability.** Google's retail delta is -14.9pp (-33.3% relative) — 2nd place by both measures. Google's improved retail Clean (39%→44.7%) came with larger degradation after the retail task fix.

---

## 2. Voice vs Text Gap

### Against text\_sota (GPT-5)

| Provider | Model | Text | Voice (Realistic) | Abs. gap | **Rel. gap** | **Voice retains** |
|----------|-------|------|-------------------|----------|-------------|-------------------|
| Google | gemini | 84.7% | 25.8% | -58.9pp | -69.5% | **30.5%** |
| OpenAI | gpt-1.5 | 84.7% | 35.3% | -49.4pp | -58.3% | **41.6%** |
| xAI | xai-realtime | 84.7% | 38.3% | -46.4pp | -54.8% | **45.2%** |

**What absolute deltas say:** The gap ranges from 46–59pp. Google has the largest gap, xAI the smallest, OpenAI in between.

**What relative deltas say:** The same ranking, expressed more intuitively as "what fraction of text capability survives in voice":
- **xAI retains 45.2%** of text SOTA performance
- **OpenAI gpt-1.5 retains 41.6%**
- **Google retains only 30.5%** — less than a third

**Impact on the story:** The relative framing is more intuitive and more damning. Saying "voice agents retain 30–45% of text capability" is a clearer message than "the gap is 46–59pp." It also makes the provider spread more vivid: xAI keeps nearly half of text performance, Google less than a third.

**Change from intermediate:** Google retains slightly more (29.1%→30.5%) due to improved retail Realistic and telecom rerun. The overall range shifts from "29–45%" to "30–45%".

### Per domain — what voice retains (% of text SOTA)

| Domain | Google | gpt-1.5 | xAI |
|--------|--------|---------|-----|
| Retail | **36.8%** | **55.2%** | **47.6%** |
| Airline | 36.1% | **48.2%** | 43.4% |
| Telecom | **19.5%** | 23.4% | **44.8%** |

- **gpt-1.5 retains the most in retail (55.2%)** — over half of text capability survives voice. This is by far the best voice-to-text ratio in the benchmark.
- **Telecom is where voice fails hardest**: Google retains only 19.5% of text capability. Even xAI, the telecom leader, retains less than half (44.8%).
- **xAI is the most consistent across domains**: retains 43–48% everywhere. Other models vary wildly (Google: 19–37%, gpt-1.5: 23–55%).
- **Google improved in retail** (34.7%→36.8%) and telecom (17.5%→19.5%) due to higher Realistic scores.

---

## 3. Ablation (Retail)

### Absolute vs relative single-factor deltas

| Factor | | Google | gpt-1.5 | xAI | Avg |
|--------|---|--------|---------|-----|-----|
| **Audio** | Abs. | -4.4pp | -4.4pp | -1.8pp | -3.5pp |
| | **Rel.** | **-9.8%** | **-6.2%** | **-3.6%** | **-6.5%** |
| **Accents** | Abs. | -0.9pp | -11.4pp | -18.4pp | -10.2pp |
| | **Rel.** | **-2.0%** | **-16.0%** | **-38.2%** | **-18.7%** |
| **Behavior** | Abs. | -11.4pp | -14.0pp | +3.5pp | -7.3pp |
| | **Rel.** | **-25.5%** | **-19.8%** | **+7.3%** | **-12.7%** |
| **Realistic** | Abs. | -14.9pp | -26.3pp | -9.6pp | -16.9pp |
| | **Rel.** | **-33.3%** | **-37.0%** | **-20.0%** | **-30.1%** |

**Key insights from relative deltas:**

1. **xAI's accent vulnerability is staggering**: -38.2% relative — accents alone wipe out **nearly two-fifths** of xAI's Clean capability. This is by far the largest single-factor relative impact in the entire ablation. In absolute terms (-18.4pp), it was already the worst, but the relative framing makes the severity more vivid.

2. **Google's behavior vulnerability is the second-largest relative impact**: -25.5% — over a quarter of Google's Clean capability lost from user behaviors alone. In absolute terms (-11.4pp) this is already severe, and relatively it's worse than gpt-1.5's -19.8%.

3. **gpt-1.5's behavior vulnerability stands out**: -19.8% relative. In absolute terms (-14.0pp) it's the worst, but relatively Google is worse (-25.5%). This is because Google's lower Clean baseline (44.7% vs 71.1%) amplifies the proportional impact.

4. **Audio is the most variable factor**: Google (-9.8%) and gpt-1.5 (-6.2%) lose 6–10% of Clean from audio, while xAI loses only 3.6%. Absolute deltas range from -1.8pp (xAI) to -4.4pp (Google, gpt-1.5). Audio impact is modest but more provider-dependent than before.

5. **Accents are nearly invisible for Google**: -2.0% relative, essentially noise. This contrasts sharply with the intermediate results where Google *gained* 18.2%. The final data shows Google is simply neutral to accents, not helped by them.

6. **Behavior is the most polarized factor**: Google (-25.5%) and gpt-1.5 (-19.8%) are severely hurt, while xAI gains (+7.3%). This two-against-one split — two models devastated, one model improved — makes behavior the most provider-dependent factor.

**Change from intermediate:** The relative deltas for Google shifted dramatically:
- Accents: +18.2% → **-2.0%** (was Google's best condition, now neutral)
- Behavior: +6.8% → **-25.5%** (was mild help, now severe hurt)
- Audio: -9.1% → -9.8% (similar)
- Realistic: -27.3% → -33.3% (worse)

---

## 4. Summary: How Relative Deltas Change the Narrative

| Narrative claim (absolute) | Relative delta revision |
|---------------------------|------------------------|
| **"Google is the most robust model (-4.9pp)"** | True, and the advantage is substantial. Google loses 16.7% vs 24–28% for others — a **1.5× gap, not 2.6×**. Part of Google's small absolute delta is having less to lose, but the relative advantage is genuine. |
| **"gpt-1.5 and xAI are equally vulnerable (~-13pp)"** | Not quite: xAI is more robust relatively (-24.4% vs -28.1%). But the difference is small — both lose about a quarter. |
| **"gpt-1.5 has the worst Realistic degradation (-26.3pp retail)"** | Confirmed in both measures: -37.0% relative is also worst. High baseline does not protect gpt-1.5. |
| **"xAI has the worst accent impact (-18.4pp)"** | Even more dramatic: **-38.2% relative**, wiping out nearly two-fifths of Clean capability. The proportional severity exceeds the absolute impression. |
| **"Google is most hurt by behavior (-11.4pp)"** | Confirmed and even starker relatively: **-25.5%** — Google loses over a quarter of its Clean score from behaviors. This is a bigger proportional hit than gpt-1.5's -19.8%, despite gpt-1.5's larger absolute loss (-14.0pp). |
| **"The voice-text gap is 46–59pp"** | Voice retains **30–45% of text capability**. More intuitive framing. xAI keeps nearly half; Google less than a third. |
| **"Google is most robust in telecom (-2.6pp)"** | True both absolutely and relatively. Google's 13.0% relative loss is far below gpt-1.5's 25.0% — a nearly 2× robustness advantage. The telecom rerun confirms Google's genuine robustness here. |
| **"Degradation ranges from 5–13pp across providers"** | Proportionally, it ranges from **17–28%** — Google loses one-sixth, others lose one-quarter of their Clean performance. |
| **"Retail: xAI is best (-9.6pp), gpt-1.5 worst (-26.3pp)"** | Rankings agree: xAI best (-20.0%), gpt-1.5 worst (-37.0%), Google in the middle (-33.3%). No ranking flip after the retail fix. |

### Key finding: rankings agree across domains

With the final data after the retail fix, absolute and relative rankings **agree in all domains**: xAI is most robust in retail (-9.6pp, -20.0%), gpt-1.5 is worst (-26.3pp, -37.0%), and Google is in the middle (-14.9pp, -33.3%). No ranking flip — both measures tell the same story.

### Recommended framing

The paper should present both absolute and relative deltas, as they answer different questions:

- **Absolute deltas** answer: "How many tasks flip from pass to fail?" — relevant for practical deployment impact.
- **Relative deltas** answer: "What fraction of capability is lost?" — relevant for understanding model robustness independent of baseline.

Key claims that should use relative deltas:
- Provider robustness comparisons (clarifies that Google's advantage is ~1.5×, not ~2.5×)
- Accent vulnerability severity (38% for xAI is more impactful than -18.4pp)
- Voice-text gap framing ("retains X% of text capability")
- Behavior vulnerability (Google's -25.5% is proportionally worse than gpt-1.5's -19.8%)
- xAI cross-domain consistency (retains 43–48% everywhere)

Key claims that should use absolute deltas:
- Overall Realistic score ranges ("26–38% under realistic conditions")
- Task-count interpretations ("14 more tasks fail under Realistic" for Google)
- Rankings by final Realistic performance (absolute scores determine real-world capability)
- gpt-1.5's retail dominance (71.1% Clean, 44.7% Realistic — absolute numbers tell the success story)
