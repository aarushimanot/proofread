"""
Analytics dashboard: what has been checked, how reviewers responded, and which topics
and sources are used. Everything is read live from the SQLite database.
"""
import altair as alt
import pandas as pd
import streamlit as st

from app import db
from app.aggregator import VERDICTS
from ui.charts import SERIES_1, hbar, heatmap
from ui.common import VERDICT_STYLE

LABEL = {v: VERDICT_STYLE[v]["label"] for v in VERDICTS}


def page():
    st.header("Dashboard")
    st.caption("Live numbers from Proofread's database: every claim checked and every human review.")

    checks = pd.DataFrame(db.get_checks(limit=100_000))
    reviews = pd.DataFrame(db.get_reviews())
    stats = db.stats()

    # ---------------------------------------------------------------- stat tiles
    agree = f"{stats['reviews_agreed'] / stats['reviews']:.0%}" if stats["reviews"] else "–"
    cols = st.columns(4)
    cols[0].metric("Claims checked", stats["checks"])
    cols[1].metric("Human reviews", stats["reviews"])
    cols[2].metric("Reviewer agreed with model", agree)
    cols[3].metric("Topics / passages", f"{stats['collections']} / {stats['passages']}")

    if checks.empty:
        st.info("No claims have been checked yet. Check a claim on the **Check a claim** page and the charts will appear here.")
        return

    checks["verdict_label"] = checks["verdict"].map(LABEL)
    checks["topic"] = checks["collection_name"].fillna("All topics")
    checks["day"] = pd.to_datetime(checks["timestamp"]).dt.tz_convert(None).dt.date

    # ---------------------------------------------------------------- verdicts + activity
    left, right = st.columns(2)
    counts = checks["verdict"].value_counts().reindex(VERDICTS, fill_value=0)
    vdf = pd.DataFrame({"verdict": [LABEL[v] for v in VERDICTS], "claims": counts.values,
                        "share": counts.values / counts.sum()})
    with left:
        st.altair_chart(hbar(vdf, "claims", "verdict", title="Verdicts given", fmt="d", color="verdict",
                             color_map={LABEL[v]: VERDICT_STYLE[v]["color"] for v in VERDICTS}, legend_title=None,
                             tooltip=[alt.Tooltip("verdict:N"), alt.Tooltip("claims:Q"),
                                      alt.Tooltip("share:Q", format=".0%")]),
                        use_container_width=True)
    per_day = checks.groupby("day").size().reset_index(name="claims")
    per_day["day"] = per_day["day"].astype(str)
    with right:
        chart = alt.Chart(per_day).mark_bar(cornerRadiusEnd=4, size=18, color=SERIES_1).encode(
            x=alt.X("day:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("claims:Q", title=None, axis=alt.Axis(tickMinStep=1)),
            tooltip=[alt.Tooltip("day:N", title="Day"), alt.Tooltip("claims:Q", title="Claims checked")],
        ).properties(title="Claims checked per day", height=220)
        st.altair_chart(chart, use_container_width=True)

    # ---------------------------------------------------------------- reviewer agreement
    st.subheader("How reviewers responded")
    if reviews.empty:
        st.info("No human reviews yet. Submit one in step 3 of “Check a claim”.")
    else:
        reviews["model"] = reviews["model_verdict"].map(LABEL)
        reviews["reviewer"] = reviews["reviewer_verdict"].map(LABEL)
        grid = (reviews.groupby(["model", "reviewer"]).size().reset_index(name="n"))
        full = pd.MultiIndex.from_product([list(LABEL.values())] * 2, names=["model", "reviewer"])
        grid = grid.set_index(["model", "reviewer"]).reindex(full, fill_value=0).reset_index()
        left, right = st.columns([3, 2])
        with left:
            st.altair_chart(heatmap(grid, "reviewer", "model", "n", title="Model verdict vs reviewer decision",
                                    x_title="Reviewer decided", y_title="Model said", order=list(LABEL.values())),
                            use_container_width=True)
        override = (reviews.assign(over=~reviews["agreed"]).groupby("model")["over"].agg(["mean", "size"])
                    .reset_index().rename(columns={"mean": "override_rate", "size": "reviews"}))
        with right:
            st.altair_chart(hbar(override, "override_rate", "model", title="How often reviewers overrode each verdict",
                                 domain_max=1, tooltip=[alt.Tooltip("model:N", title="Model said"),
                                                        alt.Tooltip("override_rate:Q", format=".0%", title="Overridden"),
                                                        alt.Tooltip("reviews:Q")]),
                            use_container_width=True)
            st.caption("Cells on the diagonal are agreements; anything off it is a human correcting the model.")

        # Who reviewed what (the reviewer name typed on the landing page).
        left, right = st.columns([2, 3])
        per = (reviews.groupby("reviewer").agg(reviews=("id", "size"), overridden=("agreed", lambda a: int((~a).sum())))
               .reset_index().sort_values("reviews", ascending=False))
        with left:
            st.altair_chart(hbar(per, "reviews", "reviewer", title="Reviews per reviewer", fmt="d",
                                 tooltip=[alt.Tooltip("reviewer:N"), alt.Tooltip("reviews:Q"),
                                          alt.Tooltip("overridden:Q", title="overrode the model")]),
                            use_container_width=True)
        with right:
            recent = reviews.sort_values("id", ascending=False).head(15)
            st.markdown("**Recent reviews**")
            st.dataframe(recent[["timestamp", "reviewer", "claim", "model", "reviewer_verdict", "note"]]
                         .assign(reviewer_verdict=recent["reviewer_verdict"].map(LABEL))
                         .rename(columns={"timestamp": "Time", "reviewer": "Reviewer", "claim": "Claim",
                                          "model": "Model said", "reviewer_verdict": "Reviewer decided", "note": "Note"}),
                         hide_index=True, use_container_width=True)

    # ---------------------------------------------------------------- topics and sources
    st.subheader("Topics and sources")
    left, right = st.columns(2)
    tdf = checks["topic"].value_counts().reset_index()
    tdf.columns = ["topic", "claims"]
    with left:
        st.altair_chart(hbar(tdf, "claims", "topic", title="Claims checked per topic", fmt="d"), use_container_width=True)
    passages = {p["id"]: p for p in db.get_passages()}
    top = checks["top_passage_id"].dropna().map(lambda i: passages.get(i, {}).get("source", "deleted passage"))
    sdf = top.value_counts().reset_index()
    sdf.columns = ["source", "claims"]
    with right:
        if sdf.empty:
            st.caption("No evidence cited yet.")
        else:
            st.altair_chart(hbar(sdf.head(8), "claims", "source", title="Source of the top evidence passage", fmt="d"),
                            use_container_width=True)

    ptop = checks["top_passage_id"].dropna().value_counts().head(8).reset_index()
    ptop.columns = ["id", "claims"]
    ptop["passage"] = ptop["id"].map(lambda i: f"{i} · {passages[i]['title']}" if i in passages else i)
    if not ptop.empty:
        st.altair_chart(hbar(ptop, "claims", "passage", title="Most-cited passages", fmt="d"), use_container_width=True)

    # ---------------------------------------------------------------- recent activity
    st.subheader("Recent checks")
    recent = checks.head(25)[["timestamp", "claim", "topic", "verdict_label", "confidence_label", "top_passage_id"]]
    st.dataframe(recent.rename(columns={"timestamp": "Time", "claim": "Claim", "topic": "Topic",
                                        "verdict_label": "Verdict", "confidence_label": "Confidence",
                                        "top_passage_id": "Top passage"}),
                 hide_index=True, use_container_width=True)
