"""
Shared pieces for the Streamlit pages: the cached pipeline, verdict styling and the
evidence card. Every page imports from here so the app looks and behaves consistently.
"""
import html
import re
import sys
from pathlib import Path

import streamlit as st

# The AI pipeline lives in backend/app; make it importable from the Streamlit app.
BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app import db  # noqa: E402
from app.aggregator import CONFLICTING, CONTRADICTED, INSUFFICIENT, SUPPORTED, VERDICTS  # noqa: E402
from app.pipeline import ProofreadPipeline  # noqa: E402

ALL_TOPICS = "__all__"

# Verdict colours follow the status palette (good / critical / neutral / warning) and always
# come with the verdict written out, so the colour never carries the meaning on its own.
VERDICT_STYLE = {
    SUPPORTED: {"label": "Supported", "color": "#0ca30c", "bg": "rgba(12,163,12,0.10)"},
    CONTRADICTED: {"label": "Contradicted", "color": "#d03b3b", "bg": "rgba(208,59,59,0.10)"},
    INSUFFICIENT: {"label": "Insufficient evidence", "color": "#898781", "bg": "rgba(137,135,129,0.12)"},
    CONFLICTING: {"label": "Conflicting evidence", "color": "#d98e00", "bg": "rgba(250,178,25,0.15)"},
}
STANCE_LABEL = {
    "supports": "Supports",
    "contradicts": "Contradicts",
    "insufficient": "Neither confirms nor refutes",
    "not_assessed": "Not relevant",
}


@st.cache_resource(show_spinner="Loading the AI models (first start takes a while)…")
def get_pipeline() -> ProofreadPipeline:
    """Load spaCy, MiniLM and the NLI model once and share them across every page and user."""
    return ProofreadPipeline()


@st.cache_resource(show_spinner=False)
def backfill_test_claims() -> int:
    """Once per server start: give every topic that has passages but no test claims a generated set."""
    from app import claimgen
    nlp, made = get_pipeline().nlp, 0
    for c in db.get_collections():
        if c["passage_count"] and not db.get_test_claims(c["id"]):
            db.replace_auto_test_claims(c["id"], claimgen.generate(nlp, db.get_passages(c["id"]), c))
            made += 1
    return made


def topic_options() -> tuple[list[str], dict]:
    """Option ids for a topic picker ('All topics' first) and a label for each."""
    collections = db.get_collections()
    total = sum(c["passage_count"] for c in collections)
    labels = {ALL_TOPICS: f"All topics ({total} passages)"}
    labels.update({c["id"]: f"{c['name']} ({c['passage_count']} passages)" for c in collections})
    return [ALL_TOPICS] + [c["id"] for c in collections], labels


def topic_name(collection_id: str | None) -> str:
    if not collection_id:
        return "All topics"
    try:
        return db.get_collection(collection_id)["name"]
    except db.NotFound:
        return collection_id


def verdict_box(result: dict) -> None:
    """The big coloured verdict panel."""
    s = VERDICT_STYLE[result["verdict"]]
    if result["verdict"] == INSUFFICIENT:
        conf_label = "Confidence that the references don't settle it"
    else:
        conf_label = "Confidence"
    conf = result["confidence_label"]
    if result["confidence"] is not None:
        conf += f" ({result['confidence']:.0%})"
    st.markdown(
        f"""<div style="border-left:6px solid {s['color']};background:{s['bg']};padding:14px 18px;border-radius:10px;margin:6px 0 12px">
        <div style="font-size:1.15rem;font-weight:650;letter-spacing:.04em;color:{s['color']}">{html.escape(s['label']).upper()}</div>
        <div style="opacity:.8;margin-top:2px">{conf_label}: <b>{html.escape(conf)}</b> ·
        checked against <b>{html.escape(topic_name(result['collection_id']))}</b> ({result['passages_searched']} passages)</div>
        <div style="margin-top:8px">{html.escape(result['summary'])}</div></div>""",
        unsafe_allow_html=True,
    )
    if result["verdict"] == CONFLICTING:
        st.warning("The references disagree. A human reviewer must decide.")


def _highlight(text: str, terms: list[str]) -> str:
    """HTML-escape text and wrap every matched term in <mark>."""
    escaped = html.escape(text)
    if not terms:
        return escaped
    pattern = "|".join(re.escape(html.escape(t)) for t in sorted(terms, key=len, reverse=True))
    return re.sub(rf"\b({pattern})\b", r'<mark style="background:#fde68a;padding:0 2px;border-radius:3px">\1</mark>',
                  escaped, flags=re.I)


def passage_html(item: dict) -> str:
    """Passage text with shared words highlighted and the key sentence underlined in colour."""
    text, idx = item["text"], item.get("key_sentence")
    if idx is None or not item.get("sentences"):
        return _highlight(text, item["matched_terms"])
    key = item["sentences"][idx]["text"]
    start = text.find(key)
    if start < 0:
        return _highlight(text, item["matched_terms"])
    color = {"supports": "#0ca30c", "contradicts": "#d03b3b"}.get(item["stance"], "#6250d6")
    before, after = text[:start], text[start + len(key):]
    key_html = (f'<span style="background:rgba(98,80,214,0.08);border-bottom:3px solid {color};padding:1px 2px">'
                f"{_highlight(key, item['matched_terms'])}</span>")
    return _highlight(before, item["matched_terms"]) + key_html + _highlight(after, item["matched_terms"])


def _key_sentence_note(item: dict) -> str | None:
    idx = item.get("key_sentence")
    if idx is None:
        return None
    probs = item["sentences"][idx]["probs"]
    if item["stance"] == "supports":
        why = f"this sentence most strongly supports the claim (entails {probs['entailment']:.0%})"
    elif item["stance"] == "contradicts":
        why = f"this sentence most strongly contradicts the claim ({probs['contradiction']:.0%})"
    else:
        why = "this is the sentence closest to the claim, but it doesn't settle it"
    return f"**Key sentence** (underlined): {why}."


def evidence_card(item: dict, threshold: float) -> None:
    with st.container(border=True):
        top = st.columns([4, 1.4])
        top[0].markdown(f"**{item['title']}**")
        top[1].markdown(f"<div style='text-align:right'>{STANCE_LABEL[item['stance']]}</div>", unsafe_allow_html=True)
        st.caption(f"{item['source']} · {item['date'] or 'no date'} · [{item['url']}]({item['url']})" if item["url"]
                   else f"{item['source']} · {item['date'] or 'no date'}")
        st.markdown(f"<div style='line-height:1.6'>{passage_html(item)}</div>", unsafe_allow_html=True)
        note = _key_sentence_note(item)
        if note:
            st.caption(note)

        st.progress(min(max(item["similarity"], 0.0), 1.0),
                    text=f"Similarity {item['similarity']:.2f} (relevance threshold {threshold:.2f})")
        if item["probs"]:
            cols = st.columns(3)
            for col, (key, label) in zip(cols, [("entailment", "Supports"), ("contradiction", "Contradicts"),
                                                ("neutral", "Neutral")]):
                col.progress(item["probs"][key], text=f"{label} {item['probs'][key]:.0%}")
        for m in item["mismatches"]:
            st.warning(f"Number/date mismatch about “{m['about']}”: the claim says **{m['claim_value']}**, "
                       f"the passage says **{m['passage_value']}**.")
        if item.get("explanation"):
            st.caption(f"**Why:** {item['explanation']}")


def render_result(result: dict) -> None:
    """Verdict panel + relevant evidence + collapsed 'not relevant' passages."""
    verdict_box(result)
    threshold = result["thresholds"]["relevance"]
    relevant = [e for e in result["evidence"] if e["relevant"]]
    other = [e for e in result["evidence"] if not e["relevant"]]
    st.markdown(f"##### Relevant evidence ({len(relevant)})")
    if not relevant:
        st.info(f"No reference passage cleared the relevance threshold ({threshold}). This does **not** mean the "
                "claim is false, only that the references don't cover it.")
    for e in relevant:
        evidence_card(e, threshold)
    if other:
        with st.expander(f"Retrieved but not relevant ({len(other)})"):
            for e in other:
                evidence_card(e, threshold)
    st.caption(result["disclaimer"])


def review_form(result: dict, key: str) -> None:
    """Step 3: the human agrees or overrides; saved to the database."""
    saved_key = f"saved-{key}"
    with st.form(f"review-{key}", border=True):
        st.markdown("**Human review**: the verdict is only a suggestion. Read the evidence, then record your decision.")
        model = result["verdict"]
        options = [model] + [v for v in VERDICTS if v != model]
        choice = st.selectbox(
            "Reviewer verdict", options,
            format_func=lambda v: f"Agree: {VERDICT_STYLE[v]['label']}" if v == model
            else f"Override → {VERDICT_STYLE[v]['label']}")
        note = st.text_input("Note (optional)", placeholder="e.g. Passage CY3-05 gives a different date")
        if st.form_submit_button("Submit review", type="primary", disabled=st.session_state.get(saved_key, False)):
            db.add_review(result["claim"], model, choice, note, result["collection_id"])
            st.session_state[saved_key] = True
            st.rerun()
    if st.session_state.get(saved_key):
        st.success("Review saved to the database. See it on the Dashboard.")
