"""
Evaluation page: how well Proofread does on the 50 labelled test claims, compared with
simpler baselines and with parts of the system switched off. Reads results/eval_summary.json,
which `python evaluate.py` (or the button on this page) produces.
"""
import json

import pandas as pd
import streamlit as st

from app import config
from app.aggregator import VERDICTS
from ui.charts import GROUP_COLORS, hbar, heatmap, line
from ui.common import VERDICT_STYLE, get_pipeline

SUMMARY_PATH = config.RESULTS_DIR / "eval_summary.json"
LABEL = {v: VERDICT_STYLE[v]["label"] for v in VERDICTS}
GROUP_NAME = {"full": "Proofread", "baseline": "Baseline", "ablation": "Ablation"}


def _load() -> dict | None:
    if not SUMMARY_PATH.exists():
        return None
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


def _run():
    import evaluate  # backend/evaluate.py (backend is on sys.path via ui.common)
    with st.spinner("Running the 14 claims through 10 systems… this takes a minute or two."):
        evaluate.run_evaluation(get_pipeline())
    st.rerun()


def page():
    st.header("Evaluation")
    s = _load()
    top = st.columns([4, 1])
    top[0].caption("14 labelled Chandrayaan-3 claims (T01–T14) plus 4 multi-claim posts. All 14 claims were seen "
                   "while the system was being built, so these numbers are optimistic: there is no unseen test set.")
    if top[1].button("Re-run evaluation"):
        _run()
    if s is None:
        st.info("No results yet. Click **Re-run evaluation**, or run `./start.sh eval` in the terminal.")
        return
    st.caption(f"Results generated {s['generated']} on {s['device']}.")

    f = s["full"]
    cols = st.columns(4)
    cols[0].metric("Accuracy", f"{f['correct']}/{f['n']} = {f['accuracy']:.0%}")
    cols[1].metric("Macro-F1", f"{f['macro_f1']:.2f}", help="Average of the F1 scores for Supported, Contradicted and Insufficient evidence.")
    cols[2].metric("Not-covered → called false", f"{f['false_contradiction_rate']:.0%}",
                   help="Claims the references don't cover that were wrongly labelled CONTRADICTED. The assignment's key rule: this must be 0.")
    cols[3].metric("Wrong claims called true", f"{f['false_support_rate']:.0%}",
                   help="Wrong or not-covered claims wrongly labelled SUPPORTED: the most harmful error for a fact-checking aid.")

    # ---------------------------------------------------------------- systems
    st.subheader("Proofread vs simpler methods")
    sys_df = pd.DataFrame([{"system": n, "group": GROUP_NAME[r["group"]], **r} for n, r in s["systems"].items()])
    color_map = {GROUP_NAME[g]: c for g, c in GROUP_COLORS.items()}
    left, right = st.columns(2)
    with left:
        st.altair_chart(hbar(sys_df, "accuracy", "system", title="Accuracy (higher is better)", color="group",
                             color_map=color_map, legend_title=None, domain_max=1), use_container_width=True)
    with right:
        st.altair_chart(hbar(sys_df, "false_contradiction_rate", "system",
                             title="Not-covered claims wrongly called false (lower is better)", color="group",
                             color_map=color_map, legend_title=None, domain_max=1), use_container_width=True)
    with st.expander("What each system is, and the full table"):
        st.dataframe(sys_df[["system", "group", "accuracy", "macro_f1", "false_contradiction_rate",
                             "false_support_rate", "sent_to_human_rate", "description"]]
                     .rename(columns={"macro_f1": "macro-F1", "false_contradiction_rate": "not covered → false",
                                      "false_support_rate": "wrongly supported", "sent_to_human_rate": "sent to human"}),
                     hide_index=True, use_container_width=True,
                     column_config={c: st.column_config.NumberColumn(format="%.2f") for c in
                                    ["accuracy", "macro-F1", "not covered → false", "wrongly supported", "sent to human"]})
    st.caption("**Baselines** are simpler methods: keyword overlap, meaning-similarity only, and NLI without Proofread's "
               "safety checks. **Ablations** are Proofread with one part switched off or changed. The two keyword/similarity "
               "baselines can never answer “contradicted”, which is why their “called false” rate is 0 but they wrongly "
               "support many false claims.")

    # ---------------------------------------------------------------- breakdowns
    st.subheader("Where it works and where it doesn't")
    left, right = st.columns(2)
    tdf = pd.DataFrame([{"topic": t, "accuracy": r["accuracy"], "n": r["n"], "correct": r["correct"]}
                        for t, r in s["by_topic"].items()])
    with left:
        if len(tdf) > 1:   # a one-bar chart says nothing; only show it when there are several topics
            st.altair_chart(hbar(tdf, "accuracy", "topic", title="Accuracy by topic", domain_max=1), use_container_width=True)
        cal = pd.DataFrame([c for c in s["calibration"] if c["n"]])
        cal["label"] = cal.apply(lambda r: f"{r['label']} ({r['n']} claims)", axis=1)
        st.altair_chart(hbar(cal, "accuracy", "label", title="Accuracy by confidence level", domain_max=1),
                        use_container_width=True)
    with right:
        conf = pd.DataFrame([{"expected": LABEL[e], "predicted": LABEL[p], "n": n}
                             for e, row in s["confusion"].items() for p, n in row.items() if e != "CONFLICTING"])
        st.altair_chart(heatmap(conf, "predicted", "expected", "n", title="Confusion matrix (full system)",
                                x_title="Predicted", y_title="Expected", order=list(LABEL.values())),
                        use_container_width=True)
        sens = pd.DataFrame(s["sensitivity"])
        st.altair_chart(line(sens, "threshold", "accuracy", title="Accuracy vs relevance threshold (default 0.45)",
                             x_title="Relevance threshold", y_domain=[0, 1]), use_container_width=True)

    # ---------------------------------------------------------------- multi-claim
    st.subheader("Multi-claim posts")
    m = s["multi"]
    cols = st.columns(3)
    cols[0].metric("Claims found", f"{m['claim_recall']:.0%}", help=f"of the {m['gold_claims']} claims written into the 4 posts")
    cols[1].metric("Found sentences that were real claims", f"{m['claim_precision']:.0%}",
                   help=f"{m['extracted_claims']} sentences were treated as claims")
    cols[2].metric("Correct verdict on claims found", f"{m['verdict_accuracy_on_found']:.0%}")
    for d in m["details"]:
        lines = [f"{'✅' if p['predicted'] == p['expected'] else '❌'} “{p['gold']}” · expected {LABEL[p['expected']]}, "
                 + (f"got {LABEL[p['predicted']]}" if p["extracted"] else "**not found**") for p in d["pairs"]]
        lines += [f"➕ also treated as a claim: “{x}”" for x in d["extra_claims"]]
        with st.expander(f"{d['id']} · {d['topic']}"):
            st.markdown("\n".join(f"- {line_}" for line_ in lines))

    # ---------------------------------------------------------------- per claim
    st.subheader("Every claim")
    rows = pd.DataFrame(s["rows"])
    only_wrong = st.toggle("Only failures")
    view = rows
    topic_f = None
    if topic_f:
        view = view[view["topic"].isin(topic_f)]
    if only_wrong:
        view = view[~view["correct"]]
    view = view.assign(result=view["correct"].map({True: "✅", False: "❌"}),
                       expected=view["expected"].map(LABEL), predicted=view["predicted"].map(LABEL))
    st.dataframe(view[["result", "id", "claim", "expected", "predicted", "confidence_label", "top_passage", "note"]],
                 hide_index=True, use_container_width=True)

    st.subheader("What the results taught us")
    st.markdown("""
- **The event-alignment gate is the most important safety part.** Switching it off makes the system call
  not-covered claims false, which breaks the assignment's key rule.
- **NLI confuses look-alike names.** T06 (“Pragati” vs “Pragyan”) is the one failure; the system routes it
  to a human as CONFLICTING instead of wrongly supporting it.
- **Passages must make sense on their own.** In the cricket multi-claim post, a passage saying “**the final** was
  played in Ahmedabad” never says *which* final, so the NLI model, reading it alone, won't confirm a claim about the
  2023 World Cup final. Self-contained (“decontextualised”) passages are the clear next step.
- **Some parts didn't change any verdict here.** On these 14 claims, removing the relevance threshold or the
  number/date check gives the same accuracy. They still add the mismatch warnings and explanations reviewers see,
  but 14 claims is too few to show a measurable effect.
""")
