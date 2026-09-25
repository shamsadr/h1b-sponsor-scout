"""Find sponsors: ranked employer groups for a role family and worksite state."""

import re

import streamlit as st

from app_data import (
    ALL_OCCUPATIONS_LABEL,
    FAMILY_DESCRIPTIONS,
    FAMILY_ORDER,
    MIN_CASES_OPTIONS,
    as_percent,
    consistent_definition,
    filter_sponsors,
    state_label,
    state_options,
    status_line,
    year_columns,
)
from ui import (
    NONE_CAPTION,
    count_col,
    data,
    money_col,
    open_employer,
    pct_col,
    reset_filters,
    text_col,
)

DATA = data()
YEARS = DATA["meta"]["fiscal_years"]
SPONSORS = DATA["sponsors"]
TABLE_HEIGHT = 35 * 16 + 3  # about 15 rows plus the header (35 px each)
EMPTY_MESSAGE = (
    "No employers match these filters. Try lowering the minimum certified LCAs or unchecking "
    "'Consistent sponsors only'."
)


def family_label(family: str) -> str:
    if family == ALL_OCCUPATIONS_LABEL:
        return "All occupations (any H-1B role) · broad view"
    return family


def column_config(year_cols: list[str]) -> dict:
    """Headers, units, formats and help text for every sponsor column."""
    config = {
        "display_name": text_col(
            "Employer",
            "Brand-level group; see Employer lookup for legal entities",
            pinned=True,
        ),
        "cases": count_col(
            "Certified LCAs",
            "Certified labor condition applications, i.e. intent to hire, not hires",
        ),
        "median_wage_floor": money_col(
            "Median offered wage ($/yr)",
            "Median lower bound of the offered pay range, annualized",
        ),
        "pct_above_pw": pct_col(
            "Pays above prevailing wage",
            "Share of LCAs offering >1% above the DOL prevailing wage",
        ),
        "level2plus_pct": pct_col(
            "Level II+ share",
            "Share at wage Level II–IV. From FY2027 these get more lottery entries",
        ),
        "withdrawn_pct": pct_col(
            "Withdrawn",
            "Share of all filings later withdrawn. The latest year is low because its LCAs "
            "have had less time to be withdrawn.",
        ),
        "n_leveled": count_col("LCAs with a wage level", "Denominator for the Level II+ share"),
        "top_soc_title": text_col("Top SOC title", "Most common occupation code title"),
        "n_entities": count_col("Filing names", "Employer names in this group that filed here"),
        "n_feins": count_col(
            "Legal entities (FEINs)", "Distinct employer tax IDs (FEINs) on these LCAs"
        ),
        "positions": count_col(
            "Worker positions", "Positions requested on these LCAs; one LCA can cover many"
        ),
    }
    for col in year_cols:
        config[col] = count_col(col.replace("cases_", "").upper(), "Certified LCAs by fiscal year")
    return config


families = [f for f in FAMILY_ORDER if f in set(SPONSORS["family"])]
if st.session_state["family"] not in families:  # e.g. a family missing from demo data
    st.session_state["family"] = families[0]

st.title("Find sponsors")
c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
family = c1.selectbox("Role family", families, key="family", format_func=family_label)
c1.caption(FAMILY_DESCRIPTIONS.get(family, ""))
state = c2.selectbox(
    "Worksite state",
    state_options(SPONSORS["state"].unique()),
    key="state",
    format_func=state_label,
)
c2.caption("Worksite state of the job, not company headquarters.")
min_cases = c3.select_slider("Minimum certified LCAs", MIN_CASES_OPTIONS, key="min_cases")
definition = consistent_definition(min_cases, YEARS)
c4.write("")  # align the checkbox with the inputs
consistent = c4.checkbox("Consistent sponsors only", key="consistent", help=definition)
c4.caption(definition)

table = filter_sponsors(SPONSORS, family, state, min_cases, consistent)
st.markdown(status_line(len(table), family, state, consistent, min_cases))
if table.empty:
    st.info(EMPTY_MESSAGE)
    st.button("Reset filters", on_click=reset_filters, type="primary")
else:
    shown = as_percent(table).drop(columns="parent_group")
    years = year_columns(shown)
    default_cols = ["display_name", "cases", *years, "median_wage_floor"]
    default_cols += ["pct_above_pw", "level2plus_pct"]
    advanced_cols = ["withdrawn_pct", "n_leveled", "top_soc_title", "n_entities", "n_feins"]
    advanced_cols += ["positions"]
    t1, t2 = st.columns([4, 1])
    advanced = t1.toggle("Show advanced columns")
    t2.button("Reset filters", on_click=reset_filters)
    cols = default_cols + (advanced_cols if advanced else [])
    event = st.dataframe(
        shown,
        hide_index=True,
        width="stretch",
        column_order=cols,
        column_config=column_config(years),
        height=TABLE_HEIGHT,
        on_select="rerun",
        selection_mode="single-row",
        key="sponsor_table",
    )
    st.caption(f"Select a row to open that employer in Employer lookup. {NONE_CAPTION}")
    if event.selection.rows:
        open_employer(table.iloc[event.selection.rows[0]]["parent_group"])
    slug = re.sub(r"[^a-z0-9]+", "_", f"{family} {state}".lower()).strip("_")
    st.download_button(
        "Download CSV",
        shown[default_cols + advanced_cols].to_csv(index=False),
        file_name=f"sponsors_{slug}.csv",
        mime="text/csv",
    )
