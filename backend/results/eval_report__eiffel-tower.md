# Proofread evaluation report: Eiffel Tower

Generated 2026-10-24T20:50:47+00:00. 10 auto-generated test claims. Settings: relevance threshold {config.RELEVANCE_THRESHOLD}, top_k 3, entailment/contradiction threshold 0.6/0.6, mismatch nudge 0.35.

## Headline results (full system)

- **Accuracy: 5/10 = 50%** (macro-F1 0.42)
- These test claims were generated automatically from the same passages the system searches, so they are easier than real claims: treat this as a sanity check, not a measure of real-world accuracy.
- Not-covered claims wrongly called false: **0%** (the assignment's key rule)
- Wrong or not-covered claims wrongly supported: **0%**
- Sent to a human as CONFLICTING: 0%
- End-to-end (claim extracted from the post): 50%; extraction found the intended claim in 10/10 posts
- Average time per claim: 0.32 s on mps

## Baselines and ablations

| system | type | accuracy | macro-F1 | not-covered → false | wrongly supported | to human |
|---|---|---|---|---|---|---|
| Keyword match | baseline | 50% | 0.43 | 0% | 83% | 0% |
| Similarity only | baseline | 40% | 0.34 | 0% | 50% | 0% |
| Plain NLI | baseline | 40% | 0.32 | 50% | 0% | 0% |
| Proofread (full) | full | 50% | 0.42 | 0% | 0% | 0% |
| − relevance threshold | ablation | 50% | 0.42 | 0% | 0% | 0% |
| − number/date check | ablation | 50% | 0.41 | 0% | 0% | 0% |
| − event-alignment gate | ablation | 40% | 0.32 | 50% | 0% | 0% |
| + sentence-level NLI | ablation | 50% | 0.46 | 50% | 0% | 20% |
| top_k = 1 | ablation | 50% | 0.41 | 0% | 0% | 0% |
| top_k = 5 | ablation | 50% | 0.42 | 0% | 0% | 0% |

What each row means:

- **Keyword match**: Supported if ≥50% of the claim's content words appear in one passage; otherwise insufficient. Can never say 'contradicted'.
- **Similarity only**: Supported if the most similar passage has similarity ≥ 0.70; otherwise insufficient. Can never say 'contradicted'.
- **Plain NLI**: Retrieval + NLI with no relevance threshold and neither heuristic.
- **Proofread (full)**: The real system: relevance threshold, NLI, number/date check, event-alignment gate.
- **− relevance threshold**: Every retrieved passage counts as relevant.
- **− number/date check**: No mismatch nudge.
- **− event-alignment gate**: Contradictions about other events are kept.
- **+ sentence-level NLI**: Each passage judged by its most decisive sentence.
- **top_k = 1**: Only the single most similar passage is used.
- **top_k = 5**: The five most similar passages are used.

## Accuracy by topic

| topic | accuracy |
|---|---|
| eiffel-tower | 5/10 = 50% |

## Per-class metrics (full system)

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| SUPPORTED | 0.00 | 0.00 | 0.00 | 4 |
| CONTRADICTED | 0.50 | 0.75 | 0.60 | 4 |
| INSUFFICIENT_EVIDENCE | 0.50 | 1.00 | 0.67 | 2 |

## Confusion matrix (full system)

| expected \ predicted | SUP | CON | INS | CNF |
|---|---|---|---|---|
| SUPPORTED | 0 | 3 | 1 | 0 |
| CONTRADICTED | 0 | 3 | 1 | 0 |
| INSUFFICIENT_EVIDENCE | 0 | 0 | 2 | 0 |

## Confidence calibration

Is the system right more often when it says High?

| confidence | claims | accuracy |
|---|---|---|
| High | 10 | 50% |
| Medium | 0 | n/a |
| Low | 0 | n/a |

## Relevance-threshold sensitivity

| threshold | accuracy | not-covered → false |
|---|---|---|
| 0.35 | 50% | 0% |
| 0.45 | 50% | 0% |
| 0.55 | 50% | 0% |
| 0.65 | 50% | 0% |

## Per-claim results (full system)

| id | claim | expected | predicted | confidence | top passage |
|---|---|---|---|---|---|
| EIFF-AUTO-01-eiffel-tower | On 27 October 1991, Thierry Devaux, along with mountain guide Hervé Calvayrac, performed a series of acrobatic figures while bungee jumping from the second floor of the tower. | SUPPORTED | WRONG: CONTRADICTED | 0.99 (High) | P-2ef2952b Eiffel Tower: Subsequent events |
| EIFF-AUTO-02-eiffel-tower | In 2009, the Eiffel Tower began hosting a seasonal ice rink on the first level. | CONTRADICTED | CONTRADICTED | 1.00 (High) | P-4b474913 Eiffel Tower: Subsequent events |
| EIFF-AUTO-03-eiffel-tower | The tower received its 200,000,000th guest on 28 November 2002. | SUPPORTED | WRONG: CONTRADICTED | 1.00 (High) | P-4b474913 Eiffel Tower: Subsequent events |
| EIFF-AUTO-04-eiffel-tower | Excluding transmitters, the Eiffel Tower is the second tallest free-standing structure in France after the Millau Viaduct. | SUPPORTED | WRONG: INSUFFICIENT_EVIDENCE | 1.00 (High) | P-543625f7 Eiffel Tower |
| EIFF-AUTO-05-eiffel-tower | The tower received 5,889,000 visitors in 2022. | SUPPORTED | WRONG: CONTRADICTED | 1.00 (High) | P-4b474913 Eiffel Tower: Subsequent events |
| EIFF-AUTO-06-eiffel-tower | The tower is 330 metres tall, about the same height as a 49-storey building, and the tallest structure in Paris. | CONTRADICTED | CONTRADICTED | 1.00 (High) | P-95f8a507 Eiffel Tower |
| EIFF-AUTO-07-eiffel-tower | The Eiffel Tower got its own official mobile app in 2018. | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | 1.00 (High) | P-dd632a41 Eiffel Tower |
| EIFF-AUTO-08-eiffel-tower | Levallois-Perret supposedly ate lunch in the tower's restaurant every day because it was the one place in Paris where the tower was not visible. | CONTRADICTED | WRONG: INSUFFICIENT_EVIDENCE | 0.97 (High) | P-ac9f1ce1 Eiffel Tower: Artists' protest |
| EIFF-AUTO-09-eiffel-tower | In 1975, A. J. Hackett made one of his first bungee jumps from the top of the Eiffel Tower, using a special cord he had helped develop. | CONTRADICTED | CONTRADICTED | 0.99 (High) | P-2ef2952b Eiffel Tower: Subsequent events |
| EIFF-AUTO-10-eiffel-tower | The Eiffel Tower received a donation of 5 million dollars from a technology company in 2005. | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | 1.00 (High) | P-b8d10a4e Eiffel Tower: Origin |

## Failures

- **EIFF-AUTO-01-eiffel-tower** “On 27 October 1991, Thierry Devaux, along with mountain guide Hervé Calvayrac, performed a series of acrobatic figures while bungee jumping from the second floor of the tower.”: expected SUPPORTED, got CONTRADICTED. Stances: P-2ef2952b:contradicts; P-324a90a6:contradicts; P-62736069:not_assessed. Note: Auto-generated: stated in “Eiffel Tower: Subsequent events”.
- **EIFF-AUTO-03-eiffel-tower** “The tower received its 200,000,000th guest on 28 November 2002.”: expected SUPPORTED, got CONTRADICTED. Stances: P-4b474913:insufficient; P-b21692f3:insufficient; P-bd7e089e:contradicts. Note: Auto-generated: stated in “Eiffel Tower: Subsequent events”.
- **EIFF-AUTO-04-eiffel-tower** “Excluding transmitters, the Eiffel Tower is the second tallest free-standing structure in France after the Millau Viaduct.”: expected SUPPORTED, got INSUFFICIENT_EVIDENCE. Stances: P-543625f7:insufficient; P-95f8a507:insufficient; P-dd632a41:insufficient. Note: Auto-generated: stated in “Eiffel Tower”.
- **EIFF-AUTO-05-eiffel-tower** “The tower received 5,889,000 visitors in 2022.”: expected SUPPORTED, got CONTRADICTED. Stances: P-4b474913:contradicts; P-b21692f3:insufficient; P-794a2079:contradicts. Note: Auto-generated: stated in “Eiffel Tower”.
- **EIFF-AUTO-08-eiffel-tower** “Levallois-Perret supposedly ate lunch in the tower's restaurant every day because it was the one place in Paris where the tower was not visible.”: expected CONTRADICTED, got INSUFFICIENT_EVIDENCE. Stances: P-ac9f1ce1:insufficient; P-6e426930:not_assessed; P-582d2421:not_assessed. Note: Auto-generated from “Eiffel Tower: Artists' protest”: swapped “Guy de Maupassant” for “Levallois-Perret”.

_Caveat: These test claims were generated automatically from the same passages the system searches, so they are easier than real claims: treat this as a sanity check, not a measure of real-world accuracy. 10 claims is a small test set._