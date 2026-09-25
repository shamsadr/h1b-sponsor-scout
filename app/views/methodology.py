"""Methodology & limitations, rendered from the README."""

import streamlit as st
from app_data import readme_sections, years_label
from ui import data

META = data()["meta"]

st.title("Methodology & limitations")
st.caption(
    f"Data {years_label(META['fiscal_years'])}, built {META['built_at']} from commit "
    f"{META['git_commit']}; {META['target_rows']:,} target-family filings."
)
sections = readme_sections(
    ["Scorecard columns", "Employer grouping", "Methodology decisions", "Limitations"]
)
for heading, body in sections.items():
    st.header(heading)
    st.markdown(body)
