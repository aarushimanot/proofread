"""
Plain-English explanations, built from templates (no LLM involved).

Each evidence card gets an explanation covering:
  * the similarity score and whether it cleared the relevance threshold
  * shared keywords/entities between claim and passage
  * numbers/dates that match or mismatch
  * the NLI label and its probability, and what that means for the verdict
"""
from . import config
from .aggregator import CONFLICTING, CONTRADICTED, INSUFFICIENT, SUPPORTED

STANCE_PHRASES = {
    "supports": "the passage states what the claim says (it entails the claim)",
    "contradicts": "the passage says something incompatible with the claim",
    "insufficient": "the passage is on topic but neither clearly confirms nor clearly rules out the claim",
}


def _fmt(p: float) -> str:
    return f"{p * 100:.0f}%"


def explain_passage(item: dict) -> str:
    """Build the explanation for one retrieved passage."""
    sim, threshold = item["similarity"], config.RELEVANCE_THRESHOLD
    terms = item["matched_terms"]
    parts = []

    if not item["relevant"]:
        parts.append(f"Similarity {sim:.2f} is below the relevance threshold of {threshold:.2f}, "
                     "so this passage was NOT used for the verdict.")
        if terms:
            parts.append(f"It shares only general terms with the claim ({', '.join(terms[:5])}), "
                         "which suggests it is about a related but different topic.")
        else:
            parts.append("It shares no meaningful keywords with the claim.")
        return " ".join(parts)

    parts.append(f"Similarity {sim:.2f} clears the relevance threshold of {threshold:.2f}, "
                 "so the passage is treated as relevant.")
    if terms:
        parts.append(f"Shared terms: {', '.join(terms[:8])}.")
    if item["number_matches"]:
        parts.append(f"Numbers/dates that match: {', '.join(item['number_matches'])}.")
    for m in item["mismatches"]:
        parts.append(f"⚠ Number/date mismatch about '{m['about']}': the claim says {m['claim_value']} "
                     f"but the passage says {m['passage_value']}.")

    probs = item["probs"]
    top_label = max(probs, key=probs.get)
    parts.append(f"The NLI model's strongest label is {top_label} ({_fmt(probs[top_label])}).")
    if item["mismatches"]:
        raw = item["raw_probs"]
        parts.append(f"Because of the mismatch, contradiction was nudged from {_fmt(raw['contradiction'])} "
                     f"to {_fmt(probs['contradiction'])} (heuristic).")
    if item.get("gated"):
        verbs = ", ".join(item.get("claim_predicates", []))
        parts.append(f"The model leaned towards contradiction, but the passage never uses the claim's main "
                     f"verb(s) ({verbs}), so it most likely describes a different event. "
                     "The contradiction was therefore not counted (event-alignment heuristic).")
    parts.append(f"Judgement: {STANCE_PHRASES[item['stance']]}.")
    return " ".join(parts)


def summarize(verdict: str, evidence: list[dict]) -> str:
    """One overall sentence summarising why the verdict was reached."""
    relevant = [e for e in evidence if e["relevant"]]
    supports = [e["title"] for e in relevant if e["stance"] == "supports"]
    contradicts = [e["title"] for e in relevant if e["stance"] == "contradicts"]

    if not relevant:
        return ("No reference passage covers this claim. This does NOT mean the claim is false; "
                "the curated references simply do not address it.")
    if verdict == SUPPORTED:
        return f"Supported by {len(supports)} reference passage(s), e.g. “{supports[0]}”, and no relevant passage contradicts it."
    if verdict == CONTRADICTED:
        return f"Contradicted by {len(contradicts)} reference passage(s), e.g. “{contradicts[0]}”, and no relevant passage supports it."
    if verdict == CONFLICTING:
        return (f"The references disagree: “{supports[0]}” supports the claim but "
                f"“{contradicts[0]}” contradicts it. A human reviewer needs to decide.")
    # INSUFFICIENT with relevant-but-neutral passages.
    return (f"{len(relevant)} related passage(s) were found, but none clearly supports or contradicts the claim. "
            "This does NOT mean the claim is false.")
