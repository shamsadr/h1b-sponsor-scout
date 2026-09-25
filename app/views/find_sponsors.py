"""Find sponsors: ranked employer groups for a role family and worksite state."""

import re

import streamlit as st
from app_data import ANALYTICS_LABEL, STATE_ALL, as_percent, filter_sponsors, years_label
from ui import data

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
shown = as_percent(table)
st.caption(
    f"{len(shown):,} employer groups, ranked by certified LCA cases. State is the worksite "
    "state. The latest year's withdrawn rate is low because recent cases have had less "
    "time to be withdrawn."
)
pct = "%.0f%%"
st.dataframe(
    shown,
    hide_index=True,
    width="stretch",
    column_config={
        "parent_group": st.column_config.TextColumn("Employer group", pinned=True),
        "cases": st.column_config.NumberColumn("Cases", format="localized"),
        "years_active": st.column_config.NumberColumn("Years active"),
        "median_wage_floor": st.column_config.NumberColumn(
            "Median wage floor (USD)", format="localized"
        ),
        "pct_above_pw": st.column_config.NumberColumn("Above prevailing wage", format=pct),
        "level2plus_pct": st.column_config.NumberColumn("Level II+", format=pct),
        "n_leveled": st.column_config.NumberColumn("Cases with a level", format="localized"),
        "withdrawn_pct": st.column_config.NumberColumn("Withdrawn", format=pct),
        "positions": st.column_config.NumberColumn("Positions", format="localized"),
        "n_entities": st.column_config.NumberColumn("Names in group"),
        "top_soc_title": st.column_config.TextColumn("Top SOC title"),
        "top_state": st.column_config.TextColumn("Top state"),
    },
)
slug = re.sub(r"[^a-z0-9]+", "_", f"{family} {state}".lower()).strip("_")
st.download_button(
    "Download CSV",
    shown.to_csv(index=False),
    file_name=f"sponsors_{slug}.csv",
    mime="text/csv",
)
