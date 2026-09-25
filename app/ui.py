"""Shared pieces of the Streamlit app: cached data, formatting and the two chart builders."""

import math
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from app_data import FILTER_DEFAULTS, data_dir, encode_query, load_tables, parse_query

# Ordinal blue ramp (older/lower -> lighter), validated for light and dark surfaces.
BLUE_STEPS = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab"]
BLUE_STEPS += ["#184f95"]
LEVEL_COLORS = {"I": "#86b6ef", "II": "#5598e7", "III": "#256abf", "IV": "#184f95"}
LEVEL_COLORS["Not leveled"] = "#898781"  # muted gray: no level, not a magnitude


@st.cache_data
def tables(folder: str) -> dict:
    """Published tables, loaded once per folder."""
    return load_tables(Path(folder))


def data() -> dict:
    """The published tables for this session (data/app/ or $H1B_APP_DATA)."""
    return tables(str(data_dir()))


# --- Formatting: the one place that decides how numbers look -----------------------------
# Tables keep numeric columns (so sorting works) and format them through column_config;
# a missing value there renders as Streamlit's gray "None" (explained in a caption).
# Scalar displays (metrics, status lines, cards) use the fmt_* helpers, which print "—".
MISSING = "—"
MONEY_FORMAT = "$%,.0f"  # needs streamlit >= 1.55 (older versions ignore the ',' flag)
PERCENT_FORMAT = "%.0f%%"  # applied to 0-100 values (see app_data.as_percent)
COUNT_FORMAT = "localized"


def _missing(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x)) or x is pd.NA


def _round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def fmt_money(x) -> str:
    """137900.4 -> '$137,900'; missing -> '—'."""
    return MISSING if _missing(x) else f"${_round_half_up(float(x)):,}"


def fmt_pct(share) -> str:
    """A 0-1 share -> whole percent: 0.844 -> '84%', 0 -> '0%'; missing -> '—'."""
    return MISSING if _missing(share) else f"{_round_half_up(float(share) * 100)}%"


def fmt_count(n) -> str:
    """1423 -> '1,423'; missing -> '—'."""
    return MISSING if _missing(n) else f"{int(n):,}"


def money_col(label: str, help: str | None = None):
    return st.column_config.NumberColumn(label, format=MONEY_FORMAT, help=help)


def pct_col(label: str, help: str | None = None):
    """For columns already scaled to 0-100."""
    return st.column_config.NumberColumn(label, format=PERCENT_FORMAT, help=help)


def count_col(label: str, help: str | None = None):
    return st.column_config.NumberColumn(label, format=COUNT_FORMAT, help=help)


def text_col(label: str, help: str | None = None, pinned: bool = False):
    return st.column_config.TextColumn(label, help=help, pinned=pinned)


NONE_CAPTION = "None = not enough full-time or leveled cases to compute that value."


# --- Shared filters: one set of values for every page, mirrored in the URL -------------
def init_filters() -> None:
    """Call at the top of every run (main script, before the page runs).

    First run of a session: read the filters from the URL (?role=...&state=...&min=...&
    consistent=1), falling back to defaults for anything missing or invalid. Later runs:
    re-assign each value so Streamlit keeps it while its widget is on another page.
    """
    if "_filters_ready" not in st.session_state:
        sponsors = data()["sponsors"]
        families = sponsors["family"].unique().tolist()
        states = sponsors["state"].unique().tolist()
        params = {k: st.query_params.get(k) for k in st.query_params.keys()}
        st.session_state.update(parse_query(params, families, states))
        st.session_state["_filters_ready"] = True
    for key in FILTER_DEFAULTS:
        st.session_state[key] = st.session_state.get(key, FILTER_DEFAULTS[key])


def sync_url() -> None:
    """Write the current filters to the URL so the view can be shared or bookmarked."""
    filters = {k: st.session_state.get(k, v) for k, v in FILTER_DEFAULTS.items()}
    wanted = encode_query(filters)
    if {k: st.query_params.get(k) for k in wanted} != wanted:
        st.query_params.update(wanted)


def reset_filters() -> None:
    """Put every shared filter back to its default (button callback)."""
    for key, value in FILTER_DEFAULTS.items():
        st.session_state[key] = value


def year_ramp(years: list[int]) -> list[str]:
    """One ramp step per fiscal year, spread across the validated range."""
    if len(years) == 1:
        return [BLUE_STEPS[-1]]
    idx = [round(i * (len(BLUE_STEPS) - 1) / (len(years) - 1)) for i in range(len(years))]
    return [BLUE_STEPS[i] for i in idx]


def cases_by_year_chart(df: pd.DataFrame, category: str) -> alt.Chart:
    """Horizontal bars of certified cases per category, one bar per fiscal year."""
    years = sorted(df["fiscal_year"].unique().tolist())
    order = df.groupby(category)["cases"].sum().sort_values(ascending=False).index.tolist()
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4, height={"band": 0.9})
        .encode(
            y=alt.Y(f"{category}:N", sort=order, title=None, axis=alt.Axis(labelLimit=260)),
            yOffset=alt.YOffset("fiscal_year:O", sort=years),
            x=alt.X("cases:Q", title="Certified cases"),
            color=alt.Color(
                "fiscal_year:O",
                title="Fiscal year",
                scale=alt.Scale(domain=years, range=year_ramp(years)),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip(f"{category}:N", title=category.replace("_", " ").capitalize()),
                alt.Tooltip("fiscal_year:O", title="Fiscal year"),
                alt.Tooltip("cases:Q", title="Certified cases", format=","),
            ],
        )
        .properties(height=alt.Step(14))
    )


def level_chart(levels: pd.DataFrame) -> alt.Chart:
    """Certified cases by wage level I-IV plus 'Not leveled'."""
    order = list(LEVEL_COLORS)
    d = levels.groupby("level", as_index=False)["cases"].sum()
    d["share"] = d["cases"] / d["cases"].sum()
    return (
        alt.Chart(d)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("level:N", sort=order, title="Wage level", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("cases:Q", title="Certified cases"),
            color=alt.Color(
                "level:N",
                scale=alt.Scale(domain=order, range=list(LEVEL_COLORS.values())),
                legend=None,  # the axis names each bar
            ),
            tooltip=[
                alt.Tooltip("level:N", title="Wage level"),
                alt.Tooltip("cases:Q", title="Certified cases", format=","),
                alt.Tooltip("share:Q", title="Share", format=".0%"),
            ],
        )
        .properties(height=260)
    )
