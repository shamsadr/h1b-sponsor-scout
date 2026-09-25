"""Trends: certified cases per role family and fiscal year."""

import streamlit as st
from app_data import readme_bullet
from ui import cases_by_year_chart, data

DATA = data()

st.title("Trends")
t = DATA["family_trends"]
families = t["family"].unique().tolist()
picked = st.multiselect("Role families", families, default=families)
d = t[t["family"].isin(picked)]
if d.empty:
    st.info("Pick at least one family.")
else:
    st.altair_chart(cases_by_year_chart(d, "family"), width="stretch")
    with st.expander("Table"):
        st.dataframe(d.pivot(index="family", columns="fiscal_year", values="cases"))
st.warning(readme_bullet("Employers substitute SOC codes"))
st.info(readme_bullet("Withdrawals are right-censored"))
