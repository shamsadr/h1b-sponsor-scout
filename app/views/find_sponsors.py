"""Find sponsors: ranked employer groups for a role family and worksite state."""

import re

import streamlit as st

from app_data import ANALYTICS_LABEL, STATE_ALL, as_percent, filter_sponsors, years_label
from ui import NONE_CAPTION, count_col, data, money_col, pct_col, text_col

DATA = data()
META = DATA["meta"]
N_YEARS = len(META["fiscal_years"])

st.title("Find sponsors")
sponsors = DATA["sponsors"]
families = sorted(sponsors["family"].unique())
default = families.index(ANALYTICS_LABEL) if ANALYTICS_LABEL in families else 0
c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
family = c1.selectbox("Role family", families, index=default)
states = sorted(sponsors.loc[sponsors["family"] == family, "state"].unique())
states = [STATE_ALL] + [s for s in states if s != STATE_ALL]
state = c2.selectbox(
    "Worksite state", states, format_func=lambda s: "All states" if s == STATE_ALL else s
)
min_cases = c3.number_input("Minimum certified cases", min_value=1, value=5, step=1)
c4.write("")  # align the checkbox with the inputs
consistent = c4.checkbox(
    "Consistent sponsors only",
    help=f"Certified cases in every loaded year ({years_label(META['fiscal_years'])}).",
)
table = filter_sponsors(sponsors, family, state, int(min_cases), consistent, N_YEARS)
shown = as_percent(table).drop(columns="parent_group")
st.caption(
    f"{len(shown):,} employer groups, ranked by certified LCA cases. State is the worksite "
    "state. The latest year's withdrawn rate is low because recent cases have had less "
    "time to be withdrawn."
)
st.dataframe(
    shown,
    hide_index=True,
    width="stretch",
    column_config={
        "display_name": text_col("Employer", pinned=True),
        "cases": count_col("Cases"),
        **{c: count_col(c.replace("cases_fy", "FY")) for c in shown if c.startswith("cases_fy")},
        "years_active": count_col("Years active"),
        "median_wage_floor": money_col("Median wage floor"),
        "pct_above_pw": pct_col("Above prevailing wage"),
        "level2plus_pct": pct_col("Level II+"),
        "n_leveled": count_col("Cases with a level"),
        "withdrawn_pct": pct_col("Withdrawn"),
        "positions": count_col("Positions"),
        "n_entities": count_col("Filing names"),
        "n_feins": count_col("Legal entities (FEINs)"),
        "top_soc_title": text_col("Top SOC title"),
        "top_state": text_col("Top state"),
    },
)
st.caption(NONE_CAPTION)
slug = re.sub(r"[^a-z0-9]+", "_", f"{family} {state}".lower()).strip("_")
st.download_button(
    "Download CSV",
    shown.to_csv(index=False),
    file_name=f"sponsors_{slug}.csv",
    mime="text/csv",
)
