# τ-Voice ICML 2026 — Camera-Ready TODO

Working document tracking what we told reviewers we would do.
Source: `paper/reviews/Tau voice Reviews ICML 2026.docx`.

Acceptance: **Accept (regular)**, weak-accept consensus (one strong-accept, two weak-accepts, one outlier strong-reject from Reviewer macs).

The rebuttals broke down into three buckets:

- **A. Already in the updated/arXiv version** — improvements we presented as already done.
- **B. New results we generated for the rebuttal** — not yet integrated into the paper.
- **C. Explicit camera-ready commitments** — what we promised to add/update.

The actionable list for camera-ready work is in sections **B** and **C**.

---

## Workflow conventions (read first before editing)

**Working tree**: `paper/tau-voice/` (inside `/Users/victorbarres/code/tau2-bench-private/`).
**Branch**: `camera-ready`.
**Build**: from `paper/tau-voice/`, run `latexmk -pdf -g -interaction=nonstopmode -halt-on-error main.tex`. Use `-g` to force a rebuild after edits; latexmk will sometimes report "All targets up-to-date" even when sources changed.
**Verify**: after each substantive edit, build the PDF, then grep the log for unresolved labels or warnings. Don't commit if the build fails.

**Reviews + rebuttals (authoritative)**: `paper/reviews/Tau voice Reviews ICML 2026.docx`.
**Reproducible data + commands for stat sig**: `paper/reviews/REPRODUCE.md`.
**Staged data files** (already produced, ready to use): `paper/reviews/pairwise_statsig_all_domains.md` and friends.

**Tracked-edit macros** (defined in `main.tex`):
- `\new{...}` — red, new text
- `\old{...}` — blue strikethrough, removed text
- `\why{tag}` — green inline reviewer attribution (e.g. `\why{addresses beyN Q1}`)

Wrap every camera-ready edit in these macros so the diff is visible in the rendered PDF. Toggle `\revmarkstrue` → `\revmarksfalse` in `main.tex` to render a clean version with no markup. Don't ship the visible-diff version to ICML; the clean version is for the final upload.

**Commits**: small, atomic, on the `camera-ready` branch. One reviewer commitment per commit when possible. Match the style of recent commits (`git log --oneline` to see); typical pattern: `area: short summary (addresses reviewer reference)`.

**Things to never do**:
- Invent numbers. If a claim can't be substantiated from `data/` or `paper/reviews/`, stop and ask Victor.
- Use placeholder figures or `TODO` numbers in the rendered text.
- Widen scope across todo items in a single edit batch — each C-item should land as its own commit.
- Push without a clean build.

---

## A. Already in the updated (arXiv) version

These were communicated as done across all four rebuttals. No camera-ready action required beyond verifying they made it into the arXiv LaTeX.

- [x] Adopted 36 τ²-bench task fixes (18 retail, 18 airline) from the community audit / external PRs.
- [x] Updated to latest models. Most notably OpenAI `gpt-realtime-1.5` (Feb 2026) replacing the Aug 2025 model.
- [x] Updated headline results:
  - Google: 29% / 24% → 31% / 26%
  - OpenAI: 33% / 19% → 49% / 35%
  - xAI: 42% / 30% → 51% / 38%
  - GPT-5 text: 80% → 85%
- [x] Expanded qualitative error analysis from 40 sampled tasks to all 91 failed simulations.
- [x] Updated statistical methodology to paired permutation tests across all three domains (retail, airline, telecom) with Holm-Bonferroni correction. **Status**: methodology and appendix paragraph + tables both now report all three domains (combined + per-domain), matching what reviewers were told. Landed under **C6**.
- [x] Updated ablations + voice interaction quality numbers (latency, responsiveness, selectivity, turn-taking, noise).
- [x] Fixed Table 7 rounding inconsistencies (Reviewer beyN Q1).
- [x] Added reference to Figure 2 in the text (Reviewer beyN Q1).

> **Verification step**: confirm each of the above is reflected in the current arXiv LaTeX (the version on `dev/tau3` `cb0e12ef`, also at `~/code/tau-voice-paper/tau-voice/`). Spot-check Section 4.x tables, Section 5.2 error analysis, and Appendix stat sig.

---

## B. New results we generated for the rebuttal (NOT in arXiv yet)

These are concrete experiments / data we produced during the rebuttal period that should be folded into the camera-ready (or at least clearly documented).

### B1. Cascaded ASR→LLM→TTS pipeline
- **Setup**: Deepgram Nova-3 STT → GPT-4.1 → ElevenLabs TTS, via LiveKit, on Retail (114 tasks).
- **Numbers**: Clean 63.2%, Realistic 43.0%. Audio-native range was 45–71% Clean / 30–45% Realistic. GPT-4.1 text baseline was 76%.
- **Use**: Showed the voice-task gap is **not specific to end-to-end APIs** — same magnitude holds for cascaded pipelines.
- **What we said about the paper**: "We did not include this in the paper because one configuration cannot represent cascaded systems as a class." But we **committed to releasing the LiveKit integration code** so the community can extend.
- **Promised to**: Reviewer beyN (Q2), Reviewer macs (W4).

### B2. ASR-enabled user simulator evaluation
- **Setup**: User simulator perceives the agent's speech through ASR (the user simulator is on the receiving end of ASR), rather than reading the agent's native transcript directly.
- **Result**: All scores dropped (tasks harder, simulator less reliable with ASR noise). **The statistically significant findings held**: text-to-voice gap and clean-to-realistic degradation both still significant.
- **What we promised**: "We will include the full ASR-enabled results in a new appendix section in the camera-ready."
- **Promised to**: Reviewer beyN (follow-up), Reviewer vw95 (follow-up).

### B3. Human annotation study of simulator realism
- **Setup**: 2 annotators independently rated 60 simulations on a 1–4 scale.
- **Numbers**:
  - Overall mean: 3.1 / 4
  - 83% of ratings at 3 or above
  - Within-1 inter-rater agreement: 94%
  - Turn-taking naturalness: 3.1 / 4
  - Interruption behavior: 3.0 / 4
  - Backchannel naturalness: 3.5 / 4
  - Voice prosody: 2.6 / 4 (weakest)
- **Use**: Direct rebuttal to Reviewer macs Q3/Q4 ("how realistic is the simulator?", "could a strong LLM make the simulator unrealistically capable?").
- [x] **Status**: Added to camera-ready. Headline numbers folded into the §6.1 Simulator Fidelity paragraph (`contents/conclusion.tex`); full methodology + per-dimension table landed as new appendix subsection `Simulator Realism Validation` (`\label{app:simulator-realism}`, `appendix/additional_results.tex`). Honest caveat that prosody (2.6/4) is the weakest dimension is surfaced in both locations. A `\todo{verify sampling stratification}` is left in the appendix for Victor to confirm before the final clean render. Also reinforces our response to beyN's "simulator is more patient and capable than real callers" limitations point.

### B4. Refined error taxonomy on all 68 agent-attributable failures
- **Numbers**:
  - 7% policy-specific (5 / 68)
  - 38% spelling (names/emails)
  - 22% conversational grounding (confirming before irreversible actions, sharing relevant info)
  - 24% conversational honesty (claiming actions that weren't executed)
  - 6% multi-part request tracking
  - 3% arithmetic / self-consistency
- **Use**: Used in Reviewer vw95 W2 rebuttal to argue that 93% of agent-attributable failures reflect *domain-agnostic commonsense skills*, not policy knowledge.
- **Status**: Verify this exact breakdown is in arXiv Section 5.2. If not, add to camera-ready.

### B5. Audit of suggested open-source / full-duplex models
- **Models surveyed**: NTPP (ICML '25), LLaMA-Omni (ICLR '25), SALMONN-omni (NeurIPS '25), Moshi, PersonaPlex, MiniCPM-o 4.5, Qwen-Omni-Realtime.
- **Finding**: None currently support native tool calling. Only 4 of ~10 surveyed audio-native models support both realtime streaming and native tool calling: OpenAI Realtime, Gemini Live, xAI Voice Agent, Nova 2 Sonic. We evaluated 3 of 4 (skipped Nova as another closed-source provider).
- **Use**: Justifies the limited baseline set and reframes the contribution as evaluating **full-duplex voice agents** (with tool-calling) vs **full-duplex speech models** (without).

---

## C. Explicit camera-ready commitments

The actionable list for paper edits.

### C1. Framing & writing

- [x] **Reframe the benchmark explicitly** as a *controlled full-duplex voice interaction benchmark*, **not** a fully end-to-end deployed-agent benchmark. (Reviewer beyN follow-up.) — landed in `contents/intro.tex` line 26 ("extending \tautwobench{} to full-duplex voice interaction under controlled audio conditions").
- [x] **Section 3.1 (orchestrator)**: clarify default transcript-injection mode vs ASR-enabled mode for the user simulator. — landed in `methods/voice_user_simulator.tex` line 6.
- [x] **Section 6.1 (limitations)**:
  - [x] Make explicit that default config results represent an **upper bound on real-world performance** (due to transcript injection + TTS rather than human speech). — landed in `contents/conclusion.tex` line 12 (Transcript Injection paragraph).
  - [x] Note the ASR-enabled mode is available as a stricter end-to-end evaluation. — same paragraph.
- [x] **Emphasize tool-calling capability as the key inclusion criterion** for τ-Voice (Reviewer macs follow-up). — landed in `contents/experiments.tex` line 16 ("inclusion requires both realtime full-duplex audio *and* native tool calling"). Distinction between "full-duplex voice agents" and "full-duplex speech models" is implicit in this framing; explicitly naming the surveyed open-source models (NTPP / LLaMA-Omni / SALMONN-omni) is tracked as a separate item in **C7**.
- [x] **Clarify task construction in the introduction**: 278 tasks inherited from τ²-bench (114 retail, 50 airline, 114 telecom), each with gold-standard database state changes, with added voice-specific instructions on top. (Reviewer macs Q2.) — landed in `contents/experiments.tex` line 6.
- [x] **Expand Future Work section** with concrete directions (Reviewer v3yK W2): — landed in `contents/conclusion.tex` line 16. All four sub-items covered:
  - [x] Evaluating open-source full-duplex models as they gain realtime tool calling — "open-source full-duplex models as they gain native tool calling"
  - [x] Cascaded pipeline comparison — "Adding cascaded ASR→LLM→TTS baselines"
  - [x] Multilingual expansion — "non-English languages"
  - [x] Evaluation with real human callers — "human user studies to validate simulator dynamics"
- [x] **Add explicit comparison to VoiceAgentBench** (Jain et al., 2026) — Reviewer beyN Q4. — landed in `contents/related_work.tex` line 48 ("plays pre-recorded TTS queries to the model rather than evaluating fully agentic, dynamically grounded task solving") + added to Table 1.

### C2. Tables & figures

- [x] **Add specific model identifiers alongside provider/system names** in the main results tables (Reviewer v3yK W1). *Implementation note:* we chose **alias-only** (e.g. `gemini-live-2.5`, `gpt-realtime-1.5`, `grok-voice`) rather than the literal "Provider (`alias`)" form from the rebuttal, since the alias→provider mapping is given once in the Models table (Table 2) and double-naming clutters every results row. Prose throughout the paper was also unified to aliases for consistency.
- [x] **Re-verify "Table 7" numbers (Reviewer beyN Q1).** In current numbering this is the **ablation table** (`tab:ablation-single`, renders as Table 7 in the built PDF). Arithmetic check: deltas are computed from un-rounded source CSV values, but displayed against percentages rounded to integers (e.g. `gemini-live-2.5 +Noise` shows "40% (-4, -9.8%)", but naive `45% - 40% = 5pp`; the -4 comes from `0.4474 - 0.4035`). Deltas are *correct*, but optics suggest inconsistency — exactly what beyN flagged. **Fix applied**: caption note added explaining deltas are computed from un-rounded source values.
- [x] **Re-verify "Figure 2" is referenced in body (Reviewer beyN Q1).** In current numbering, Figure 2 is the **orchestrator architecture diagram** (`fig:architecture`, `contents/methods/orchestrator.tex`). beyN's original complaint still applied — only the `\label` existed, no `\ref` in the body. **Fix applied**: added "Figure~\ref{fig:architecture} shows the overall \tauvoice{} architecture." at the top of the Full-Duplex Orchestrator subsection.

### C3. New appendix material

- [ ] **New appendix section**: full ASR-enabled evaluation results (from B2). **Blocked on data** (Victor to share results). One subtlety: line 956 of the reviews says the text-free configuration "along with results for existing models in that setting, **is now included**" — past-tense framing in the rebuttal to vw95. Reviewers may expect this section to be ready, not just promised.
- [ ] **Release LiveKit integration code** for cascaded pipelines (Reviewer beyN Q2). No commitment to put cascaded numbers in the paper, but code must be released.
- [ ] Consider adding (not strictly promised, but high-value):
  - [x] **Human annotation study of simulator realism** (from B3) — landed: §6.1 Simulator Fidelity paragraph (`conclusion.tex`) + new appendix subsection `Simulator Realism Validation` (`\label{app:simulator-realism}`, `additional_results.tex`).
  - [x] **Refined error taxonomy with percentages** (from B4) — landed in §5.2 (`results.tex`) as a closing "Commonsense vs. policy skills" paragraph with the 7%/38%/22%/24%/6%/3% breakdown and counts (5/26/15/16/4/2 of 68 agent-attributable failures), cross-referenced to new appendix subsection `Commonsense vs. Policy Error Taxonomy` (`\label{app:commonsense-taxonomy}`, `additional_results.tex`). The appendix contains the full bucket-by-bucket definitions, an interpretation paragraph, and a reproducibility note explaining the re-coding from the existing mechanical error-type annotations (Table~\ref{tab:full-notes-both}). All edits wrapped in `\new{}\why{vw95 W2; macs final framing}`.

### C4. Infrastructure / ongoing

- [x] **Maintain an updated leaderboard** as more models gain realtime + tool-calling capabilities (Reviewers macs, vw95). Not a paper edit; just a public commitment. **Status**: live at `https://taubench.com` and being maintained. Paper-side commitment is in place: leaderboard URL appears in the front matter (under the title) and in the Future Work section.

### C6. Statistical reliability — extend to all three domains

- [x] **Extend Statistical Reliability appendix from Retail-only to all three domains** (Reviewer beyN W4 / Q5; promised in rebuttal). The current appendix paragraph (`appendix/additional_results.tex`) still only reports Retail, but our Q5 rebuttal stated *"the updated version extends to all three domains (2 runs per condition, paired permutation tests, Holm-Bonferroni corrected). The key gaps (text-to-voice, clean-to-realistic) are significant across all three domains."* This was repeated to vw95, v3yK, and macs. The all-domains stat sig data is already produced and staged in `paper/reviews/pairwise_statsig_all_domains.md` (with a polished proposed replacement paragraph at the bottom of that file). Work needed:
  - [x] Replace the Retail-only "Statistical Reliability" paragraph in `appendix/additional_results.tex` with the all-domains version.
  - [x] Replace / extend `tab:stat-sig` (currently Retail-only) with per-domain stat sig tables (Airline n=50, Retail n=114, Telecom n=114) plus the combined view. *Landed as two tables: `tab:stat-sig` is now the combined "All Domains" headline; `tab:stat-sig-per-domain` is the per-domain breakdown (`results/stat_sig_table.tex` + `results/stat_sig_table_per_domain.tex`).*
  - [x] Update the brief stat sig mention in `results.tex` (Section 5) to match the new scope and table reference.
  - [x] Surface the nuance honestly: e.g. Telecom xAI Clean *exceeds* the non-reasoning text baseline (+20.6 pp, p < 0.001), which makes the combined non-reasoning Text → Clean gap non-significant for xAI — but Text → Realistic and Clean → Realistic remain significant. *Covered in the appendix interpretive paragraph (Telecom +20.6pp story is the highlighted "per-domain deviation"); kept out of the Section 5 paragraph to preserve its page footprint, which now hedges with "significant for two of three models" and defers to the appendix.*
  - [x] **Methodology fix found during verification**: the source MD's combined "All Domains" view mixed two aggregation methods — voice rates and Text(R) baseline were per-task averaged across 278 tasks, but Text(NR) baseline was trial-level averaged across 770 GPT-4.1 trials (over-weighting Retail because it has 4 runs vs Telecom's 1). This inflated the displayed combined Text(NR) baseline to 64.3% (vs the methodologically-consistent 55.9%) and inflated the 6 Text(NR) Δs in Table 17. Recomputed via independent paired-permutation rerun from the raw CSV; p-values matched the source MD exactly (paired test is per-task and was always valid), so only the displayed Rate A and Δs needed updating. Section 5 text baseline corrected from "64% (GPT-4.1)" to "56% (GPT-4.1)" — now consistent within rounding with the headline `combined_comparison_table.tex` (which reports "54%"). Verification script approach + corrected outputs noted here so future-Victor doesn't re-derive.
  - [x] **Reviewer attribution**: beyN W4 / Q5; reinforces commitments made in rebuttals to vw95 and v3yK as well.

### C5. Reference correctness (from Program Chairs)

- [x] **Check flagged references** from the automated checker (PCs noted potential false positives). Spot-check authors, title, venue, arXiv ID for any reference the checker flagged. The PC's machine-readable list is essentially unreadable (`[object Object]` artifacts); spot-check the whole bibliography. *(VoiceAgentBench `year={2026}` is correct per the arXiv v3 canonical bibtex; reviewers' "Jain et al., 2025" referred to the older v1.)*
  - **Cited entries audited**: 9 of 22 rendered entries had arXiv-only metadata when the work was actually venue-published. Switched to canonical proceedings citation and updated year to match the venue:
    - `yao_-bench_2024` → ICLR 2025 Poster (Yao et al., 2024 → 2025).
    - `barres_2-bench_2025` → unchanged (ICLR 2026 desk reject; arXiv stays canonical, 2025).
    - `si_spokenwoz_2025` → NeurIPS 2023 D&B Track (Si et al., 2025 → 2023).
    - `wang_audiobench_2025` → NAACL 2025 long, pp.\ 4297-4316.
    - `ao_sd-eval_2025` → NeurIPS 2024 D&B Track (Ao et al., 2025 → 2024).
    - `arora_talking_2025` → ICLR 2025 Poster.
    - `lin_full-duplex-bench_2025` → IEEE ASRU 2025.
    - `lin_full-duplex-bench-v2_2025` → ACL 2026 main, to appear (Lin et al., 2025 → 2026).
    - `jiang_s2s-arena_2025` → ACL 2026 main, to appear; title and author list also updated from the v1 form to the v2 (current) form (Jiang et al., 2025 → 2026).
    - `yang_paras2s_2025` → ICLR 2026 Poster (Yang et al., 2025 → 2026).
  - **Citation keys unchanged**: all 22 inline `\cite{...}` sites still resolve. Inline citations now render the venue year per natbib, so the in-text label updates automatically (e.g. "Yao et al. (2024)" → "(2025)"; "Si et al. (2025)" → "(2023)").
  - **Other cited entries verified clean**: `chen_voicebench_2024`, `gosai_audio_2025`, `liu_vocalbench_2026`, `zhang_wildspeech-bench_2025`, `li_cb-whisper_2024`, four Gartner / a16z / OpenAI / Vertex AI / xAI URL entries, and `jain2026voiceagentbenchvoiceassistantsready` all matched their authoritative sources (arXiv canonical bibtex or ACL Anthology bibtex).
  - **Uncited bib entries**: 11 entries were carried over from drafts but never cited. Three had stale metadata fixed for hygiene (`arora_landscape_2025` → TMLR 2025; `yang_air-bench_2024` → ACL 2024 long; `li_televal_2025` author list and year corrected against arXiv canonical). The other 8 (gartner, blomsma, cathcart, raux, chen_wavrag, elevenlabs, hou_sova-bench, ji_wavchat, yan_uro-bench) were spot-checked and left as-is. No uncited entry renders in the PDF, so this is purely future-citation hygiene.
  - **Build verification**: clean rebuild from `latexmk -C` then `latexmk -pdf` produces 33-page PDF, 22 `\bibitem` entries, zero unresolved citations or LaTeX warnings.
  - **Commits**: split into 4 small batches by venue cluster: `5634a5a` (τ-bench/SpokenWOZ/AudioBench), `36017bf` (SD-Eval/Talking Turns/FDB-v1), `f672872` (FDB-v2/S2S-Arena/ParaS2S), `9dcb8aa` (uncited hygiene).
  - **C7 follow-up bib additions** (separate commit `c9edeff`, scoped to C7 not C5): 8 new entries for the audio-native audit — `wang_ntpp_2025` (ICML 2025), `fang_llama-omni_2025` (ICLR 2025), `yu_salmonn-omni_2025` (NeurIPS 2025), `defossez_moshi_2024` (arXiv canonical), `nvidia_personaplex_2026` (`@misc`, GitHub), `openbmb_minicpm-o_2026` (`@misc`, HuggingFace), `qwen_omni_realtime_2025` (`@misc`, Qwen blog), `amazon_nova_sonic_2025` (`@misc`, AWS blog). Total rendered bibliography went from 22 to 30 entries — the three pre-existing keys for the evaluated providers (`openai_introducing_2025`, `vertex_ai_gemini_2025`, `xai_grok_voice_2025`) are now cited for the first time in the appendix table.

### C7. Audited audio-native model survey (paper-side)

- [x] **Add the audit of audio-native models to the paper** (Reviewers macs W4 + macs follow-up, vw95 W3). Landed `app:audio-native-audit` (Appendix H.1) with an 11-row capability matrix (`tab:audio-native-audit`, Table 15): 4 qualifying models (OpenAI Realtime, Gemini Live, xAI Voice Agent, Amazon Nova 2 Sonic) and 7 disqualifying ones (NTPP, LLaMA-Omni, SALMONN-omni, Moshi, PersonaPlex, MiniCPM-o 4.5, Qwen-Omni-Realtime). Nova 2 Sonic is explicitly footnoted as qualifying-but-deprioritized (closed source). All ✓/✗ cells are backed verbatim by the rebuttals to macs W4 and macs follow-up; nothing invented. Cross-referenced from §4.2 (`contents/experiments.tex` line 16) with a single \new{...}\why{...} sentence. Audit dated March 2026; live freshness handled by the existing taubench.com leaderboard hedge. PDF grew from 33 to 35 pages.

### C8. Refined error taxonomy (commonsense vs policy)

- [x] **Add the commonsense-vs-policy error taxonomy to §5.2** (Reviewer vw95 W2, Reviewer macs final-framing critique). Landed using the **Option C** placement: a load-bearing summary paragraph in §5.2 with the 7%/38%/22%/24%/6%/3% headline plus the explicit 93% commonsense framing, and full per-bucket definitions, examples, and interpretation in new appendix subsection `Commonsense vs. Policy Error Taxonomy` (`\label{app:commonsense-taxonomy}`, H.4 in the camera-ready PDF). Bucket counts taken verbatim from the rebuttal (5/26/15/16/4/2 of 68), with the 23.5%→24% and 5.9%→6% rounding made auditable by reporting both the count and the percent. All edits wrapped in `\new{}\why{vw95 W2; macs final framing}`. No undefined references, no multiply-defined labels, clean 35-page build.

---

## Reviewer-by-reviewer attribution

| Commitment | beyN | macs | vw95 | v3yK | PCs |
|---|:---:|:---:|:---:|:---:|:---:|
| Reframe as controlled (not end-to-end) | ✓ | | | | |
| Section 3.1 clarification | ✓ | | | | |
| Section 6.1: upper-bound framing | ✓ | | ✓ | | |
| Section 6.1: ASR mode available | ✓ | | ✓ | | |
| Emphasize tool-calling as inclusion criterion | | ✓ | | | |
| Clarify 278-task construction | | ✓ | | | |
| Expand Future Work | | | | ✓ | |
| VoiceAgentBench comparison | ✓ | | | | |
| Model identifiers in tables | | | | ✓ | |
| Table 7 / Figure 2 fixes | ✓ | | | | |
| ASR-enabled appendix | ✓ | | ✓ | | |
| LiveKit code release | ✓ | ✓ | | | |
| Simulator-realism study (B3) | | ✓ | | | |
| Refined error taxonomy (verify) | | | ✓ | | |
| Leaderboard | | ✓ | ✓ | | |
| Reference correctness | | | | | ✓ |
| Stat sig: all three domains (C6) | ✓ | ✓ | ✓ | ✓ | |
| Audited audio-native model survey (C7) | | ✓ | ✓ | | |
| Commonsense-vs-policy error taxonomy (C8) | | ✓ | ✓ | | |

---

## Quick triage / suggested order of work

**Completed**
- Model identifiers in tables (C2.1).
- Table 7 rounding caption note + Figure 2 body reference (C2.2, C2.3).
- All C1 framing edits (controlled-benchmark, ASR-mode, upper-bound, tool-calling inclusion, 278-task construction, Future Work expansion, VoiceAgentBench comparison).
- Leaderboard public commitment (C4).
- Stat sig appendix + Section 5 paragraph extended to all three domains (C6).
- Reference correctness check (C5): 9 cited entries converted from arXiv to canonical venue citations; 3 uncited entries fixed for hygiene; all other entries spot-checked clean.
- Simulator-realism human study (B3): §6.1 paragraph + new `app:simulator-realism` appendix subsection with per-dimension table.
- Audited audio-native model survey (C7): new `app:audio-native-audit` appendix subsection with 11-row capability matrix (`tab:audio-native-audit`), one-sentence cross-ref from §4.2. Audit dated March 2026; 8 new bib entries added (`c9edeff`); landing commit `830f164`.
- Figure 1 regeneration (C2.1 follow-up): regenerated `results/pass_1_headline_simple.pdf` with canonical model aliases (`gemini-live-2.5`, `gpt-realtime-1.5`, `grok-voice`) replacing the human-readable provider names, matching Table~\ref{tab:models} and the paper prose. Source fix landed in `src/experiments/tau_voice/exp/plot_style.py` (`SHORT_MODEL_NAMES`); regenerated from `data/exp/final_voice_results_trial1_analysis` (the same single-trial CSV that backs the main results tables, so headline numbers 31/26, 49/35, 51/38 are unchanged). Removed the inline `\todo` from `intro.tex`. Landing commit `21e31ece`.

**Remaining, ordered by urgency × effort:**

1. **C3 — ASR-enabled appendix.** Partial data in hand (raw block below, shared 2026-05-15). Eight metadata questions outstanding before the appendix can be drafted — answers will determine framing, stat-sig claims, and whether the conclusion's existing "remains statistically significant" promise (`contents/conclusion.tex:12`) can be kept as-is or must be softened. **Do not draft the appendix until Q1–Q8 are answered.** The current `\todo{}` placeholder in `appendix/additional_results.tex:223` (under `\new{\subsection{ASR-enabled Evaluation}\label{app:asr-enabled}}`, line 221) is intentionally left in place so the build still flags this as outstanding.

   <details>
   <summary><strong>Raw data (provided 2026-05-15)</strong></summary>

   | Provider | Control (no noise) | Regular (with noise) | Delta |
   |----------|-------------------|---------------------|-------|
   | OpenAI | 0.61 | 0.33 | -0.28 |
   | xAI | 0.48 | 0.22 | -0.26 |
   | Gemini 2.5 | 0.40 | 0.25 | -0.15 |

   </details>

   <details>
   <summary><strong>Open metadata questions (asked of data owner 2026-05-15; awaiting response)</strong></summary>

   - **Q1. Domain.** What domain(s) was this run on? The shape (OpenAI > xAI > Gemini, 61/48/40 Control) doesn't cleanly match either the default-mode "All" row (gemini-live-2.5 31% / gpt-realtime-1.5 49% / grok-voice 51% Clean) or the default-mode Retail-only row (45 / 71 / 48 Clean). Best guess: Retail-114, but the relative ordering shifts under ASR. **Need confirmation.**
   - **Q2. Condition mapping.** Does "Control (no noise)" map to the paper's **Clean** and "Regular (with noise)" map to **Realistic**? Almost certainly yes (Clean = no noise + American accents + standard turn-taking; Realistic = noise + accents + behaviors), but confirm so the appendix uses the paper's vocabulary consistently.
   - **Q3. Run count and per-task scores.** Is this 1 run or 2 runs per condition? Are per-task pass/fail scores available, or only aggregate pass rates? Determines whether we can run a **paired permutation test** against the default mode (matching the C6 methodology) or have to label this a single-run preliminary.
   - **Q4. Model aliases.** Confirm "OpenAI / xAI / Gemini 2.5" in the table = `gpt-realtime-1.5` / `grok-voice` / `gemini-live-2.5` (same model vintage as the default-mode camera-ready numbers). Reviewer v3yK W1 requires the appendix to use the aliases, not provider names.
   - **Q5. Reporting precision.** Convert 0.61 / 0.33 / etc. to integer percentages (61% / 33%) for paper convention? Or keep two-decimal proportions?
   - **Q6. ASR pipeline.** Which ASR is the user simulator using to perceive the agent? Deepgram Nova-3 (same as the cascaded baseline)? Whisper-large-v3? Something else? Reviewer beyN's follow-up specifically asked for the pipeline to be named.
   - **Q7. Gemini delta is notably smaller (-0.15 vs -0.26 and -0.28).** Worth one sentence in the appendix interpretation, but which reading is correct: (a) Gemini is genuinely more robust to ASR-mediated user perception; (b) Gemini already had the lowest Control score (40%) so less ceiling to lose; (c) something else noticed at run time. We must not over-claim (a) if (b) explains it.
   - **Q8. Stat sig.** The conclusion currently promises "under [ASR-enabled] mode the text-to-voice gap and the clean-to-realistic degradation both remain statistically significant" (`contents/conclusion.tex:12`). Were stat tests actually run on this data? Sanity check from the numbers alone suggests both gaps probably are significant (Text 76% → 40–61% voice and 28–15pp Clean→Realistic drops), but I will not write "remains statistically significant" in the appendix without confirmation. If no stat test was run, the conclusion promise has to soften to "the gaps in our preliminary ASR-enabled run are consistent with the default-mode findings" or similar.

   </details>

   <details>
   <summary><strong>Planned appendix structure (once Q1–Q8 answered)</strong></summary>

   Mirrors `app:audio-native-audit` and `app:commonsense-taxonomy`:

   1. **Framing paragraph** — why two configurations, why ASR-enabled is a stricter stress test, explicit upper-bound interpretation of default mode (this is already promised in `contents/conclusion.tex:12` and `methods/voice_user_simulator.tex:6`).
   2. **Methodology** — ASR pipeline (Q6), task subset/domain (Q1), run count (Q3).
   3. **Results table** — per-model Clean / Realistic with deltas, side-by-side with default-mode reference numbers from `tab:text-control-regular` so the gap is visually unmistakable.
   4. **Stat sig** (if Q3/Q8 supports it) — paired permutation result against default mode, Holm-Bonferroni corrected to match C6; otherwise an honest "preliminary, deferred to follow-up" sentence.
   5. **Interpretation** (~3 sentences) — both gaps persist; Gemini-specific note (Q7); main-text upper-bound framing holds.

   All wrapped `\new{...}\why{addresses beyN follow-up; vw95 follow-up}`.

   </details>

2. **C3 — LiveKit code release** (repo work, not paper LaTeX).

---

## Open questions / risks

- **Cascaded baseline in the paper — deferred decision.** We told reviewers (beyN Q2, macs W4) the cascaded LiveKit numbers would not appear in the paper, only the code (B1, line 75). The current camera-ready prose is consistent with that promise: `contents/conclusion.tex` future-work sentence on cascaded ASR→LLM→TTS baselines + `contents/impact.tex` capability framing ("Researchers can bring their own ... cascaded models"). Two options on the table for a later revisit:
  - **Option A — keep the promise (no paper change).** Pros: zero risk of reviewer follow-up; consistent with rebuttal text. Cons: the 63.2% Clean / 43.0% Realistic Retail-114 data point (Deepgram Nova-3 → GPT-4.1 → ElevenLabs via LiveKit) that empirically backs "the gap is not specific to end-to-end APIs" stays buried in OpenReview only.
  - **Option B — add a small "preliminary cascaded probe" appendix sidebar.** A new appendix subsection (~150 words, label something like `app:cascaded-baseline`) with: the pipeline configuration (Deepgram Nova-3, GPT-4.1 vintage, ElevenLabs v3, LiveKit version), the aggregate 63.2%/43.0% Retail numbers, side-by-side with the audio-native range (45–71% Clean, 30–45% Realistic) and text GPT-4.1 baseline (76%), plus the "one configuration cannot represent cascaded systems as a class" caveat verbatim from the rebuttal. One-sentence cross-ref in §5. Wrapped `\new{}\why{beyN Q2; macs W4}`. Pros: directly answers beyN Q2 in-paper rather than only in OpenReview; modest hedge against macs's "the paper is just text-tool-calling" framing (cascaded systems are the closest thing to text-tool-calling with audio, and they still show the gap). Cons: goes beyond what we promised at rebuttal (a *positive* deviation — no reviewer can fault us for *adding* baseline evidence — but worth noting).
  - **Hard prerequisite for Option B**: commit the raw cascaded-run artifacts somewhere under `data/exp/` (CSV / per-task log) with the same provenance discipline used for B3 (`paper/reviews/user_realism_annotations/`) and C6 (`paper/reviews/pairwise_statsig_all_domains.md`). Citing 63.2%/43.0% in the appendix without committed receipts would contradict the reproducibility-note discipline we applied for C8.
  - **Status:** deferred. Revisit when the cascaded-run artifacts are available (or when we explicitly decide to keep Option A).
- The "ASR-enabled" results were described qualitatively in the rebuttal ("all scores dropped … significant findings held"). Partial concrete data received 2026-05-15 (aggregate Control / Regular pass rates per provider; see C3 entry in the Remaining list for the raw block). Eight metadata questions outstanding (domain, condition mapping, run count, model aliases, reporting precision, ASR pipeline, Gemini interpretation, stat sig) before the appendix can be drafted. Stat-sig analysis reproducibility still needs to be tied back to `REPRODUCE.md` once the underlying runs are located.
- Reviewer macs's confidence-5 strong reject was explicitly flagged to the AC. No action required, but worth noting in case the meta-review references it.
