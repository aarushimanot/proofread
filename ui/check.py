"""
"Check a claim" page: paste a post, extract the claim(s), check them, review them.

Two modes:
  One claim      the classic flow: pick (or type) one claim and check it
  Every claim    find every factual sentence in the post and check each one separately
"""
import json
import uuid

import streamlit as st

from app import config, db
from ui.common import (ALL_TOPICS, VERDICT_STYLE, get_pipeline, render_result, review_form,
                       topic_options)

ONE, EVERY = "One claim", "Every claim in the post"


def _examples() -> list[dict]:
    """Single-claim test claims plus the multi-claim test posts, for the 'Load example' box."""
    items = [{"key": t["id"], "label": f"{t['id']} · {t['claim']}", "post": t["post_text"],
              "topic": t["collection_id"], "mode": ONE} for t in db.get_test_claims()]
    with open(config.MULTI_CLAIM_TESTS_PATH, encoding="utf-8") as f:
        items += [{"key": m["id"], "label": f"{m['id']} · multi-claim post ({len(m['claims'])} claims)",
                   "post": m["post_text"], "topic": m["collection_id"], "mode": EVERY} for m in json.load(f)]
    return items


def _reset_results():
    for k in ("result", "multi", "candidates"):
        st.session_state.pop(k, None)
    st.session_state["run_id"] = uuid.uuid4().hex[:8]   # fresh keys for new review forms


def _load_example():
    ex = next((e for e in _examples() if e["label"] == st.session_state.get("example")), None)
    if ex:
        st.session_state.update(post=ex["post"], topic=ex["topic"], mode=ex["mode"], claim="")
        _reset_results()


def _pick_candidate():
    st.session_state["claim"] = st.session_state["candidate_choice"]
    st.session_state.pop("result", None)


def page():
    pipeline = get_pipeline()
    st.session_state.setdefault("topic", "chandrayaan-3")
    st.session_state.setdefault("mode", ONE)
    st.session_state.setdefault("run_id", "start")

    st.header("Check a claim")
    ids, labels = topic_options()
    if st.session_state["topic"] not in ids:
        st.session_state["topic"] = ALL_TOPICS
    left, right = st.columns([2, 3])
    left.selectbox("Check against topic", ids, format_func=labels.get, key="topic", on_change=_reset_results)
    right.selectbox("Load example (optional)", [e["label"] for e in _examples()], index=None,
                    placeholder="Choose a test claim or multi-claim post…", key="example", on_change=_load_example)
    collection_id = None if st.session_state["topic"] == ALL_TOPICS else st.session_state["topic"]
    if collection_id and db.get_collection(collection_id) and not db.get_passages(collection_id):
        st.warning("This topic has no reference passages yet, so every claim will be “Insufficient evidence”. "
                   "Add trusted sources on the **Lie-brary** page first.")

    # ---------------------------------------------------------------- step 1
    st.subheader("1 · Paste a post")
    st.text_area("Social media post", key="post", height=110, placeholder="Paste a social media post here…",
                 on_change=_reset_results)
    st.radio("What should Proofread check?", [ONE, EVERY], key="mode", horizontal=True, on_change=_reset_results,
             help="“Every claim” finds each factual sentence in the post and checks them one by one.")

    if st.session_state["mode"] == ONE:
        _one_claim(pipeline, collection_id)
    else:
        _every_claim(pipeline, collection_id)


def _one_claim(pipeline, collection_id):
    if st.button("Extract claim", disabled=not st.session_state.get("post", "").strip()):
        out = pipeline.extract(st.session_state["post"])
        st.session_state["candidates"] = out["candidates"]
        st.session_state["claim"] = out["claim"]
        st.session_state.pop("result", None)
        if not out["claim"]:
            st.warning("No checkable factual sentence was found. Type the claim yourself below.")

    candidates = st.session_state.get("candidates", [])
    kept = [c for c in candidates if c["kept"]]
    if kept:
        st.radio("Candidate sentences (best first). Pick one to use it as the claim:",
                 [c["sentence"] for c in kept], key="candidate_choice", on_change=_pick_candidate,
                 index=[c["sentence"] for c in kept].index(st.session_state["claim"])
                 if st.session_state.get("claim") in [c["sentence"] for c in kept] else None,
                 captions=[f"score {c['score']} · " + "; ".join(c["reasons"]) for c in kept])
    dropped = [c for c in candidates if not c["kept"]]
    if dropped:
        st.caption("Ignored: " + " · ".join(f"~~{c['sentence']}~~ ({c['reasons'][0].replace('discarded: ', '')})"
                                            for c in dropped))
    st.text_input("Claim to check (editable, or type your own)", key="claim",
                  placeholder="Type or edit the single factual claim to check",
                  on_change=lambda: st.session_state.pop("result", None))

    # ---------------------------------------------------------------- step 2
    st.subheader("2 · Check against the references")
    claim = st.session_state.get("claim", "").strip()
    if st.button("Check against references", type="primary", disabled=len(claim) < 3):
        with st.spinner("Reading the reference passages…"):
            result = pipeline.verify(claim, collection_id)
        db.add_check(result, collection_id)
        st.session_state["result"] = result
        st.session_state["run_id"] = uuid.uuid4().hex[:8]

    result = st.session_state.get("result")
    if result:
        render_result(result)
        st.subheader("3 · Human review")
        review_form(result, key=f"one-{st.session_state['run_id']}")


def _every_claim(pipeline, collection_id):
    st.subheader("2 · Find and check every claim")
    if st.button("Find & check every claim", type="primary", disabled=not st.session_state.get("post", "").strip()):
        with st.spinner("Finding the claims and reading the reference passages…"):
            out = pipeline.check_post(st.session_state["post"], collection_id)
        for r in out["claims"]:
            db.add_check(r, collection_id)
        st.session_state["multi"] = out
        st.session_state["run_id"] = uuid.uuid4().hex[:8]

    out = st.session_state.get("multi")
    if not out:
        return
    if not out["claims"]:
        st.warning("No factual sentences were found in this post. Switch to “One claim” to type a claim yourself.")
        return

    st.markdown(f"**{len(out['claims'])} claim(s) found.**")
    cols = st.columns(4)
    for col, (verdict, n) in zip(cols, out["counts"].items()):
        col.metric(f"{VERDICT_STYLE[verdict]['icon']} {VERDICT_STYLE[verdict]['label']}", n)
    ignored = [c for c in out["candidates"] if c["sentence"] not in {r["claim"] for r in out["claims"]}]
    if ignored:
        st.caption("Not treated as claims: " + " · ".join(f"“{c['sentence']}”" for c in ignored))

    st.subheader("3 · Review each claim")
    tabs = st.tabs([f"{VERDICT_STYLE[r['verdict']]['icon']} Claim {i + 1}" for i, r in enumerate(out["claims"])])
    for i, (tab, r) in enumerate(zip(tabs, out["claims"])):
        with tab:
            st.markdown(f"**Claim {i + 1}:** {r['claim']}")
            render_result(r)
            review_form(r, key=f"multi-{st.session_state['run_id']}-{i}")
