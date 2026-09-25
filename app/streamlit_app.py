"""H-1B Sponsor Scout: Streamlit app over the precomputed tables in data/app/.

Run from the repo root: streamlit run app/streamlit_app.py
Each page is a file in app/views/; shared data and charts live in app/ui.py.
"""

import sys
from pathlib import Path

import streamlit as st

# Pages import app_data/ui from this folder; `streamlit run` adds it to sys.path, but not
# every runner does (e.g. older AppTest), so add it explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app_data import footer_text  # noqa: E402
from ui import data  # noqa: E402

st.set_page_config(page_title="H-1B Sponsor Scout", layout="wide")

pages = st.navigation(
    [
        st.Page("views/find_sponsors.py", title="Find sponsors", default=True),
        st.Page("views/employer_lookup.py", title="Employer lookup"),
        st.Page("views/trends.py", title="Trends"),
        st.Page("views/methodology.py", title="Methodology & limitations"),
    ]
)
pages.run()
st.divider()
st.caption(footer_text(data()["meta"]))
