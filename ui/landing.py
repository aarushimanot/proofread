"""
Landing page: the first thing a visitor sees. Shows the name, tagline and what Proofread
does; the "Start checking" button opens the app itself.
"""
import streamlit as st

FEATURES = [
    ("Extract the claim", "Paste a social media post. Proofread strips the noise and finds the factual "
                          "claim, or every claim, worth checking."),
    ("Check it against trusted sources", "Each claim is compared with a curated library of reference passages "
                                         "using language models, with the exact evidence and a plain-English reason."),
    ("A human makes the call", "Proofread suggests a verdict; a reviewer reads the evidence and decides. "
                               "Absence of evidence is never treated as false."),
]


def enter_app():
    st.session_state["entered"] = True


def page():
    st.markdown("""
    <style>
      [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display: none;}
      .block-container {max-width: 960px; padding-top: 5.5rem;}
      .pr-hero-title {font-size: 4.2rem; font-weight: 700; letter-spacing: -0.045em; line-height: 1;
                      color: #111827; margin: 0;}
      .pr-hero-mark {display: inline-block; width: 18px; height: 18px; border-radius: 4px; background: #4f46e5;
                     margin-right: 18px; vertical-align: 0.55rem;}
      .pr-hero-tagline {font-size: 1.45rem; color: #4b5563; margin: 18px 0 10px; letter-spacing: -0.01em;}
      .pr-hero-sub {font-size: 1.02rem; color: #6b7280; max-width: 640px; line-height: 1.6; margin-bottom: 28px;}
      .pr-feature {border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px 20px 18px; min-height: 235px;
                   background: #fafafa;}
      .pr-feature-num {font-size: .78rem; font-weight: 600; color: #4f46e5; letter-spacing: .08em;}
      .pr-feature-title {font-size: 1.05rem; font-weight: 600; color: #111827; margin: 6px 0 6px;}
      .pr-feature-body {font-size: .92rem; color: #6b7280; line-height: 1.55;}
      .pr-foot {color: #9ca3af; font-size: .85rem; margin-top: 44px; border-top: 1px solid #f0f0f0; padding-top: 16px;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="pr-hero-title"><span class="pr-hero-mark"></span>Proofread</p>'
                '<p class="pr-hero-tagline">Read it for proof before you share it.</p>'
                '<p class="pr-hero-sub">An AI-assisted claim review aid for student journalists. Check a claim from '
                'social media against trusted sources, see exactly why, and decide for yourself.</p>',
                unsafe_allow_html=True)

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
