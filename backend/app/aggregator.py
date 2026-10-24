"""
Verdict rules: turn per-passage NLI results into one overall verdict.

These are simple, explicit rules (no learning) so that every verdict can be traced:

  * no relevant passage                      -> INSUFFICIENT_EVIDENCE
  * per relevant passage:
        entailment    >= 0.6                 -> "supports"
        contradiction >= 0.6                 -> "contradicts"
        otherwise                            -> "insufficient"
  * some support, no contradiction           -> SUPPORTED
  * some contradiction, no support           -> CONTRADICTED
  * both                                     -> CONFLICTING (needs human review)
  * neither                                  -> INSUFFICIENT_EVIDENCE

Crucially, "no match" never becomes CONTRADICTED. A claim is only CONTRADICTED
when a relevant passage actively says something incompatible with it.
"""
from . import config

SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
CONFLICTING = "CONFLICTING"
VERDICTS = (SUPPORTED, CONTRADICTED, INSUFFICIENT, CONFLICTING)


def apply_mismatch_nudge(probs: dict, nudge: float = config.MISMATCH_NUDGE) -> dict:
    """
    HEURISTIC: a relevant passage gives a different number/date for the same thing.

    NLI models are known to be weak at spotting changed numbers, so we move up to
    `nudge` probability mass into "contradiction", taking it from "entailment"
    first and then from "neutral". The three probabilities still sum to 1.
    """
    adjusted = dict(probs)
    take_from_entail = min(adjusted["entailment"], nudge)
    take_from_neutral = min(adjusted["neutral"], nudge - take_from_entail)
    adjusted["entailment"] -= take_from_entail
    adjusted["neutral"] -= take_from_neutral
    adjusted["contradiction"] += take_from_entail + take_from_neutral
    return {k: round(min(max(v, 0.0), 1.0), 4) for k, v in adjusted.items()}


def passage_stance(probs: dict) -> str:
    """Classify one passage's stance towards the claim from its NLI probabilities."""
    if probs["entailment"] >= config.ENTAILMENT_THRESHOLD:
        return "supports"
    if probs["contradiction"] >= config.CONTRADICTION_THRESHOLD:
        return "contradicts"
    return "insufficient"


def confidence_label(score: float | None) -> str:
    if score is None:
        return "Low"
    if score >= config.CONFIDENCE_HIGH:
        return "High"
    if score >= config.CONFIDENCE_MEDIUM:
        return "Medium"
    return "Low"


def aggregate(evidence: list[dict]) -> dict:
    """
    Combine evidence items (each with 'relevant', 'stance' and 'probs') into a verdict.

    Confidence = the highest probability, among relevant passages, of the label that
    produced the verdict (e.g. the best entailment score for SUPPORTED).
    """
    relevant = [e for e in evidence if e["relevant"]]
    if not relevant:
        return {"verdict": INSUFFICIENT, "confidence": None, "confidence_label": "Low"}

    supports = [e for e in relevant if e["stance"] == "supports"]
    contradicts = [e for e in relevant if e["stance"] == "contradicts"]

    if supports and not contradicts:
        verdict, score = SUPPORTED, max(e["probs"]["entailment"] for e in supports)
    elif contradicts and not supports:
        verdict, score = CONTRADICTED, max(e["probs"]["contradiction"] for e in contradicts)
    elif supports and contradicts:
        # Disagreeing evidence: report confidence as Low by design, a human must decide.
        verdict = CONFLICTING
        score = max(max(e["probs"]["entailment"] for e in supports),
                    max(e["probs"]["contradiction"] for e in contradicts))
        return {"verdict": verdict, "confidence": round(score, 4), "confidence_label": "Low"}
    else:
        verdict, score = INSUFFICIENT, max(e["probs"]["neutral"] for e in relevant)

    return {"verdict": verdict, "confidence": round(score, 4), "confidence_label": confidence_label(score)}
