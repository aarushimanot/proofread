"""About & Limitations page: how Proofread works, what it cannot do, and how to use it responsibly."""
import streamlit as st

LIMITATIONS = [
    ("Only as good as its sources", "Proofread knows only the passages saved in the Lie-brary. Few or poor sources give few or poor verdicts, and anything not covered is INSUFFICIENT EVIDENCE."),
    ("Passages must make sense on their own", "A passage that says “the final” without saying which final can't confirm a claim about the 2023 World Cup final. This caused most held-out failures."),
    ("Imported pages are treated as true", "Link imports keep a page's paragraphs automatically, including opinions, quotes or outdated facts. Untick those before saving."),
    ("NLI weaknesses", "The NLI model is weak on numbers, negation, look-alike names (it confused “Pragati” with “Pragyan”) and reasoning that needs two passages."),
    ("Hand-written heuristics", "The number/date check and the event-alignment gate are simple rules. They can misfire, e.g. comparing dates from two different missions."),
    ("Threshold sensitivity", "Relevance (0.45), stance (0.6) and nudge (0.35) were set by hand; see the Evaluation page for how accuracy changes."),
    ("Uncalibrated confidence", "“High” means the model is very sure, not that it's right."),
    ("English only", "Posts in other languages are not handled."),
    ("Extraction heuristics", "The claim finder uses simple rules. It may pick the wrong sentence, miss a claim phrased as a question, or treat a non-claim as a claim. Always check the claim."),
    ("No live updates", "Claims are never checked against the live web; new facts are invisible until a curator adds them."),
    ("Small evaluation", "50 hand-written claims on 3 topics (30 held out). Accuracy on real posts and on user-imported topics has not been measured."),
]


def page():
    st.header("About & Limitations")
    st.subheader("How Proofread works")
    st.markdown("""
1. **Curate.** Reviewers create a topic and add trusted sources to it in the Lie-brary (paste a link, paste text, or type a passage).
2. **Extract.** spaCy splits the post into sentences, drops questions, opinions and very short sentences, and scores the rest by names, dates, numbers and factual verbs. In *Every claim* mode, each factual sentence becomes its own claim.
3. **Retrieve.** The claim and every passage are turned into meaning-vectors with MiniLM. The 3 most similar passages in the chosen topic are retrieved; only those with similarity ≥ 0.45 count as relevant.
4. **Judge.** An NLI model (DeBERTa-v3) reads each relevant passage, and each of its sentences, next to the claim: does it entail it, contradict it, or neither?
5. **Safety checks.** A number/date check flags a different value for the same thing; an event-alignment check ignores “contradictions” from passages about a different event.
6. **Decide.** Support only → SUPPORTED · contradiction only → CONTRADICTED · both → CONFLICTING (a human decides) · neither, or nothing relevant → INSUFFICIENT EVIDENCE.
7. **Explain and review.** Each passage shows its link, highlighted words, scores, the key sentence and a plain-English reason. A human agrees or overrides, and it's saved.
""")
    st.info("**No match never means false.** A claim is only CONTRADICTED when a relevant reference passage says "
            "something incompatible with it. The models never use their own knowledge to give a verdict.")

    st.subheader("Limitations")
    cols = st.columns(2)
    for i, (title, body) in enumerate(LIMITATIONS):
        with cols[i % 2].container(border=True):
            st.markdown(f"**{title}**")
            st.caption(body)

    st.subheader("Responsible use")
    st.markdown("""
- Proofread is a **decision aid for human reviewers**, not an automatic fact checker. A person makes every final call.
- Always open the linked sources. Don't publish a verdict based on the badge alone.
- Record your decision in the review step, especially when you override the model, so the club can see where it fails (Dashboard).
- Don't use it to label people or accounts as liars. It assesses one claim against one small reference set.
""")
    st.caption("Models: spaCy en_core_web_sm · sentence-transformers/all-MiniLM-L6-v2 · cross-encoder/nli-deberta-v3-small. "
               "All open-source, running locally; no paid APIs.")
