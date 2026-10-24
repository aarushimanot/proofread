# Proofread evaluation report: climate change

Generated 2026-10-24T20:50:22+00:00. 8 auto-generated test claims. Settings: relevance threshold {config.RELEVANCE_THRESHOLD}, top_k 3, entailment/contradiction threshold 0.6/0.6, mismatch nudge 0.35.

## Headline results (full system)

- **Accuracy: 8/8 = 100%** (macro-F1 1.00)
- These test claims were generated automatically from the same passages the system searches, so they are easier than real claims: treat this as a sanity check, not a measure of real-world accuracy.
- Not-covered claims wrongly called false: **0%** (the assignment's key rule)
- Wrong or not-covered claims wrongly supported: **0%**
- Sent to a human as CONFLICTING: 0%
- End-to-end (claim extracted from the post): 100%; extraction found the intended claim in 8/8 posts
- Average time per claim: 0.14 s on mps

## Baselines and ablations

| system | type | accuracy | macro-F1 | not-covered → false | wrongly supported | to human |
|---|---|---|---|---|---|---|
| Keyword match | baseline | 62% | 0.56 | 0% | 60% | 0% |
| Similarity only | baseline | 62% | 0.56 | 0% | 60% | 0% |
| Plain NLI | baseline | 62% | 0.52 | 100% | 0% | 12% |
| Proofread (full) | full | 100% | 1.00 | 0% | 0% | 0% |
| − relevance threshold | ablation | 88% | 0.93 | 0% | 0% | 12% |
| − number/date check | ablation | 100% | 1.00 | 0% | 0% | 0% |
| − event-alignment gate | ablation | 100% | 1.00 | 0% | 0% | 0% |
| + sentence-level NLI | ablation | 100% | 1.00 | 0% | 0% | 0% |
| top_k = 1 | ablation | 100% | 1.00 | 0% | 0% | 0% |
| top_k = 5 | ablation | 100% | 1.00 | 0% | 0% | 0% |

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
| climate-change | 8/8 = 100% |

## Per-class metrics (full system)

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| SUPPORTED | 1.00 | 1.00 | 1.00 | 3 |
| CONTRADICTED | 1.00 | 1.00 | 1.00 | 3 |
| INSUFFICIENT_EVIDENCE | 1.00 | 1.00 | 1.00 | 2 |

## Confusion matrix (full system)

| expected \ predicted | SUP | CON | INS | CNF |
|---|---|---|---|---|
| SUPPORTED | 3 | 0 | 0 | 0 |
| CONTRADICTED | 0 | 3 | 0 | 0 |
| INSUFFICIENT_EVIDENCE | 0 | 0 | 2 | 0 |

## Confidence calibration

Is the system right more often when it says High?

| confidence | claims | accuracy |
|---|---|---|
| High | 6 | 100% |
| Medium | 0 | n/a |
| Low | 2 | 100% |

## Relevance-threshold sensitivity

| threshold | accuracy | not-covered → false |
|---|---|---|
| 0.35 | 100% | 0% |
| 0.45 | 100% | 0% |
| 0.55 | 100% | 0% |
| 0.65 | 100% | 0% |

## Per-claim results (full system)

| id | claim | expected | predicted | confidence | top passage |
|---|---|---|---|---|---|
| CLIM-AUTO-01-climate-change | Scottish Green Mark Ruskell, the SNP’s Keith Brown and Scottish Labour’s Jenny Young weigh up the James Cook decision. | CONTRADICTED | CONTRADICTED | 1.00 (High) | P-ce05b2c1 Climate - BBC News: Jackdaw decision 'taken outwith Scotland about Scotland's energy' |
| CLIM-AUTO-02-climate-change | Rosebank leader Stephen Place says it will help businesses counter the rising cost of fuel. | CONTRADICTED | CONTRADICTED | 0.95 (High) | P-8240a384 Climate - BBC News: Fund to help businesses switch to green vehicles |
| CLIM-AUTO-03-climate-change | Council leader Stephen Place says it will help businesses counter the rising cost of fuel. | SUPPORTED | SUPPORTED | 0.98 (High) | P-8240a384 Climate - BBC News: Fund to help businesses switch to green vehicles |
| CLIM-AUTO-04-climate-change | Scotland editor James Cook visits Council - the UK's largest known untapped oilfield - in the North Atlantic. | CONTRADICTED | CONTRADICTED | 0.99 (High) | P-1be2822c Climate - BBC News: Is the UK set to green-light a huge untapped oil field? |
| CLIM-AUTO-05-climate-change | Climate change got its own official mobile app in 2004. | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | – (Low) | P-6427cd78 Climate - BBC News: Why do farmers want to build reservoirs and what's stopping them? |
| CLIM-AUTO-06-climate-change | Climate change received a donation of 5 million dollars from a technology company in 1991. | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | – (Low) | P-8240a384 Climate - BBC News: Fund to help businesses switch to green vehicles |
| CLIM-AUTO-07-climate-change | The Prince of Wales was marking his Earthshot Prize, to which all of Norton's guests were linked. | SUPPORTED | SUPPORTED | 0.98 (High) | P-f0ed0493 Climate - BBC News: Gasps as Prince William makes surprise appearance on Graham Norton Show |
| CLIM-AUTO-08-climate-change | A committee hears that Northern Ireland could lose out on economic opportunities if action is not accelerated. | SUPPORTED | SUPPORTED | 0.99 (High) | P-04c00826 Climate - BBC News: NI risks missing 2030 energy goals, says Stormont committee |

## Failures

None.

_Caveat: These test claims were generated automatically from the same passages the system searches, so they are easier than real claims: treat this as a sanity check, not a measure of real-world accuracy. 8 claims is a small test set._