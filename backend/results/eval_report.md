# Proofread evaluation report

Test claims: **14**. Settings: relevance threshold 0.45, top_k 3, entailment/contradiction threshold 0.6/0.6, mismatch nudge 0.35.

## Summary

- Verification accuracy (gold claim): **13/14 = 93%**
- End-to-end accuracy (extracted claim): **13/14 = 93%**
- Extraction found the intended claim: **14/14** (13 exact, 1 with extra words)

## Per-class metrics (gold claim)

| class | precision | recall | F1 | support | predicted |
|---|---|---|---|---|---|
| SUPPORTED | 1.00 | 1.00 | 1.00 | 5 | 5 |
| CONTRADICTED | 1.00 | 0.80 | 0.89 | 5 | 4 |
| INSUFFICIENT_EVIDENCE | 1.00 | 1.00 | 1.00 | 4 | 4 |
| CONFLICTING | 0.00 | n/a | 0.00 | 0 | 1 |

## Confusion matrix (gold claim)

| expected \ predicted | SUP | CON | INS | CNF |
|---|---|---|---|---|
| SUPPORTED | 5 | 0 | 0 | 0 |
| CONTRADICTED | 0 | 4 | 0 | 1 |
| INSUFFICIENT_EVIDENCE | 0 | 0 | 4 | 0 |
| CONFLICTING | 0 | 0 | 0 | 0 |

## Per-claim results

| id | claim | expected | predicted | confidence | top passage | extraction | end-to-end |
|---|---|---|---|---|---|---|---|
| T01 | Chandrayaan-3 was launched on 14 July 2023 from Sriharikota. | SUPPORTED | ✅ SUPPORTED | 0.93 (High) | CY3-02 Launch of Chandrayaan-3 from Sriharikota | exact | SUPPORTED |
| T02 | The Vikram lander touched down near the Moon's south pole on 23 August 2023. | SUPPORTED | ✅ SUPPORTED | 1.00 (High) | CY3-05 Vikram lander touches down near the lunar south pole | exact | SUPPORTED |
| T03 | The Pragyan rover confirmed the presence of sulphur on the lunar surface. | SUPPORTED | ✅ SUPPORTED | 0.99 (High) | CY3-10 Sulphur detected on the lunar surface by Pragyan | exact | SUPPORTED |
| T04 | India became the first country to land near the lunar south pole. | SUPPORTED | ✅ SUPPORTED | 0.76 (Medium) | CY3-06 India's place in lunar landing history | exact | SUPPORTED |
| T05 | Chandrayaan-3 landed on the Moon on 15 August 2023. | CONTRADICTED | ✅ CONTRADICTED | 1.00 (High) | CY3-04 Lunar orbit insertion and lander separation | contains | CONTRADICTED |
| T06 | The rover deployed by Chandrayaan-3 was named Pragati. | CONTRADICTED | ❌ CONFLICTING | 1.00 (Low) | CY3-08 Pragyan rover | exact | CONFLICTING |
| T07 | Chandrayaan-3 landed near the Moon's north pole. | CONTRADICTED | ✅ CONTRADICTED | 1.00 (High) | CY3-05 Vikram lander touches down near the lunar south pole | exact | CONTRADICTED |
| T08 | The Pragyan rover has four wheels and carried two instruments. | CONTRADICTED | ✅ CONTRADICTED | 1.00 (High) | CY3-08 Pragyan rover | exact | CONTRADICTED |
| T09 | The Chandrayaan-3 mission cost less than the budget of the movie Interstellar. | INSUFFICIENT_EVIDENCE | ✅ INSUFFICIENT_EVIDENCE | – (Low) | CY3-01 Chandrayaan-3 mission overview | exact | INSUFFICIENT_EVIDENCE |
| T10 | The Pragyan rover found water ice at the Chandrayaan-3 landing site. | INSUFFICIENT_EVIDENCE | ✅ INSUFFICIENT_EVIDENCE | 1.00 (High) | CY3-08 Pragyan rover | exact | INSUFFICIENT_EVIDENCE |
| T11 | The Chandrayaan-3 mission was led by project director P. Veeramuthuvel. | INSUFFICIENT_EVIDENCE | ✅ INSUFFICIENT_EVIDENCE | 1.00 (High) | CY3-01 Chandrayaan-3 mission overview | exact | INSUFFICIENT_EVIDENCE |
| T12 | Over 8 million people watched the Chandrayaan-3 landing live on YouTube. | INSUFFICIENT_EVIDENCE | ✅ INSUFFICIENT_EVIDENCE | 1.00 (High) | CY3-02 Launch of Chandrayaan-3 from Sriharikota | exact | INSUFFICIENT_EVIDENCE |
| T13 | ISRO's Moon rover drove more than a hundred metres before going to sleep. | SUPPORTED | ✅ SUPPORTED | 0.99 (High) | CY3-12 Rover traverse and sleep mode | exact | SUPPORTED |
| T14 | India became the third country to soft-land on the Moon. | CONTRADICTED | ✅ CONTRADICTED | 1.00 (High) | CY3-06 India's place in lunar landing history | exact | CONTRADICTED |

## Failures

- **T06** “The rover deployed by Chandrayaan-3 was named Pragati.”: expected CONTRADICTED, got CONFLICTING. Stances: CY3-08:supports; CY3-01:insufficient; CY3-07:contradicts. Note: Wrong rover name: the rover is Pragyan (CY3-01, CY3-08).

_Caveat: 14 hand-written claims is a tiny test set, and some heuristics were added after inspecting failures on it, so these numbers are optimistic. Treat them as a sanity check, not a measure of real-world accuracy._