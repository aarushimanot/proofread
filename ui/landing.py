"""
Landing page: the first thing a visitor sees. Shows the name, tagline and what Proofread
does; the "Start checking" button opens the app itself.
"""
import streamlit as st

from ui.common import logo_img

FEATURES = [
    ("Extract the claim", "Paste a social media post. Proofread strips the noise and finds the factual "
                          "claim, or every claim, worth checking."),
    ("Check it against trusted sources", "Each claim is compared with a curated library of reference passages "
                                         "using language models, with the exact evidence and a plain-English reason."),
    ("A human makes the call", "Proofread suggests a verdict; a reviewer reads the evidence and decides. "
                               "Absence of evidence is never treated as false."),
]


def enter_app():
    st.session_state["reviewer"] = st.session_state.get("reviewer_input", "").strip() or "Anonymous"
    st.session_state["entered"] = True


def page():
    st.markdown("""
    <style>
      [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display: none;}
      .block-container {max-width: 960px; padding-top: 5.5rem;}
      /* "inherit" + opacity, so the page reads well in both the light and the dark theme */
      .pr-hero-title {display: flex; align-items: center; gap: 22px; font-size: 4.2rem; font-weight: 700;
                      letter-spacing: -0.045em; line-height: 1; color: inherit; margin: 0;}
      .pr-hero-tagline {font-size: 1.45rem; opacity: .8; margin: 20px 0 10px; letter-spacing: -0.01em;}
      .pr-hero-sub {font-size: 1.02rem; opacity: .65; max-width: 640px; line-height: 1.6; margin-bottom: 28px;}
      .pr-feature {border: 1px solid rgba(128,128,128,.25); border-radius: 12px; padding: 20px 20px 18px;
                   min-height: 235px; background: rgba(128,128,128,.06);}
      .pr-feature-num {font-size: .78rem; font-weight: 600; color: #7c6cf2; letter-spacing: .08em;}
      .pr-feature-title {font-size: 1.05rem; font-weight: 600; color: inherit; margin: 6px 0 6px;}
      .pr-feature-body {font-size: .92rem; opacity: .7; line-height: 1.55;}
      .pr-foot {opacity: .55; font-size: .85rem; margin-top: 44px; border-top: 1px solid rgba(128,128,128,.25);
                padding-top: 16px;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f'<div class="pr-hero-title">{logo_img(76)}<span>Proofread</span></div>'
                '<p class="pr-hero-tagline">Read it for proof before you share it.</p>'
                '<p class="pr-hero-sub">An AI-assisted claim review aid for student journalists. Check a claim from '
                'social media against trusted sources, see exactly why, and decide for yourself.</p>',
                unsafe_allow_html=True)

    name_col, _ = st.columns([2, 3])
    name_col.text_input("Your name (optional)", key="reviewer_input", max_chars=60,
                        placeholder="e.g. Aarav, News desk",
                        help="Saved with each review you make, so the club knows who approved each verdict. "
                             "Leave blank to review as Anonymous.")
    st.button("Start checking", type="primary", on_click=enter_app)

    st.write("")
    st.write("")
    cols = st.columns(3, gap="medium")
    for i, (col, (title, body)) in enumerate(zip(cols, FEATURES), start=1):
        col.markdown(f'<div class="pr-feature"><div class="pr-feature-num">STEP {i}</div>'
                     f'<div class="pr-feature-title">{title}</div><div class="pr-feature-body">{body}</div></div>',
                     unsafe_allow_html=True)

    st.markdown('<div class="pr-foot">A decision-support prototype for a student media club. Verdicts are based only '
                'on a curated reference set and may be wrong. Open-source models, no paid APIs.</div>',
                unsafe_allow_html=True)
