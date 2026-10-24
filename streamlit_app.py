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

st.set_page_config(page_title="Proofread", page_icon="🔎", layout="wide")

from ui import about, check, dashboard, evaluation, library  # noqa: E402  (after set_page_config)
from ui.common import get_pipeline  # noqa: E402

st.markdown("""<style>
  .block-container {padding-top: 2.2rem; max-width: 1150px;}
  mark {color: inherit;}
</style>""", unsafe_allow_html=True)

# Header + the persistent human-in-the-loop banner shown on every page.
st.markdown("## 🔎 Proofread")
st.caption("Read it for proof before you share it.")
st.warning("**Decision-support tool for human reviewers.** Verdicts are based only on the curated reference set and "
           "may be wrong. Absence of evidence ≠ false.")

# Register the pages first (so links straight to a page work), then load the models.
pages = st.navigation([
    st.Page(check.page, title="Check a claim", icon="✅", url_path="check", default=True),
    st.Page(library.page, title="Lie-brary", icon="📚", url_path="library"),
    st.Page(dashboard.page, title="Dashboard", icon="📊", url_path="dashboard"),
    st.Page(evaluation.page, title="Evaluation", icon="🧪", url_path="evaluation"),
    st.Page(about.page, title="About & Limitations", icon="ℹ️", url_path="about"),
])
get_pipeline()   # load the models once, with a spinner, before any page needs them
pages.run()

st.sidebar.caption("Student media club prototype · open-source models · no paid APIs")
