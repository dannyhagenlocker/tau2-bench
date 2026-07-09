# Document ablation — baseline-gpt55-t2

36 labeled failures, 6 root-cause classes. Score = V-measure of clustering vs hand-labeled root cause (best threshold).

**Signature engine reference:** V-measure=0.647, ARI=0.204, 21 clusters

**Best by V-measure (purity):** embedder=`st`, doc=`core+last_message`, threshold=0.3 → V-measure=0.769, ARI=0.697, 6 clusters

**Best by ARI (grouping — our target):** embedder=`st`, doc=`core+last_message`, threshold=0.3 → ARI=0.697, V-measure=0.769, 6 clusters

## Marginal V-measure vs core spine (embedder=`st`, core=0.443)

| Added signal | Δ V-measure |
|--------------|------------|
| last_message | +0.326 |
| nl | +0.103 |
| escalation | +0.083 |
| tool_errors | +0.000 |

## All configs (sorted by V-measure)

| embedder | document | V-measure | ARI | homog | compl | k | thr |
|----------|----------|-----------|-----|-------|-------|---|-----|
| st | core+last_message | 0.769 | 0.697 | 0.769 | 0.769 | 6 | 0.3 |
| st | core+last+mechanism | 0.769 | 0.697 | 0.769 | 0.769 | 6 | 0.3 |
| st | core+esc+last | 0.769 | 0.697 | 0.769 | 0.769 | 6 | 0.3 |
| st | core+esc+last+nl | 0.716 | 0.531 | 0.841 | 0.624 | 10 | 0.2 |
| st | all_why | 0.716 | 0.531 | 0.841 | 0.624 | 10 | 0.2 |
| char | all_why | 0.691 | 0.491 | 0.786 | 0.616 | 8 | 0.5 |
| char | core+escalation | 0.684 | 0.293 | 0.961 | 0.531 | 14 | 0.2 |
| tfidf | core+last_message | 0.671 | 0.467 | 0.826 | 0.565 | 12 | 0.6 |
| tfidf | core+last+mechanism | 0.671 | 0.467 | 0.826 | 0.565 | 12 | 0.6 |
| tfidf | core+esc+last | 0.671 | 0.467 | 0.826 | 0.565 | 12 | 0.6 |
| tfidf | core+esc+last+nl | 0.671 | 0.467 | 0.826 | 0.565 | 12 | 0.7 |
| tfidf | all_why | 0.671 | 0.467 | 0.826 | 0.565 | 12 | 0.7 |
| lsa | core+last_message | 0.671 | 0.467 | 0.826 | 0.565 | 12 | 0.6 |
| lsa | core+last+mechanism | 0.671 | 0.467 | 0.826 | 0.565 | 12 | 0.6 |
| lsa | core+esc+last | 0.671 | 0.467 | 0.826 | 0.565 | 12 | 0.6 |
| lsa | core+esc+last+nl | 0.671 | 0.467 | 0.826 | 0.565 | 12 | 0.7 |
| lsa | all_why | 0.671 | 0.467 | 0.826 | 0.565 | 12 | 0.7 |
| char | core+mechanism | 0.67 | 0.281 | 0.961 | 0.515 | 16 | 0.2 |
| tfidf | core+mechanism | 0.657 | 0.329 | 0.904 | 0.516 | 14 | 0.5 |
| lsa | core+mechanism | 0.657 | 0.329 | 0.904 | 0.516 | 14 | 0.5 |
| char | core+esc+last | 0.655 | 0.38 | 0.822 | 0.544 | 11 | 0.4 |
| st | core+mechanism | 0.653 | 0.479 | 0.622 | 0.686 | 5 | 0.2 |
| char | core+last+mechanism | 0.646 | 0.326 | 0.831 | 0.529 | 11 | 0.4 |
| char | core+esc+last+nl | 0.645 | 0.306 | 0.864 | 0.515 | 12 | 0.4 |
| char | core | 0.635 | 0.25 | 0.886 | 0.495 | 15 | 0.2 |
| char | core+nl | 0.63 | 0.247 | 0.875 | 0.492 | 15 | 0.2 |
| char | core+last_message | 0.63 | 0.387 | 0.736 | 0.551 | 8 | 0.5 |
| tfidf | core+escalation | 0.621 | 0.153 | 0.972 | 0.456 | 21 | 0.2 |
| lsa | core+escalation | 0.621 | 0.153 | 0.972 | 0.456 | 21 | 0.2 |
| char | core+tool_errors | 0.619 | 0.203 | 0.875 | 0.478 | 15 | 0.2 |
| tfidf | core | 0.615 | 0.216 | 0.904 | 0.466 | 17 | 0.3 |
| tfidf | core+nl | 0.615 | 0.216 | 0.904 | 0.466 | 17 | 0.3 |
| tfidf | core+tool_errors | 0.615 | 0.241 | 0.858 | 0.479 | 15 | 0.4 |
| lsa | core | 0.615 | 0.216 | 0.904 | 0.466 | 17 | 0.3 |
| lsa | core+nl | 0.615 | 0.216 | 0.904 | 0.466 | 17 | 0.3 |
| lsa | core+tool_errors | 0.615 | 0.241 | 0.858 | 0.479 | 15 | 0.4 |
| st | core+nl | 0.546 | 0.304 | 0.573 | 0.522 | 7 | 0.2 |
| st | core+escalation | 0.526 | 0.36 | 0.481 | 0.58 | 4 | 0.2 |
| st | core | 0.443 | 0.333 | 0.384 | 0.524 | 3 | 0.2 |
| st | core+tool_errors | 0.443 | 0.333 | 0.384 | 0.524 | 3 | 0.2 |
