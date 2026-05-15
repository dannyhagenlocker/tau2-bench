# C8 skill-axis classification of agent-attributable failures

Source-of-truth for the 95% commonsense / 5% policy claim that appears in §5.2 of the
camera-ready paper (`papers/tau-voice/tau-voice-icml/contents/results.tex`).

## Provenance

- **Input**: `tau voice qa arxiv submission.xlsx`, sheets `voice fragile` and `noise fragile`
  (the reconciled inter-rater annotations from Mike + Niko + Soham's arbitration).
- **Filter**: Rows where the final-attribution `error_source` is `agent`. Final attribution
  follows the convention that `"X Y"` means originally tagged `X`, reclassified to `Y` (last
  word wins). Under this rule, the reconciled sheets yield 77 agent-attributable
  simulations (34 voice-fragile + 43 noise-fragile), matching Table 5
  (`tab:combined-error-analysis`) in the camera-ready PDF and the `overall` sheet of the
  source spreadsheet.
- **Classification axis**: Each of the 77 agent rows is assigned to exactly one of six
  skill buckets, addressing the question "what skill, if present, would have prevented
  this failure?" Buckets are mutually exclusive; each failure is assigned to the single
  skill whose absence is the proximal cause.

## Skill buckets

| Bucket | Definition |
|---|---|
| `policy` | Failure requires knowledge of a domain-specific rule in the agent's policy prompt (e.g., one-time-process rule, refund-method policy). |
| `spelling` | Agent transcribes a spelled-out name, email, or ID incorrectly, blocking authentication or producing a downstream lookup miss. |
| `grounding` | Agent executes an irreversible action without explicit user confirmation, or fails to share information the user needs to make the next decision. |
| `honesty` | Agent claims an action was performed when no corresponding tool call exists in the trace, or acts on a wrong item/entity. |
| `multi-part` | User makes a compound request; agent completes one part and treats the call as resolved. |
| `arithmetic` | Agent makes an arithmetic error (refund total, line-item sum) or contradicts an earlier statement in the same call. |

## Aggregate counts (this CSV)

| Bucket | Count | % |
|---|---:|---:|
| Policy-specific knowledge | 4 | 5.2% |
| Spelling | 27 | 35.1% |
| Conversational grounding | 24 | 31.2% |
| Conversational honesty | 13 | 16.9% |
| Multi-part request tracking | 5 | 6.5% |
| Arithmetic / self-consistency | 4 | 5.2% |
| **Total** | **77** | **100%** |

**Headline**: 73 / 77 (94.8%) of agent-attributable failures reflect domain-agnostic
commonsense skills; only 4 / 77 (5.2%) require domain-specific policy knowledge.

## Relationship to the rebuttal

The rebuttal to Reviewer vw95 W2 reported counts (5/26/15/16/4/2 = 68 = 7%/38%/22%/24%/6%/3%)
on a different denominator — Mike's solo pre-reconciliation count of strictly-agent-only
simulations (25 voice + 43 noise = 68). The camera-ready uses the reconciled denominator
(77) for consistency with Table 5 in the paper. The headline finding (≈95% commonsense,
≈5% policy) is preserved and slightly strengthened.

## Reproducibility

The classification was produced by reviewing each row's mechanical `error_type` and the
free-text `notes` column (and `soham notes` arbitration where present), assigning to the
single bucket whose absent skill is the proximal cause. See the
`classification_rationale` column for the one-line per-row justification.
