# Speech Complexity — Pairwise Statistical Significance

Paired permutation test (100k permutations) on per-task mean success rates, paired by `task_id`. P-values are Holm-Bonferroni corrected within each (domain, provider) group. Fisher's exact test (unpaired) shown for reference.

## Voice Pairwise Comparisons

### Retail — GEMINI

| Condition A | Condition B | Rate A | Rate B | Δ (pp) | 95% CI Δ (pp) | Perm p (adj) | Fisher p (adj) | Sig |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| Control (Clean) | Control (Audio) | 42.1% | 37.7% | -4.4 | [-11.4, +3.5] – | 0.939 | 1.000 |  |
| Control (Clean) | Control (Accents) | 42.1% | 44.7% | +2.6 | [-5.3, +11.4] – | 1.000 | 1.000 |  |
| Control (Clean) | Control (Behavior) | 42.1% | 37.3% | -4.8 | [-11.8, +2.6] – | 0.939 | 1.000 |  |
| Control (Clean) | Regular (Realistic) | 42.1% | 28.9% | -13.2 | [-21.1, -4.4] ↓ | 0.026 | 0.040 | \*\*\* |
| Control (Audio) | Control (Accents) | 37.7% | 44.7% | +7.0 | [-0.0, +14.9] – | 0.469 | 0.767 |  |
| Control (Audio) | Control (Behavior) | 37.7% | 37.3% | -0.4 | [-7.5, +7.5] – | 1.000 | 1.000 |  |
| Control (Audio) | Regular (Realistic) | 37.7% | 28.9% | -8.8 | [-17.1, -0.0] – | 0.452 | 0.471 |  |
| Control (Accents) | Control (Behavior) | 44.7% | 37.3% | -7.5 | [-14.5, +0.9] – | 0.452 | 0.765 |  |
| Control (Accents) | Regular (Realistic) | 44.7% | 28.9% | -15.8 | [-22.8, -8.3] ↓ | 0.0014 | 0.0066 | \*\*\* |
| Control (Behavior) | Regular (Realistic) | 37.3% | 28.9% | -8.3 | [-16.2, +0.4] – | 0.452 | 0.512 |  |

### Retail — OPENAI

| Condition A | Condition B | Rate A | Rate B | Δ (pp) | 95% CI Δ (pp) | Perm p (adj) | Fisher p (adj) | Sig |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| Control (Clean) | Control (Audio) | 67.5% | 60.1% | -7.5 | [-14.9, +0.9] – | 0.318 | 0.475 |  |
| Control (Clean) | Control (Accents) | 67.5% | 64.5% | -3.1 | [-10.1, +4.8] – | 0.863 | 1.000 |  |
| Control (Clean) | Control (Behavior) | 67.5% | 56.1% | -11.4 | [-17.5, -4.4] ↓ | 0.013 | 0.095 | \*\*\* |
| Control (Clean) | Regular (Realistic) | 67.5% | 43.0% | -24.6 | [-31.6, -16.2] ↓ | 0.0e+00 | 1.9e-06 | \*\*\* |
| Control (Audio) | Control (Accents) | 60.1% | 64.5% | +4.4 | [-2.6, +11.8] – | 0.863 | 1.000 |  |
| Control (Audio) | Control (Behavior) | 60.1% | 56.1% | -3.9 | [-10.5, +3.5] – | 0.863 | 1.000 |  |
| Control (Audio) | Regular (Realistic) | 60.1% | 43.0% | -17.1 | [-24.1, -8.8] ↓ | 2.4e-04 | 0.0029 | \*\*\* |
| Control (Accents) | Control (Behavior) | 64.5% | 56.1% | -8.3 | [-14.9, -0.9] ↓ | 0.158 | 0.424 |  |
| Control (Accents) | Regular (Realistic) | 64.5% | 43.0% | -21.5 | [-28.9, -13.2] ↓ | 0.0e+00 | 5.4e-05 | \*\*\* |
| Control (Behavior) | Regular (Realistic) | 56.1% | 43.0% | -13.2 | [-20.6, -5.3] ↓ | 0.013 | 0.046 | \*\*\* |

### Retail — XAI

| Condition A | Condition B | Rate A | Rate B | Δ (pp) | 95% CI Δ (pp) | Perm p (adj) | Fisher p (adj) | Sig |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| Control (Clean) | Control (Audio) | 50.0% | 46.1% | -3.9 | [-11.4, +4.4] – | 1.000 | 1.000 |  |
| Control (Clean) | Control (Accents) | 50.0% | 31.1% | -18.9 | [-27.2, -10.1] ↓ | 6.0e-04 | 5.9e-04 | \*\*\* |
| Control (Clean) | Control (Behavior) | 50.0% | 49.1% | -0.9 | [-8.3, +7.9] – | 1.000 | 1.000 |  |
| Control (Clean) | Regular (Realistic) | 50.0% | 36.8% | -13.2 | [-21.9, -3.9] ↓ | 0.044 | 0.043 | \*\*\* |
| Control (Audio) | Control (Accents) | 46.1% | 31.1% | -14.9 | [-22.8, -6.1] ↓ | 0.0061 | 0.012 | \*\*\* |
| Control (Audio) | Control (Behavior) | 46.1% | 49.1% | +3.1 | [-4.4, +11.8] – | 1.000 | 1.000 |  |
| Control (Audio) | Regular (Realistic) | 46.1% | 36.8% | -9.2 | [-17.5, -0.4] ↓ | 0.216 | 0.286 |  |
| Control (Accents) | Control (Behavior) | 31.1% | 49.1% | +18.0 | [+9.2, +27.6] ↑ | 0.0027 | 0.0011 | \*\*\* |
| Control (Accents) | Regular (Realistic) | 31.1% | 36.8% | +5.7 | [-3.1, +14.5] – | 1.000 | 0.942 |  |
| Control (Behavior) | Regular (Realistic) | 49.1% | 36.8% | -12.3 | [-20.6, -3.1] ↓ | 0.045 | 0.063 | \*\*\* |

## Text vs Voice Comparisons

### Retail — voice provider: GEMINI

| Condition A | Condition B | Rate A | Rate B | Δ (pp) | 95% CI Δ (pp) | Perm p (adj) | Fisher p (adj) | Sig |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| Text (Non-Reasoning) | Control (Clean) | 76.3% | 42.1% | -34.2 | [-41.4, -26.5] ↓ | 0.0e+00 | 5.0e-18 | \*\*\* |
| Text (Non-Reasoning) | Control (Audio) | 76.3% | 37.7% | -38.6 | [-45.8, -30.7] ↓ | 0.0e+00 | 4.5e-22 | \*\*\* |
| Text (Non-Reasoning) | Control (Accents) | 76.3% | 44.7% | -31.6 | [-38.8, -23.7] ↓ | 0.0e+00 | 6.6e-16 | \*\*\* |
| Text (Non-Reasoning) | Control (Behavior) | 76.3% | 37.3% | -39.0 | [-46.1, -31.6] ↓ | 0.0e+00 | 2.2e-22 | \*\*\* |
| Text (Non-Reasoning) | Regular (Realistic) | 76.3% | 28.9% | -47.4 | [-55.0, -38.6] ↓ | 0.0e+00 | 4.8e-32 | \*\*\* |
| Text (Reasoning) | Control (Clean) | 81.6% | 42.1% | -39.5 | [-46.7, -31.1] ↓ | 0.0e+00 | 3.5e-24 | \*\*\* |
| Text (Reasoning) | Control (Audio) | 81.6% | 37.7% | -43.9 | [-51.1, -35.5] ↓ | 0.0e+00 | 5.1e-29 | \*\*\* |
| Text (Reasoning) | Control (Accents) | 81.6% | 44.7% | -36.8 | [-44.3, -28.9] ↓ | 0.0e+00 | 1.2e-21 | \*\*\* |
| Text (Reasoning) | Control (Behavior) | 81.6% | 37.3% | -44.3 | [-51.5, -36.4] ↓ | 0.0e+00 | 2.2e-29 | \*\*\* |
| Text (Reasoning) | Regular (Realistic) | 81.6% | 28.9% | -52.6 | [-59.6, -44.3] ↓ | 0.0e+00 | 1.9e-40 | \*\*\* |

### Retail — voice provider: OPENAI

| Condition A | Condition B | Rate A | Rate B | Δ (pp) | 95% CI Δ (pp) | Perm p (adj) | Fisher p (adj) | Sig |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| Text (Non-Reasoning) | Control (Clean) | 76.3% | 67.5% | -8.8 | [-16.4, -1.1] ↓ | 0.032 | 0.017 | \*\*\* |
| Text (Non-Reasoning) | Control (Audio) | 76.3% | 60.1% | -16.2 | [-24.1, -7.9] ↓ | 8.8e-04 | 6.6e-05 | \*\*\* |
| Text (Non-Reasoning) | Control (Accents) | 76.3% | 64.5% | -11.8 | [-19.5, -3.3] ↓ | 0.012 | 0.0029 | \*\*\* |
| Text (Non-Reasoning) | Control (Behavior) | 76.3% | 56.1% | -20.2 | [-28.3, -11.0] ↓ | 6.0e-05 | 6.3e-07 | \*\*\* |
| Text (Non-Reasoning) | Regular (Realistic) | 76.3% | 43.0% | -33.3 | [-41.0, -24.8] ↓ | 0.0e+00 | 1.8e-16 | \*\*\* |
| Text (Reasoning) | Control (Clean) | 81.6% | 67.5% | -14.0 | [-21.1, -6.4] ↓ | 9.3e-04 | 2.2e-04 | \*\*\* |
| Text (Reasoning) | Control (Audio) | 81.6% | 60.1% | -21.5 | [-29.1, -13.2] ↓ | 0.0e+00 | 2.2e-08 | \*\*\* |
| Text (Reasoning) | Control (Accents) | 81.6% | 64.5% | -17.1 | [-24.6, -8.8] ↓ | 4.5e-04 | 8.8e-06 | \*\*\* |
| Text (Reasoning) | Control (Behavior) | 81.6% | 56.1% | -25.4 | [-32.9, -17.1] ↓ | 0.0e+00 | 4.9e-11 | \*\*\* |
| Text (Reasoning) | Regular (Realistic) | 81.6% | 43.0% | -38.6 | [-46.3, -30.3] ↓ | 0.0e+00 | 6.2e-23 | \*\*\* |

### Retail — voice provider: XAI

| Condition A | Condition B | Rate A | Rate B | Δ (pp) | 95% CI Δ (pp) | Perm p (adj) | Fisher p (adj) | Sig |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| Text (Non-Reasoning) | Control (Clean) | 76.3% | 50.0% | -26.3 | [-34.9, -17.3] ↓ | 0.0e+00 | 8.9e-12 | \*\*\* |
| Text (Non-Reasoning) | Control (Audio) | 76.3% | 46.1% | -30.3 | [-38.6, -21.1] ↓ | 0.0e+00 | 2.8e-14 | \*\*\* |
| Text (Non-Reasoning) | Control (Accents) | 76.3% | 31.1% | -45.2 | [-53.3, -36.3] ↓ | 0.0e+00 | 3.3e-29 | \*\*\* |
| Text (Non-Reasoning) | Control (Behavior) | 76.3% | 49.1% | -27.2 | [-35.5, -18.2] ↓ | 0.0e+00 | 5.1e-12 | \*\*\* |
| Text (Non-Reasoning) | Regular (Realistic) | 76.3% | 36.8% | -39.5 | [-47.8, -30.7] ↓ | 0.0e+00 | 1.2e-22 | \*\*\* |
| Text (Reasoning) | Control (Clean) | 81.6% | 50.0% | -31.6 | [-39.0, -23.2] ↓ | 0.0e+00 | 1.7e-16 | \*\*\* |
| Text (Reasoning) | Control (Audio) | 81.6% | 46.1% | -35.5 | [-43.2, -27.2] ↓ | 0.0e+00 | 6.0e-20 | \*\*\* |
| Text (Reasoning) | Control (Accents) | 81.6% | 31.1% | -50.4 | [-57.9, -42.3] ↓ | 0.0e+00 | 2.1e-37 | \*\*\* |
| Text (Reasoning) | Control (Behavior) | 81.6% | 49.1% | -32.5 | [-40.1, -24.1] ↓ | 0.0e+00 | 2.9e-17 | \*\*\* |
| Text (Reasoning) | Regular (Realistic) | 81.6% | 36.8% | -44.7 | [-52.6, -35.7] ↓ | 0.0e+00 | 4.6e-30 | \*\*\* |
