"""
Automatic test-claim generation for topics added in the app.

When a curator adds sources to a topic, Proofread builds labelled test claims from the
passages, so every topic can be evaluated, not only the built-in one. The spaCy model
finds fact sentences and the names, dates and numbers inside them; simple, explainable
rules then turn them into claims whose correct answer is known by construction:

  SUPPORTED              a fact sentence taken from one passage (lightly tidied)
  CONTRADICTED           a fact sentence with ONE detail changed: a year, date, number,
                         ordinal ("third" -> "fifth") or a name/place swapped for another
  INSUFFICIENT_EVIDENCE  a plausible statement about the topic's main subject on something
                         no passage mentions (e.g. a postage stamp or a film about it)

How many: one per passage up to 10 (8 passages -> 8 claims; 40 passages -> 10), and the
curator can ask for more. About 40% supported, 40% contradicted, 20% not covered.

Why rules and not a text-generating model: the expected answer of a test must be right.
A generative model can write a "false" claim that is accidentally true, or a "true" one
the passages don't actually say. Rule-made claims are predictable and explainable, and
the curator can still edit or delete any of them.

Caveat (shown in the app): these claims are built from the same passages the system
searches. They test whether Proofread can confirm or reject facts stated in its own sources,
not how it does on real social media posts, and a generated claim can occasionally be odd
(e.g. a name swapped for a place spaCy mislabelled). Review them before relying on the numbers.
"""
import random
import re
from collections import Counter

from .aggregator import CONTRADICTED, INSUFFICIENT, SUPPORTED
from .textutils import MONTHS, ORDINAL_WORDS, WORD_NUMBERS, content_keys, normalise_key

DEFAULT_MAX = 10              # one claim per passage, up to this many by default
SWAP_LABELS = {"PERSON", "GPE", "ORG", "LOC", "FAC", "NORP", "EVENT", "PRODUCT", "WORK_OF_ART"}
SUBJECT_LABELS = {"PERSON", "GPE", "ORG", "LOC", "FAC", "EVENT", "PRODUCT", "WORK_OF_ART"}
PRONOUN_START = {"it", "its", "they", "their", "he", "she", "his", "her", "this", "these", "those",
                 "that", "there", "such", "both", "however", "also", "but", "and"}
# Replacements used when the topic has no other entity of the same kind to swap in.
FALLBACK_ENTITIES = {
    "PERSON": ["John Mitchell", "Maria Fernandes", "Rahul Verma", "Anna Schmidt"],
    "GPE": ["London", "Tokyo", "Brazil", "Canada", "Egypt"],
    "ORG": ["the United Nations", "the World Bank", "Microsoft", "the Red Cross"],
    "NORP": ["German", "Japanese", "Brazilian", "Canadian"],
    "LOC": ["the Pacific Ocean", "the Alps", "the Sahara Desert"],
}
# "Not covered" templates: (claim template, words that must NOT appear in the topic's passages).
NOT_COVERED_TEMPLATES = [
    ("{s} was the subject of a Hollywood film released in {y}.", {"film", "hollywood", "movie"}),
    ("A postage stamp honouring {s} was issued in Japan in {y}.", {"stamp", "postage"}),
    ("{s} received a donation of 5 million dollars from a technology company in {y}.", {"donation", "donate"}),
    ("{s} won an international design award in {y}.", {"award"}),
    ("A museum dedicated to {s} opened in Singapore in {y}.", {"museum", "singapore"}),
    ("{s} was featured in a popular video game released in {y}.", {"video", "game"}),
    ("A song about {s} topped the music charts in {y}.", {"song", "chart"}),
    ("{s} got its own official mobile app in {y}.", {"app", "mobile"}),
]
POST_TEMPLATES = [
    "Did you know? {c} Share this with your friends.",
    "Fun fact for today: {c}",
    "Just read this. {c} Thoughts?",
    "{c} I had no idea until today.",
    "Saw this on my feed: {c} Is this true?",
    "Quick history lesson. {c} Pass it on.",
]


def default_count(n_passages: int) -> int:
    """One test claim per passage, up to 10."""
    return min(n_passages, DEFAULT_MAX)


# ------------------------------------------------------------------ picking fact sentences
def _tidy(text: str) -> str:
    text = re.sub(r"\s*\([^)]*\)", "", text)          # drop bracketed asides
    text = re.sub(r"\[\d+\]", "", text)                # drop footnote markers
    text = text.split("; ")[0]                          # keep the first clause of a long sentence
    text = re.sub(r"\s+", " ", text).strip().rstrip(".,;:") + "."
    return text[0].upper() + text[1:]


def _fact_sentences(nlp, passage: dict, topic_words: set) -> list:
    """
    Sentences that state a self-contained fact (6-30 words, a name/date/number, no leading
    pronoun), best first: ones that mention the topic and contain a checkable detail.
    """
    scored = []
    for sent in nlp(passage["text"]).sents:
        words = [t for t in sent if not t.is_punct]
        first = sent[0].lower_ if len(sent) else ""
        if not (6 <= len(words) <= 30) or first in PRONOUN_START or sent.text.strip().endswith("?"):
            continue
        has_detail = any(t.like_num for t in sent) or any(e.label_ in {"DATE", "CARDINAL", "ORDINAL"} for e in sent.ents)
        if not (sent.ents or has_detail):
            continue
        mentions_topic = any(t.lower_ in topic_words for t in sent)
        scored.append((2 * mentions_topic + has_detail - len(words) / 100, sent))
    return [s for _, s in sorted(scored, key=lambda x: -x[0])]


# ------------------------------------------------------------------ making a false version
def _change_year(text, topic_years, rng):
    years = re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", text)
    if not years:
        return None
    old = rng.choice(years)
    for _ in range(20):
        new = int(old) + rng.choice([-12, -8, -5, -3, 3, 5, 8, 12])
        if str(new) not in topic_years and new <= 2030:
            return re.sub(rf"\b{old}\b", str(new), text, count=1), f"changed the year {old} to {new}"
    return None


def _change_daymonth(text, rng):
    m = re.search(r"\b(\d{1,2})(\s+(?:" + "|".join(k.capitalize() for k in MONTHS) + r"))\b", text)
    if not m:
        return None
    day = int(m.group(1))
    new = day + rng.choice([-9, -6, -4, 4, 6, 9])
    new = new if 1 <= new <= 28 else (day + 5 if day + 5 <= 28 else day - 5)
    return text[:m.start(1)] + str(new) + text[m.end(1):], f"changed the date {day}{m.group(2)} to {new}{m.group(2)}"


def _change_number(text, rng):
    # plain numbers that are not years and not part of a date
    candidates = [m for m in re.finditer(r"\b\d[\d,]*(?:\.\d+)?\b", text)
                  if not re.fullmatch(r"1[5-9]\d\d|20\d\d", m.group())
                  and not re.match(r"\s+(?:" + "|".join(k.capitalize() for k in MONTHS) + r")\b", text[m.end():])]
    if not candidates:
        return None
    m = rng.choice(candidates)
    raw = m.group().replace(",", "")
    value = float(raw) if "." in raw else int(raw)
    if value <= 12:
        new = value + rng.choice([2, 3, 4])
    else:
        new = value * rng.choice([0.6, 1.5, 2])
        new = round(new, 1) if isinstance(value, float) else int(round(new))
    if new == value:
        return None
    new_text = f"{new:,}" if isinstance(new, int) and "," in m.group() else str(new)
    return text[:m.start()] + new_text + text[m.end():], f"changed the number {m.group()} to {new_text}"


def _change_word_number(text, rng):
    words = {**ORDINAL_WORDS, **{k: v for k, v in WORD_NUMBERS.items() if 2 <= v <= 12}}
    hits = [m for m in re.finditer(r"\b(" + "|".join(words) + r")\b", text, re.I)]
    if not hits:
        return None
    m = rng.choice(hits)
    word = m.group().lower()
    pool = ORDINAL_WORDS if word in ORDINAL_WORDS else {k: v for k, v in WORD_NUMBERS.items() if 2 <= v <= 12}
    options = [w for w, v in pool.items() if v != words[word] and abs(v - words[word]) <= 3]
    new = rng.choice(options)
    new = new.capitalize() if m.group()[0].isupper() else new
    return text[:m.start()] + new + text[m.end():], f"changed “{m.group()}” to “{new}”"


def _swap_entity(sent, text, topic_entities, rng):
    ents = [e for e in sent.ents if e.label_ in SWAP_LABELS and e.text in text]
    if not ents:
        return None
    ent = rng.choice(ents)
    others = [t for t in topic_entities.get(ent.label_, []) if t.lower() not in sent.text.lower()]
    pool = others or FALLBACK_ENTITIES.get(ent.label_, [])
    pool = [p for p in pool if p.lower() != ent.text.lower()]
    if not pool:
        return None
    new = rng.choice(pool)
    return text.replace(ent.text, new, 1), f"swapped “{ent.text}” for “{new}”"


def _make_false(sent, topic_entities, topic_years, rng):
    """Change exactly one detail; numbers and dates first (cleanest contradictions), names last."""
    text = _tidy(sent.text)
    def fix_article(result):
        if not result:
            return result
        # "an 49-storey" -> "a 49-storey" (keep "an 8", "an 11", "an 18")
        return re.sub(r"\b([Aa])n (?=(?!8|11\b|18\b)\d)", r"\1 ", result[0]), result[1]

    for change in (lambda: _change_year(text, topic_years, rng), lambda: _change_daymonth(text, rng),
                   lambda: _change_number(text, rng), lambda: _change_word_number(text, rng),
                   lambda: _swap_entity(sent, text, topic_entities, rng)):
        result = fix_article(change())
        if result and result[0] != text:
            return result
    return None


# ------------------------------------------------------------------ the topic's main subject
def _with_article(name: str, joined: str) -> str:
    """'Eiffel Tower' -> 'the Eiffel Tower' when the passages mostly write it with 'the'."""
    low, n = joined.lower(), name.lower()
    if n.startswith("the ") or low.count(n) == 0:
        return name
    return f"the {name}" if low.count(f"the {n}") * 2 >= low.count(n) else name


def _main_subject(docs, topic_name: str) -> str:
    """The topic's own name, or the closest name the passages use for it ("2023 ICC Men's Cricket World Cup")."""
    joined = " ".join(d.text for d in docs)
    if topic_name.lower() in joined.lower():
        return _with_article(topic_name, joined)
    # A name in the passages that shares most of the topic's words ("2023 ICC Men's Cricket World Cup").
    topic_words = {w.lower() for w in re.findall(r"\w+", topic_name)}
    overlap = lambda text: len(topic_words & {w.lower() for w in re.findall(r"\w+", text)})  # noqa: E731
    close = Counter(e.text for doc in docs for e in doc.ents if overlap(e.text) * 2 >= len(topic_words))
    if close:   # most shared words first, then most frequent
        best = _with_article(max(close, key=lambda text: (overlap(text), close[text])), joined)
        # an event/thing named in several words reads better with "the" ("the Cricket World Cup")
        return best if best.lower().startswith("the ") or len(best.split()) < 2 else f"the {best}"
    # Otherwise use the topic's own name: a random frequent name ("Rosebank") could be off-topic.
    return topic_name


# ------------------------------------------------------------------ main entry point
def generate(nlp, passages: list[dict], topic: dict, count: int | None = None, seed: int = 0) -> list[dict]:
    """
    Build `count` labelled test claims (default: one per passage, up to 10) for a topic.
    Returns dicts ready for db.replace_auto_test_claims().
    """
    if not passages:
        return []
    count = count or default_count(len(passages))
    rng = random.Random(f"{topic['id']}-{len(passages)}-{seed}")   # same input -> same claims
    docs = [nlp(p["text"]) for p in passages]
    topic_entities: dict[str, list[str]] = {}
    for doc in docs:
        for e in doc.ents:
            if e.label_ in SWAP_LABELS and e.text not in topic_entities.setdefault(e.label_, []):
                topic_entities[e.label_].append(e.text)
    joined = " ".join(p["text"] for p in passages)
    topic_years = set(re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", joined))
    topic_keys = set(content_keys(nlp(joined[:100_000])))
    subject = _main_subject(docs, topic["name"])

    n_not_covered = max(1, round(count * 0.2)) if count >= 3 else 0
    n_false = round(count * 0.4)
    n_true = count - n_false - n_not_covered

    # Fact sentences, visiting passages in a shuffled order so claims spread over the topic.
    order = list(range(len(passages)))
    rng.shuffle(order)
    topic_words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", topic["name"] + " " + subject)}
    facts = [(passages[i], s) for i in order for s in _fact_sentences(nlp, passages[i], topic_words)[:2]]
    # Best sentences first, while still spreading over passages (at most 2 per passage).
    facts.sort(key=lambda f: -(any(t.lower_ in topic_words for t in f[1]) + any(t.like_num for t in f[1])))
    claims, used = [], set()

    def add(claim, verdict, note):
        key = claim.lower()
        if key not in used:
            used.add(key)
            claims.append((claim, verdict, note))

    # Alternate true/false so both draw from many passages; one sentence is used once.
    want = {SUPPORTED: n_true, CONTRADICTED: n_false}
    made = Counter()
    for p, sent in facts:
        if made[SUPPORTED] >= want[SUPPORTED] and made[CONTRADICTED] >= want[CONTRADICTED]:
            break
        want_false = made[CONTRADICTED] < want[CONTRADICTED] and (
            made[SUPPORTED] >= want[SUPPORTED] or made[CONTRADICTED] <= made[SUPPORTED])
        if want_false:
            changed = _make_false(sent, topic_entities, topic_years, rng)
            if changed:
                add(changed[0], CONTRADICTED, f"Auto-generated from “{p['title']}”: {changed[1]}.")
                made[CONTRADICTED] += 1
                continue
        if made[SUPPORTED] < want[SUPPORTED]:
            add(_tidy(sent.text), SUPPORTED, f"Auto-generated: stated in “{p['title']}”.")
            made[SUPPORTED] += 1

    # Not-covered claims about the main subject, skipping templates whose key words appear in the passages.
    templates = [t for t, banned in NOT_COVERED_TEMPLATES if not {normalise_key(w) for w in banned} & topic_keys]
    rng.shuffle(templates)
    years = [y for y in range(1990, 2026) if str(y) not in topic_years]
    for template in templates[:n_not_covered]:
        claim = template.format(s=subject, y=rng.choice(years))
        add(claim[0].upper() + claim[1:], INSUFFICIENT,
            "Auto-generated: a plausible statement no passage mentions, so the right answer is insufficient evidence.")

    # If the passages ran out of usable sentences, top up with more true or not-covered claims.
    for p, sent in facts:
        if len(claims) >= count:
            break
        add(_tidy(sent.text), SUPPORTED, f"Auto-generated: stated in “{p['title']}”.")
    for template in templates[n_not_covered:]:
        if len(claims) >= count:
            break
        claim = template.format(s=subject, y=rng.choice(years))
        add(claim[0].upper() + claim[1:], INSUFFICIENT,
            "Auto-generated: a plausible statement no passage mentions, so the right answer is insufficient evidence.")

    rng.shuffle(claims)
    prefix = re.sub(r"[^A-Z0-9]", "", topic["name"].upper())[:4] or "TOP"
    return [{
        "id": f"{prefix}-AUTO-{i + 1:02d}-{topic['id']}",
        "collection_id": topic["id"], "claim": claim, "expected_verdict": verdict, "note": note,
        "post_text": rng.choice(POST_TEMPLATES).format(c=claim),
    } for i, (claim, verdict, note) in enumerate(claims[:count])]


# ------------------------------------------------------------------ keeping topics' test claims up to date
def uses_generated_tests(collection_id: str) -> bool:
    """Every topic except one with hand-written tests (the built-in Chandrayaan-3 set) uses generated claims."""
    from . import db
    return not db.get_test_claims(collection_id, origin="seed")


def refresh(nlp, collection: dict, count: int | None = None) -> int:
    """Regenerate a topic's test claims from its current passages; returns how many were made."""
    from . import db
    if not uses_generated_tests(collection["id"]):
        return 0
    items = generate(nlp, db.get_passages(collection["id"]), collection, count=count)
    db.replace_auto_test_claims(collection["id"], items)
    return len(items)


def backfill(nlp) -> int:
    """Give every topic that has passages but no test claims a generated set (run at startup)."""
    from . import db
    made = 0
    for c in db.get_collections():
        if c["passage_count"] and not db.get_test_claims(c["id"]):
            made += refresh(nlp, c) > 0
    return made
