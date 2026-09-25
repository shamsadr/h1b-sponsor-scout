"""Employer lookup: one group's cases by year and family, wage levels and member names."""

import streamlit as st

from app_data import search_groups
from ui import cases_by_year_chart, count_col, data, fmt_count, level_chart, text_col

DATA = data()


def render() -> None:
    """Draw the page (a function, so an early return keeps the app footer)."""
    st.title("Employer lookup")
    query = st.text_input("Search an employer or brand", placeholder="e.g. Deloitte, Merrill")
    matches = search_groups(DATA["members"], query)
    if not query.strip():
        st.info("Type part of a name. Searches group labels and every member name.")
        return
    if not matches:
        st.warning(f"No employer group matches '{query}' in the target role families.")
        return
    group = st.selectbox("Employer group", matches)
    breakdown = DATA["employer_breakdown"]
    b = breakdown[breakdown["parent_group"] == group]
    members = DATA["members"][DATA["members"]["parent_group"] == group]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Certified cases", fmt_count(b["cases"].sum()))
    m2.metric("All filings", fmt_count(b["filings"].sum()))
    m3.metric("Withdrawn", fmt_count(b["withdrawn"].sum()))
    m4.metric("Names in group", fmt_count(len(members)))

    left, right = st.columns(2)
    with left:
        st.subheader("Certified cases by family and year")
        by = b.groupby(["soc_family", "fiscal_year"], as_index=False)["cases"].sum()
        by = by[by["cases"] > 0]
        if by.empty:
            st.write("No certified cases in the target families.")
        else:
            st.altair_chart(cases_by_year_chart(by, "soc_family"), width="stretch")
            with st.expander("Table"):
                wide = by.pivot(index="soc_family", columns="fiscal_year", values="cases")
                wide = wide.fillna(0).astype(int)
                wide.columns = [f"FY{y}" for y in wide.columns]
                st.dataframe(wide, column_config={c: count_col(c) for c in wide.columns})
    with right:
        st.subheader("Wage-level mix (certified)")
        lv = DATA["employer_levels"]
        lv = lv[lv["parent_group"] == group]
        if lv.empty:
            st.write("No certified cases.")
        else:
            st.altair_chart(level_chart(lv), width="stretch")
            st.caption(
                "Level depends on the SOC code the employer chose; 'Not leveled' means a DOL "
                "determination or private survey was used."
            )
    st.subheader("Member names")
    st.dataframe(
        members.sort_values("rows", ascending=False).drop(columns="parent_group"),
        hide_index=True,
        width="stretch",
        column_config={
            "employer_norm": text_col("Normalized name"),
            "primary_fein": text_col("Primary FEIN"),
            "primary_state": text_col("Employer state"),
            "rows": count_col("LCA rows (all roles)"),
            "link": text_col("Linked by"),
        },
    )


render()
