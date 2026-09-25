"""Trends: certified LCAs per role family and fiscal year."""

import streamlit as st

from app_data import readme_bullet
from ui import cases_by_year_chart, count_col, data

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
        wide = d.pivot(index="family", columns="fiscal_year", values="cases")
        wide.columns = [f"FY{y}" for y in wide.columns]
        st.dataframe(wide, column_config={c: count_col(c) for c in wide.columns})
st.warning(readme_bullet("Employers substitute SOC codes"))
st.info(readme_bullet("Withdrawals are right-censored"))
