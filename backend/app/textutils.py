"""
Small text helpers shared by the extractor, the explainer and the mismatch check.

The most important piece is `extract_quantities`, which pulls numbers, years and
day-month dates out of a spaCy Doc together with "anchor" words (the verb/noun the
number is attached to). Anchors let us compare like with like: "launched on 14 July"
should only be compared with another *launch* date, not with a *landing* date.
"""
import re
from dataclasses import dataclass, field

# Entity types that usually signal a checkable fact.
FACT_ENTITY_TYPES = {"DATE", "CARDINAL", "PERCENT", "GPE", "ORG", "PERSON", "EVENT",
                     "ORDINAL", "QUANTITY", "MONEY", "LOC", "NORP", "FAC", "PRODUCT"}

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}

WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "hundred": 100, "thousand": 1000, "dozen": 12,
}
ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}
SCALE_WORDS = {"hundred": 100, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}

# Hedges/opinion markers: sentences containing these are opinions, not checkable claims.
HEDGE_PATTERNS = [
    r"\bi think\b", r"\bi feel\b", r"\bi believe\b", r"\bi guess\b", r"\bmaybe\b",
    r"\bperhaps\b", r"\bin my opinion\b", r"\bimo\b", r"\bimho\b", r"\bprobably\b",
    r"\bi feel like\b", r"\bseems like\b",
]


def clean_text(text: str) -> str:
    """Strip URLs, @mentions, hashtags, emoji and extra whitespace from post text."""
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[@#]\w+", " ", text)
    # Emoji and pictographs (most live outside the Basic Multilingual Plane) are often
    # used instead of a full stop, so turn them into a line break first...
    text = re.sub(r"[\U00010000-\U0010FFFF☀-➿️‍]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)   # so "history! \n" is seen as ending in "!"
    # ...then a line break before a capital letter becomes a sentence boundary.
    text = re.sub(r"(?<![.!?:])\n\s*(?=[A-Z0-9])", ". ", text)
    return re.sub(r"\s+", " ", text).strip()


# Verbs that describe a state rather than an event ("is located in", "is known as").
# The event-alignment gate is meant to tell different EVENTS apart, so these are ignored:
# a passage saying "the tower is in Paris" should still be able to contradict
# "the tower is located in London", even though it never uses the word "located".
STATIVE_VERBS = {"be", "have", "do", "locate", "situate", "base", "sit", "stand", "lie",
                 "call", "know", "consider", "regard", "remain", "seem"}


def claim_predicates(doc) -> set:
    """Main event verbs of a claim ('landed' -> 'land'), ignoring be/have/do and stative verbs."""
    return {normalise_key(t.lemma_) for t in doc
            if t.pos_ == "VERB" and t.lemma_.lower() not in STATIVE_VERBS}


def lemma_keys(doc) -> set:
    """Every normalised lemma in a Doc, for checking whether a passage uses a word."""
    return {normalise_key(t.lemma_) for t in doc if not t.is_punct}


def normalise_key(word: str) -> str:
    """Crude normaliser so 'wheeled'/'wheels'/'wheel' compare equal."""
    w = word.lower()
    for suffix in ("ed", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 4:
            return w[: -len(suffix)]
    return w


def content_keys(doc) -> dict:
    """
    Map normalised lemma -> surface word for every content word in a Doc.
    Content words are nouns, proper nouns, verbs, adjectives and numbers that
    are not stop words. Used to find terms shared by a claim and a passage.
    """
    keys = {}
    for tok in doc:
        if tok.is_stop or tok.is_punct or tok.is_space or len(tok.text) < 2:
            continue
        if tok.pos_ in {"NOUN", "PROPN", "VERB", "ADJ", "NUM"} or tok.like_num:
            keys.setdefault(normalise_key(tok.lemma_), tok.text)
    return keys


def fact_entities(doc) -> list:
    """Named entities that look like checkable facts (dates, places, numbers...)."""
    return [ent for ent in doc.ents if ent.label_ in FACT_ENTITY_TYPES]


# ------------------------------------------------------------------ quantities
@dataclass
class Quantity:
    kind: str                 # "year", "daymonth" or "number"
    value: object             # int, float or (month, day)
    text: str                 # surface text, for explanations
    anchors: set = field(default_factory=set)

    def describe(self) -> str:
        return self.text


def _anchors(token, hops: int = 3) -> set:
    """
    Collect the words a number is attached to: walk up the dependency tree
    from the number's token and keep noun/verb/adjective lemmas.
    """
    anchors = set()
    current = token
    for _ in range(hops):
        if current.head is current:          # reached the sentence root
            break
        current = current.head
        if current.pos_ in {"NOUN", "VERB", "ADJ", "PROPN"} and not current.is_stop:
            anchors.add(normalise_key(current.lemma_))
    return anchors


def _window_anchors(doc, index: int, width: int = 2) -> set:
    """Content words right after a number ('six-wheeled rover' -> wheel, rover)."""
    anchors = set()
    for tok in doc[index + 1: index + 1 + width + 1]:  # +1 skips a hyphen
        if tok.pos_ in {"NOUN", "VERB", "ADJ"} and not tok.is_stop:
            anchors.add(normalise_key(tok.lemma_))
    return anchors


def _token_number(tok):
    """Convert a token like '26', '1.5', 'six', 'fourth' or '14th' to a number."""
    t = tok.text.lower().replace(",", "")
    if t in WORD_NUMBERS:
        return WORD_NUMBERS[t]
    if t in ORDINAL_WORDS:
        return ORDINAL_WORDS[t]
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:st|nd|rd|th)?", t)
    if m:
        return float(m.group(1)) if "." in m.group(1) else int(m.group(1))
    return None


def _parse_daymonth(text: str):
    """Find '14 July' or 'July 14' in a date string; return (month, day) or None."""
    t = text.lower()
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]+)", t)
    if m and m.group(2) in MONTHS:
        return (MONTHS[m.group(2)], int(m.group(1)))
    m = re.search(r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\b", t)
    if m and m.group(1) in MONTHS:
        return (MONTHS[m.group(1)], int(m.group(2)))
    return None


def extract_quantities(doc) -> list:
    """Return every year, day-month date and plain number found in a Doc."""
    quantities = []
    used = set()  # token positions already consumed (by a date or a scale word)

    # 1) Dates: split into a year and a (month, day) pair so each can be compared.
    for ent in doc.ents:
        if ent.label_ != "DATE":
            continue
        anchors = _anchors(ent.root)
        for year in re.findall(r"\b(1[89]\d\d|20\d\d)\b", ent.text):
            quantities.append(Quantity("year", int(year), year, anchors))
        daymonth = _parse_daymonth(ent.text)
        if daymonth:
            label = re.sub(r"\s*\b(1[89]\d\d|20\d\d)\b", "", ent.text).strip(" ,")
            quantities.append(Quantity("daymonth", daymonth, label, anchors))
        used.update(range(ent.start, ent.end))

    # 2) Plain numbers and ordinals outside dates ("six", "26 kg", "fourth", "a hundred").
    for tok in doc:
        if tok.i in used or tok.ent_type_ in {"TIME"}:
            continue
        value = _token_number(tok)
        if value is None:
            continue
        text = tok.text
        # Combine "1.5 million" / "two hundred" into one value.
        nxt = doc[tok.i + 1] if tok.i + 1 < len(doc) else None
        if nxt is not None and nxt.text.lower() in SCALE_WORDS and tok.text.lower() not in SCALE_WORDS:
            value = value * SCALE_WORDS[nxt.text.lower()]
            text = f"{tok.text} {nxt.text}"
            used.add(nxt.i)
        # A bare four-digit 19xx/20xx outside a DATE entity is still a year.
        kind = "year" if isinstance(value, int) and 1800 <= value <= 2099 and len(tok.text) == 4 else "number"
        anchors = _anchors(tok) | _window_anchors(doc, tok.i)
        quantities.append(Quantity(kind, value, text, anchors))
    return quantities


def compare_quantities(claim_q: list, passage_q: list):
    """
    Compare claim numbers with passage numbers.

    Returns (matches, mismatches):
      matches    - claim values that also appear in the passage
      mismatches - claim values where the passage gives a *different* value of the
                   same kind about the same thing (overlapping anchor words)
    Claim numbers the passage never talks about are neither: they are simply not covered.
    """
    matches, mismatches = [], []
    for cq in claim_q:
        same_kind = [pq for pq in passage_q if pq.kind == cq.kind]
        if any(pq.value == cq.value for pq in same_kind):
            matches.append(cq.text)
            continue
        # Only call it a mismatch if the passage number describes the same thing.
        related = [pq for pq in same_kind if pq.anchors & cq.anchors]
        if related:
            mismatches.append({
                "claim_value": cq.text,
                "passage_value": ", ".join(sorted({pq.text for pq in related})),
                "about": ", ".join(sorted(cq.anchors & set().union(*(pq.anchors for pq in related)))),
            })
    return matches, mismatches
