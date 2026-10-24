"""
"Lie-brary" page: create topics and add the trusted reference passages verdicts may use.

Sources can be added by pasting a link, pasting text, or typing one passage. Link and
text imports are only a PREVIEW: the curator ticks the passages they trust before saving.
"""
from datetime import date

import pandas as pd
import streamlit as st

from app import db, importer
from ui.common import get_pipeline

MIN_TEXT = 20  # characters, same rule as the API


def _new_topic():
    with st.expander("➕ New topic"):
        with st.form("new-topic", clear_on_submit=True, border=False):
            name = st.text_input("Topic name", placeholder="e.g. Climate change")
            description = st.text_input("Short description (optional)")
            if st.form_submit_button("Create topic", type="primary"):
                try:
                    c = db.create_collection(name, description) if len(name.strip()) >= 2 else None
                    if c is None:
                        st.error("Please enter a topic name.")
                    else:
                        # The topic menu is already drawn, so ask for the switch on the next run.
                        st.session_state["lib_topic_next"] = c["id"]
                        st.rerun()
                except ValueError as e:
                    st.error(str(e))


def _preview_editor(preview: dict, collection: dict):
    """Show an import preview as a table with a 'keep' tick box per passage, then save."""
    st.markdown(f"**{preview['title']}** · {preview['source']} · {preview['date']} · "
                f"{len(preview['passages'])} passages found"
                + (" (long page: only the first part was used)" if preview["truncated"] else ""))
    st.caption("Untick anything that isn't a clear factual statement (opinions, quotes, menus). You can also edit text.")
    df = pd.DataFrame([{"keep": True, "title": p["title"], "text": p["text"]} for p in preview["passages"]])
    edited = st.data_editor(df, hide_index=True, use_container_width=True, key=f"editor-{preview['url']}{preview['title']}",
                            column_config={"keep": st.column_config.CheckboxColumn("Keep", width="small"),
                                           "title": st.column_config.TextColumn("Title", width="medium"),
                                           "text": st.column_config.TextColumn("Passage", width="large")})
    chosen = edited[edited["keep"]]
    c1, c2 = st.columns([1, 1])
    if c1.button(f"Save {len(chosen)} selected passage(s)", type="primary", disabled=chosen.empty):
        items = [{"title": r["title"], "source": preview["source"], "url": preview["url"], "date": preview["date"],
                  "text": r["text"]} for _, r in chosen.iterrows() if len(str(r["text"]).strip()) >= MIN_TEXT]
        db.add_passages(collection["id"], items)
        st.session_state.pop("preview", None)
        st.session_state["lib_message"] = f"Saved {len(items)} passage(s) to “{collection['name']}”."
        st.rerun()
    if c2.button("Discard"):
        st.session_state.pop("preview", None)
        st.rerun()


def _add_sources(collection: dict):
    st.markdown(f"#### Add trusted sources to “{collection['name']}”")
    st.warning("Proofread treats everything in a topic as true. Only add sources you trust (official sites, "
               "reputable news, encyclopedias), and read what you save.")
    nlp = get_pipeline().nlp
    tab_link, tab_text, tab_manual = st.tabs(["Paste a link", "Paste text", "Type one passage"])

    with tab_link:
        st.caption("Paste a web address (e.g. a Wikipedia article or a news story). Proofread reads the page and "
                   "splits it into short passages for you to review.")
        url = st.text_input("Web address", placeholder="https://en.wikipedia.org/wiki/…", key="import_url")
        if st.button("Read page", disabled=len(url.strip()) < 8):
            with st.spinner("Reading the page…"):
                try:
                    st.session_state["preview"] = importer.preview_from_url(nlp, url)
                except importer.ImportError_ as e:
                    st.error(str(e))

    with tab_text:
        st.caption("Copy text from a trusted source and paste it below. It will be split into short passages.")
        a, b = st.columns(2)
        title = a.text_input("Title *", placeholder="e.g. WHO fact sheet on malaria", key="text_title")
        source = b.text_input("Source name *", placeholder="e.g. WHO", key="text_source")
        link = a.text_input("Link to the source (recommended)", key="text_url")
        when = b.text_input("Date (YYYY-MM-DD)", value=date.today().isoformat(), key="text_date")
        text = st.text_area("Text *", height=150, key="text_body")
        if st.button("Split into passages", disabled=not (title.strip() and source.strip() and len(text.strip()) >= MIN_TEXT)):
            try:
                st.session_state["preview"] = importer.preview_from_text(nlp, text, title, source, link, when)
            except importer.ImportError_ as e:
                st.error(str(e))

    with tab_manual:
        st.caption("Write one passage of 2–4 sentences that states facts plainly.")
        with st.form("manual", clear_on_submit=True, border=False):
            a, b = st.columns(2)
            m_title = a.text_input("Title *")
            m_source = b.text_input("Source name *")
            m_url = a.text_input("Link to the source (recommended)")
            m_date = b.text_input("Date (YYYY-MM-DD)", value=date.today().isoformat())
            m_text = st.text_area("Passage text *", height=110)
            if st.form_submit_button("Save passage", type="primary"):
                if not (m_title.strip() and m_source.strip() and len(m_text.strip()) >= MIN_TEXT):
                    st.error(f"Title, source and at least {MIN_TEXT} characters of text are required.")
                else:
                    db.add_passages(collection["id"], [{"title": m_title, "source": m_source, "url": m_url,
                                                        "date": m_date, "text": m_text}])
                    st.session_state["lib_message"] = f"Saved “{m_title}” to “{collection['name']}”."
                    st.rerun()

    if st.session_state.get("preview"):
        with st.container(border=True):
            _preview_editor(st.session_state["preview"], collection)


def _passage(p: dict):
    with st.container(border=True):
        builtin = p["origin"] == "seed"
        a, b = st.columns([5, 1])
        a.markdown(f"**{p['title']}**")
        b.markdown(f"<div style='text-align:right'><code>{p['id'] if builtin else 'added'}</code></div>",
                   unsafe_allow_html=True)
        meta = f"{p['source']} · {p['date'] or 'no date'}"
        st.caption(f"{meta} · [{p['url']}]({p['url']})" if p["url"] else meta)
        st.write(p["text"])
        if not builtin:
            with st.expander("Edit or delete"):
                with st.form(f"edit-{p['id']}", border=False):
                    title = st.text_input("Title", p["title"])
                    a, b, c = st.columns(3)
                    source = a.text_input("Source", p["source"])
                    url = b.text_input("Link", p["url"])
                    when = c.text_input("Date", p["date"])
                    text = st.text_area("Text", p["text"])
                    if st.form_submit_button("Save changes"):
                        db.update_passage(p["id"], {"title": title, "source": source, "url": url, "date": when, "text": text})
                        st.rerun()
                if st.button("Delete this passage", key=f"del-{p['id']}"):
                    db.delete_passage(p["id"])
                    st.rerun()


def page():
    st.header("Lie-brary")
    st.caption("Proofread can only judge a claim against the passages saved here. Create a topic for any subject, "
               "add trusted sources to it, then pick that topic on the “Check a claim” page.")
    if msg := st.session_state.pop("lib_message", None):
        st.success(msg)

    collections = db.get_collections()
    ids = [c["id"] for c in collections]
    by_id = {c["id"]: c for c in collections}
    if "lib_topic_next" in st.session_state:          # set by "Create topic" / "Delete topic"
        st.session_state["lib_topic"] = st.session_state.pop("lib_topic_next")
    if st.session_state.get("lib_topic") not in ids:
        st.session_state["lib_topic"] = ids[0]
    left, right = st.columns([3, 2])
    left.selectbox("Topic", ids, key="lib_topic",
                   format_func=lambda i: f"{by_id[i]['name']} ({by_id[i]['passage_count']} passages)"
                   + (" · built-in" if by_id[i]["origin"] == "seed" else ""),
                   on_change=lambda: st.session_state.pop("preview", None))
    with right:
        _new_topic()

    collection = by_id[st.session_state["lib_topic"]]
    st.subheader(collection["name"])
    if collection["description"]:
        st.write(collection["description"])
    if collection["origin"] == "seed":
        st.info("Built-in topic: read-only in the app (edit its file in backend/data/topics/ to change it). "
                + ("IDs starting DIS- are deliberate distractors on other missions, to test relevance filtering."
                   if collection["id"] == "chandrayaan-3" else ""))
    else:
        _add_sources(collection)
        with st.expander("Delete this topic"):
            st.write(f"This permanently deletes “{collection['name']}” and its {collection['passage_count']} passages.")
            if st.button("Delete topic", type="primary"):
                db.delete_collection(collection["id"])
                st.session_state["lib_topic_next"] = ids[0]
                st.rerun()

    passages = db.get_passages(collection["id"])
    st.markdown(f"#### Passages ({len(passages)})")
    if not passages:
        st.info("No passages yet. Add some trusted sources above.")
        return
    query = st.text_input("Search passages", placeholder="Type to filter…", label_visibility="collapsed")
    shown = [p for p in passages if query.lower() in f"{p['title']} {p['text']} {p['source']} {p['id']}".lower()]
    cols = st.columns(2)
    for i, p in enumerate(shown):
        with cols[i % 2]:
            _passage(p)
    if not shown:
        st.caption(f"No passages match “{query}”.")
