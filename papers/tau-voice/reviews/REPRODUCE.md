# How to Reproduce τ-Voice Camera-Ready Results

This folder contains the stat sig artifacts shared with reviewers
(`pairwise_statsig_all_domains.md`).
Below are the exact commands to reproduce the figures, tables, and stat sig
results, filtered to `gpt-realtime-1.5` (not `gpt-realtime-2025-08-28`).

## Prerequisites

```bash
cd ~/code/tau2-bench-private
git checkout victorb/new-voice-runs
uv sync --extra dev --extra experiments
```

The analysis code only lives on `victorb/new-voice-runs` (commits `4d6aa7ed`
and `233d041b`). It is not on `main` or `dev/tau3`.

Raw data lives in `data/exp/final_voice_results/voice_trial{1,2}/` and
`data/exp/final_text_results/`. These are gitignored — only on local disk.

## 1. Full analysis pipeline (figures + tables)

Generates all paper-ready figures and LaTeX tables from raw simulation data.

```bash
uv run python -m experiments.tau_voice.exp.run_all_analysis \
    --data-dir data/exp/final_voice_results \
    --output-dir data/exp/final_voice_results_all_analysis
```

Runtime: ~25 min (18 min sim loading + 5 min performance + 2 min voice).

Outputs:
- `data/exp/final_voice_results_all_analysis/performance_analysis/` — CSVs and PDFs (pass@k, action success, auth, etc.)
- `data/exp/final_voice_results_all_analysis/voice_analysis/` — voice quality CSVs and PDFs (latency, interrupts, etc.)
- `data/exp/final_voice_results_all_analysis/paper/` — paper-ready `.tex`, `.csv`, `.pdf` files

### Filter to gpt-realtime-1.5 only

`run_all_analysis.py` does NOT have a model filter — it pools both OpenAI models
by provider. After running, post-filter the CSVs and rerun the `--paper`
step on the filtered data, or manually edit the generated tables.

The simplest filter is on the unified pass-k CSV:

```bash
python3 -c "
import pandas as pd
src = 'data/exp/final_voice_results_all_analysis/performance_analysis/pass_k_by_domain/pass_k_by_domain_raw.csv'
df = pd.read_csv(src)
df = df[df['llm'] != 'openai:gpt-realtime-2025-08-28']
df.to_csv(src.replace('.csv', '_15only.csv'), index=False)
"
```

Then regenerate just the paper tables from the filtered CSV — or, easier,
filter at the raw-data level by excluding `*_openai_gpt-realtime-2025-08-28/`
folders before passing `--data-dir`.

### Useful flags

| Flag | Purpose |
|---|---|
| `--plots-only` | Regenerate plots from existing CSVs (skip sim loading) |
| `--paper` | Generate only the paper-ready outputs from existing CSVs |
| `--copy-to-paper PATH` | Copy `.tex`/`.csv`/`.pdf` files to e.g. `papers/tau-voice/results/` |
| `--performance-only` / `--voice-only` | Restrict to one analysis type |
| `--clean` | Wipe output dirs before running |

## 2. Stat sig (pairwise permutation tests)

Generates pairwise paired-permutation-test results across all speech complexity
conditions and text baselines, per (domain, provider).

### Step 1: Run full pipeline to build the unified CSV

```bash
uv run python -m experiments.tau_voice.exp.speech_complexity_statsig \
    --voice-dirs data/exp/final_voice_results/voice_trial1 \
                 data/exp/final_voice_results/voice_trial2 \
    --text-dir data/exp/final_text_results \
    --output-dir data/exp/statsig_camera_ready
```

Runtime: ~13 min (data loading dominates).

This writes `unified_voice_text_raw.csv` containing per-sim rows for both
OpenAI models. The `speech_complexity_pairwise_statsig.{md,csv}` and
`pairwise_statsig_all_domains.md` outputs at this point will pool both OpenAI
models together.

### Step 2: Filter to gpt-realtime-1.5 only and re-run

```bash
python3 -c "
import pandas as pd
df = pd.read_csv('data/exp/statsig_camera_ready/unified_voice_text_raw.csv')
df[df['llm'] != 'openai:gpt-realtime-2025-08-28'].to_csv(
    'data/exp/statsig_camera_ready_15/unified_voice_text_raw_15only.csv',
    index=False,
)
"

mkdir -p data/exp/statsig_camera_ready_15

uv run python -m experiments.tau_voice.exp.speech_complexity_statsig \
    --input data/exp/statsig_camera_ready_15/unified_voice_text_raw_15only.csv \
    --output-dir data/exp/statsig_camera_ready_15
```

Runtime: ~10 sec (no data loading; pure stat compute).

Outputs:
- `speech_complexity_pairwise_statsig.md` — full pairwise table per (domain, provider)
- `speech_complexity_pairwise_statsig.csv` — same data, machine-readable
- `pairwise_statsig_all_domains.md` — condensed summary table per domain (this matches `data/exp/reviews/pairwise_statsig_all_domains.md`)

### Verifying reproduction

```bash
diff data/exp/statsig_camera_ready_15/speech_complexity_pairwise_statsig.md \
     data/exp/statsig_output3/speech_complexity_pairwise_statsig.md
# Expected: empty (byte-identical)

diff data/exp/statsig_camera_ready_15/pairwise_statsig_all_domains.md \
     data/exp/reviews/pairwise_statsig_all_domains.md
# Expected: only the manually-appended "Paper Text" commentary at the end
# of the reviewer file (lines 82–108). The tables (lines 1–81) are identical.
```

## Notes

- **Why we exclude `gpt-realtime-2025-08-28`**: it is the original ICML
  submission model. The revised paper (arXiv and camera-ready) uses
  `gpt-realtime-1.5`. Mixing them pools two different models under the
  "OpenAI" label and changes rates by ~6–8pp.
- **Why we keep both in the raw data**: pre-vs-post comparisons in some
  ablations and supplementary analyses.
- **Reviewer artifacts**: `data/exp/reviews/pairwise_statsig_all_domains.md` is
  byte-identical to `data/exp/statsig_output3/pairwise_statsig_all_domains.md`
  (the Mar 27 run).
