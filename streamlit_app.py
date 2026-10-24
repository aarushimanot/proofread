"""
Proofread: AI-assisted claim review aid (Streamlit app).

Run it with:
    ./start.sh                       (sets everything up, then opens http://localhost:8501)
or  streamlit run streamlit_app.py   (inside backend/.venv)

Pages live in the ui/ folder; the AI pipeline lives in backend/app/.
"""
import sys
from pathlib import Path

import streamlit as st

# Make the ui/ pages and the backend/app pipeline importable however the app is launched.
ROOT = Path(__file__).resolve().parent
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

st.set_page_config(page_title="Proofread", page_icon=":material/fact_check:", layout="wide")

from ui import about, check, dashboard, evaluation, landing, library  # noqa: E402  (after set_page_config)
from ui.common import backfill_test_claims, get_pipeline  # noqa: E402

# Typography: Inter (falls back to the system font when offline). Icon fonts are left alone,
# otherwise Streamlit's arrows and menu icons would turn into words.
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
  p, li, label, input, textarea, button, h1, h2, h3, h4, h5, h6, td, th, div, span:not([data-testid="stIconMaterial"]) {
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  [data-testid="stIconMaterial"], .material-symbols-rounded { font-family: "Material Symbols Rounded" !important; }
  .block-container {padding-top: 3.2rem; max-width: 1150px;}
  h1, h2, h3, h4 {font-weight: 600 !important; letter-spacing: -0.015em;}
  h2 {font-size: 1.75rem !important;}
  h3 {font-size: 1.25rem !important;}
  .pr-brand {font-size: 1.6rem; font-weight: 700; letter-spacing: -0.03em; color: #111827;}
  .pr-brand::before {content: ""; display: inline-block; width: 10px; height: 10px; margin-right: 10px;
                     border-radius: 2px; background: #4f46e5; vertical-align: middle;}
  .pr-tagline {color: #6b7280; font-size: 0.95rem; margin: 2px 0 14px;}
  mark {color: inherit;}
</style>""", unsafe_allow_html=True)

APP_PAGES = [
    st.Page(check.page, title="Check a claim", url_path="check", default=True),
    st.Page(library.page, title="Lie-brary", url_path="library"),
    st.Page(dashboard.page, title="Dashboard", url_path="dashboard"),
    st.Page(evaluation.page, title="Evaluation", url_path="evaluation"),
    st.Page(about.page, title="About & Limitations", url_path="about"),
]

if not st.session_state.get("entered"):
    # Landing page first. The app's pages are registered (hidden) so a link to any of them
    # still lands here cleanly; "Start checking" switches to the real app.
    st.navigation([st.Page(landing.page, title="Proofread", url_path="welcome")] + APP_PAGES, position="hidden")
    landing.page()
    get_pipeline()      # warm up the models while the visitor reads the landing page
else:
    # Header + the persistent human-in-the-loop banner shown on every page.
    st.markdown('<div class="pr-brand">Proofread</div><div class="pr-tagline">Read it for proof before you share it.</div>',
                unsafe_allow_html=True)
    st.warning("**Decision-support tool for human reviewers.** Verdicts are based only on the curated reference set "
               "and may be wrong. Absence of evidence ≠ false.")
    pages = st.navigation(APP_PAGES)   # register the pages first, so links straight to a page work
    get_pipeline()          # load the models once, with a spinner, before any page needs them
    backfill_test_claims()  # topics created before auto test claims existed get theirs now
    pages.run()
    st.session_state.setdefault("reviewer", "Anonymous")
    st.sidebar.text_input("Reviewing as", key="reviewer", max_chars=60,
                          help="Saved with each review you submit.")
    st.sidebar.button("Back to home page", on_click=lambda: st.session_state.update(entered=False))
    st.sidebar.caption("Student media club prototype · open-source models · no paid APIs")
