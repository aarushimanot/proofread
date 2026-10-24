# Proofread evaluation report: Built-in test set (Chandrayaan-3)

Generated 2026-10-24T20:51:35+00:00. 14 hand-written test claims; 4 multi-claim posts. Settings: relevance threshold {config.RELEVANCE_THRESHOLD}, top_k 3, entailment/contradiction threshold 0.6/0.6, mismatch nudge 0.35.

## Headline results (full system)

- **Accuracy: 13/14 = 93%** (macro-F1 0.96)
- All test claims were seen while the system was being built (there is no held-out set), so this is an optimistic estimate.
- Not-covered claims wrongly called false: **0%** (the assignment's key rule)
- Wrong or not-covered claims wrongly supported: **0%**
- Sent to a human as CONFLICTING: 7%
- End-to-end (claim extracted from the post): 93%; extraction found the intended claim in 14/14 posts
- Multi-claim posts: found 100% of the claims (precision 92%); verdict correct for 82% of the claims found
- Average time per claim: 0.12 s on mps

## Baselines and ablations

| system | type | accuracy | macro-F1 | not-covered → false | wrongly supported | to human |
|---|---|---|---|---|---|---|
| Keyword match | baseline | 57% | 0.49 | 0% | 67% | 0% |
| Similarity only | baseline | 57% | 0.46 | 0% | 33% | 0% |
| Plain NLI | baseline | 71% | 0.80 | 25% | 0% | 21% |
| Proofread (full) | full | 93% | 0.96 | 0% | 0% | 7% |
| − relevance threshold | ablation | 93% | 0.96 | 0% | 0% | 7% |
| − number/date check | ablation | 93% | 0.96 | 0% | 0% | 7% |
| − event-alignment gate | ablation | 71% | 0.80 | 25% | 0% | 21% |
| + sentence-level NLI | ablation | 86% | 0.93 | 0% | 0% | 14% |
| top_k = 1 | ablation | 86% | 0.85 | 0% | 11% | 0% |
| top_k = 5 | ablation | 93% | 0.96 | 0% | 0% | 7% |

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
| chandrayaan-3 | 13/14 = 93% |

## Per-class metrics (full system)

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| SUPPORTED | 1.00 | 1.00 | 1.00 | 5 |
| CONTRADICTED | 1.00 | 0.80 | 0.89 | 5 |
| INSUFFICIENT_EVIDENCE | 1.00 | 1.00 | 1.00 | 4 |

## Confusion matrix (full system)

| expected \ predicted | SUP | CON | INS | CNF |
|---|---|---|---|---|
| SUPPORTED | 5 | 0 | 0 | 0 |
| CONTRADICTED | 0 | 4 | 0 | 1 |
| INSUFFICIENT_EVIDENCE | 0 | 0 | 4 | 0 |

## Confidence calibration

Is the system right more often when it says High?

| confidence | claims | accuracy |
|---|---|---|
| High | 11 | 100% |
| Medium | 1 | 100% |
| Low | 2 | 50% |

## Relevance-threshold sensitivity

| threshold | accuracy | not-covered → false |
|---|---|---|
| 0.35 | 93% | 0% |
| 0.45 | 93% | 0% |
| 0.55 | 93% | 0% |
| 0.65 | 86% | 0% |

## Multi-claim posts

- **M01** (chandrayaan-3)
  - (correct) “Chandrayaan-3 was launched on 14 July 2023.” expected SUPPORTED, found → SUPPORTED
  - (correct) “The Pragyan rover has four wheels.” expected CONTRADICTED, found → CONTRADICTED
  - (extra) sentence treated as a claim: “Big week in space history!”
- **M02** (constitution-of-india)
  - (correct) “The Constitution of India was adopted on 26 November 1949.” expected SUPPORTED, found → SUPPORTED
  - (correct) “It came into force on 26 January 1950.” expected SUPPORTED, found → SUPPORTED
  - (correct) “B. R. Ambedkar chaired the Drafting Committee.” expected SUPPORTED, found → SUPPORTED
- **M03** (cricket-world-cup-2023)
  - (WRONG) “Australia won the 2023 World Cup final in Ahmedabad.” expected SUPPORTED, found → CONTRADICTED
  - (WRONG) “Travis Head scored 137 in the final.” expected SUPPORTED, found → INSUFFICIENT_EVIDENCE
  - (correct) “Virat Kohli scored 900 runs in the tournament.” expected CONTRADICTED, found → CONTRADICTED
- **M04** (chandrayaan-3)
  - (correct) “Chandrayaan-3 landed near the Moon's south pole on 23 August 2023.” expected SUPPORTED, found → SUPPORTED
  - (correct) “The mission cost only 615 crore rupees.” expected INSUFFICIENT_EVIDENCE, found → INSUFFICIENT_EVIDENCE
  - (correct) “The Pragyan rover found sulphur on the Moon.” expected SUPPORTED, found → SUPPORTED

## Per-claim results (full system)

| id | claim | expected | predicted | confidence | top passage |
|---|---|---|---|---|---|
| T01 | Chandrayaan-3 was launched on 14 July 2023 from Sriharikota. | SUPPORTED | SUPPORTED | 0.93 (High) | CY3-02 Launch of Chandrayaan-3 from Sriharikota |
| T02 | The Vikram lander touched down near the Moon's south pole on 23 August 2023. | SUPPORTED | SUPPORTED | 1.00 (High) | CY3-05 Vikram lander touches down near the lunar south pole |
| T03 | The Pragyan rover confirmed the presence of sulphur on the lunar surface. | SUPPORTED | SUPPORTED | 0.99 (High) | CY3-10 Sulphur detected on the lunar surface by Pragyan |
| T04 | India became the first country to land near the lunar south pole. | SUPPORTED | SUPPORTED | 0.76 (Medium) | CY3-06 India's place in lunar landing history |
| T05 | Chandrayaan-3 landed on the Moon on 15 August 2023. | CONTRADICTED | CONTRADICTED | 1.00 (High) | CY3-04 Lunar orbit insertion and lander separation |
| T06 | The rover deployed by Chandrayaan-3 was named Pragati. | CONTRADICTED | WRONG: CONFLICTING | 1.00 (Low) | CY3-08 Pragyan rover |
| T07 | Chandrayaan-3 landed near the Moon's north pole. | CONTRADICTED | CONTRADICTED | 1.00 (High) | CY3-05 Vikram lander touches down near the lunar south pole |
| T08 | The Pragyan rover has four wheels and carried two instruments. | CONTRADICTED | CONTRADICTED | 1.00 (High) | CY3-08 Pragyan rover |
| T09 | The Chandrayaan-3 mission cost less than the budget of the movie Interstellar. | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | – (Low) | CY3-01 Chandrayaan-3 mission overview |
| T10 | The Pragyan rover found water ice at the Chandrayaan-3 landing site. | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | 1.00 (High) | CY3-08 Pragyan rover |
| T11 | The Chandrayaan-3 mission was led by project director P. Veeramuthuvel. | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | 1.00 (High) | CY3-01 Chandrayaan-3 mission overview |
| T12 | Over 8 million people watched the Chandrayaan-3 landing live on YouTube. | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | 1.00 (High) | CY3-02 Launch of Chandrayaan-3 from Sriharikota |
| T13 | ISRO's Moon rover drove more than a hundred metres before going to sleep. | SUPPORTED | SUPPORTED | 0.99 (High) | CY3-12 Rover traverse and sleep mode |
| T14 | India became the third country to soft-land on the Moon. | CONTRADICTED | CONTRADICTED | 1.00 (High) | CY3-06 India's place in lunar landing history |

## Failures

- **T06** “The rover deployed by Chandrayaan-3 was named Pragati.”: expected CONTRADICTED, got CONFLICTING. Stances: CY3-08:supports; CY3-01:insufficient; CY3-07:contradicts. Note: Wrong rover name: the rover is Pragyan (CY3-01, CY3-08).

_Caveat: All test claims were seen while the system was being built (there is no held-out set), so this is an optimistic estimate. 14 claims is a small test set._