"""
Claim extraction: pick the single most "checkable" sentence from a social media post.

Steps
  1. Clean the post (remove URLs, hashtags, emoji).
  2. Split it into sentences with spaCy.
  3. Discard sentences that are not factual claims: questions, opinions/hedges
     ("I think", "maybe", ...), and very short sentences.
  4. Score what is left by how many fact-like signals it contains:
     named entities, numbers and factual verbs.
  5. Return the best sentence plus every candidate with its score and reasons,
     so a human can pick a different one if the heuristic gets it wrong.
"""
import re

from . import config
from .textutils import HEDGE_PATTERNS, clean_text, fact_entities

# Verbs that usually introduce a checkable statement of fact.
FACTUAL_VERBS = {
    "launch", "land", "become", "confirm", "detect", "find", "discover", "record",
    "name", "cost", "carry", "reach", "enter", "build", "develop", "announce",
    "measure", "weigh", "travel", "traverse", "drive", "deploy", "operate", "lead",
    "touch", "watch", "orbit", "send", "achieve", "have", "be",
}
# Weights for each signal. Entities count most because they pin down *what* is claimed.
WEIGHT_ENTITY = 2.0
WEIGHT_NUMBER = 1.0
WEIGHT_FACT_VERB = 1.0
# Exclamations, hype and calls to action make a sentence less likely to be the claim.
SUBJECTIVE_WORDS = {"amazing", "proud", "proudest", "goosebumps", "wow", "incredible",
                    "heroes", "follow", "tag", "share", "like", "believe", "honestly"}
WEIGHT_SUBJECTIVE = -1.5


class ClaimExtractor:
    def __init__(self, nlp):
        self.nlp = nlp  # a loaded spaCy pipeline (shared with the rest of the app)

    def _discard_reason(self, sent) -> str | None:
        """Return why a sentence is not a claim, or None if it should be kept."""
        text = sent.text.strip()
        lower = text.lower()
        words = [t for t in sent if not t.is_punct and not t.is_space]
        if text.endswith("?"):
            return "question"
        for pattern in HEDGE_PATTERNS:
            if re.search(pattern, lower):
                return "opinion or hedge"
        if len(words) < config.MIN_CLAIM_TOKENS:
            return "too short"
        return None

    def _score(self, sent) -> tuple[float, list]:
        """Score a sentence and return human-readable reasons for the score."""
        entities = fact_entities(sent)
        numbers = [t for t in sent if t.like_num or any(c.isdigit() for c in t.text)]
        verbs = [t for t in sent if t.pos_ in {"VERB", "AUX"} and t.lemma_.lower() in FACTUAL_VERBS]
        subjective = [t for t in sent if t.lower_ in SUBJECTIVE_WORDS]

        score = (WEIGHT_ENTITY * len(entities) + WEIGHT_NUMBER * len(numbers)
                 + WEIGHT_FACT_VERB * min(len(verbs), 2) + WEIGHT_SUBJECTIVE * len(subjective))
        reasons = []
        if entities:
            reasons.append("entities: " + ", ".join(f"{e.text} ({e.label_})" for e in entities))
        if numbers:
            reasons.append(f"{len(numbers)} number(s)")
        if verbs:
            reasons.append("factual verb: " + ", ".join(sorted({v.lemma_ for v in verbs})))
        if subjective:
            reasons.append("subjective words: " + ", ".join(t.text for t in subjective))
        return round(score, 2), reasons

    def extract(self, post_text: str) -> dict:
        """Return {'claim': best sentence or '', 'candidates': [...all sentences...]}."""
        doc = self.nlp(clean_text(post_text))
        candidates = []
        for sent in doc.sents:
            text = sent.text.strip()
            if not text:
                continue
            # Drop a lead-in such as "Fun fact for your Monday:" when what follows
            # is long enough to be a sentence on its own.
            lead, colon, rest = text.partition(": ")
            if colon and len(rest.split()) >= config.MIN_CLAIM_TOKENS:
                sent = self.nlp(rest)
                text = rest.strip()
            reason = self._discard_reason(sent)
            if reason:
                candidates.append({"sentence": text, "score": 0.0, "kept": False,
                                   "reasons": [f"discarded: {reason}"]})
                continue
            score, reasons = self._score(sent)
            candidates.append({"sentence": text, "score": score, "kept": True, "reasons": reasons})

        # Best-scoring kept sentences first; discarded ones go to the end.
        candidates.sort(key=lambda c: (c["kept"], c["score"]), reverse=True)
        best = next((c["sentence"] for c in candidates if c["kept"]), "")
        return {"claim": best, "candidates": candidates}
