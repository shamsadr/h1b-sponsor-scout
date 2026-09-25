"""Trends: certified LCAs per role family and fiscal year."""

import streamlit as st

from app_data import (
    ANALYTICS_LABEL,
    FAMILY_ORDER,
    pct_change_table,
    plain,
    readme_bullet,
    years_label,
)
from ui import cases_by_year_chart, count_col, data, pct_change_chart

DATA = data()
YEARS = DATA["meta"]["fiscal_years"]
FIRST, LAST = YEARS[0], YEARS[-1]
CAVEATS = [
    (
        "Employers sometimes file the same kind of job under a different occupation code from "
        "one year to the next, so part of a family's change is relabeling, not new hiring. "
        "Analytics (combined) nets out moves among its four families, so it is shown as the "
        "reference.",
        "Employers substitute SOC codes",
    ),
    (
        f"Withdrawals are recorded in the year they happen, so FY{LAST} has had less time for "
        f"them than FY{FIRST}. Read the FY{LAST} counts as an upper bound.",
        "Withdrawals are right-censored",
    ),
]

st.title("Trends")
t = DATA["family_trends"]
families = [f for f in FAMILY_ORDER if f in set(t["family"]) and f != ANALYTICS_LABEL]
picked = st.multiselect("Role families", families, default=families)
st.caption(f"Certified LCAs, all states, {years_label(YEARS)}.")
if not picked:
    st.info("Pick at least one role family.")
else:
    st.subheader(f"Change FY{FIRST} → FY{LAST}")
    changes = pct_change_table(t[t["family"].isin(picked + [ANALYTICS_LABEL])])
    st.altair_chart(pct_change_chart(changes, ANALYTICS_LABEL, FIRST, LAST), width="stretch")
    no_base = changes.loc[changes["pct_change"].isna(), "family"].tolist()
    if no_base:
        st.caption(f"No % change for {', '.join(no_base)}: no certified LCAs in FY{FIRST}.")
    st.subheader("Certified LCAs by year")
    counts = t[t["family"].isin(picked)]
    st.altair_chart(cases_by_year_chart(counts, "family"), width="stretch")
    with st.expander("Table"):
        wide = counts.pivot(index="family", columns="fiscal_year", values="cases")
        wide.columns = [f"FY{y}" for y in wide.columns]
        wide.index.name = "Role family"
        st.dataframe(wide, column_config={c: count_col(c) for c in wide.columns})

st.subheader("Read these first")
for summary, bullet in CAVEATS:
    with st.container(border=True):
        st.write(summary)
        with st.expander("Details"):
            st.write(plain(readme_bullet(bullet)))
