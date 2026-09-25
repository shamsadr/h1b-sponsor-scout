"""Shared pieces of the Streamlit app: cached data, formatting and the two chart builders."""

import math
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from app_data import FILTER_DEFAULTS, data_dir, encode_query, load_tables, parse_query

# Colors. Every bar color clears 3:1 against its theme's background (WCAG 1.4.11) and every
# text color clears 4.5:1 (WCAG 1.4.3), so ramps and muted text depend on the theme.
SERIES_BLUE = "#2a78d6"  # 4.4:1 on white, 4.3:1 on Streamlit's dark background
# Ordinal ramps for fiscal years (older -> lighter), per theme: steps 400-600 on light
# (3.6-8.1:1 on white), steps 250-500 on dark (9.0-3.5:1 on #0e1117).
YEAR_RAMPS = {
    "light": ["#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95"],
    "dark": ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf"],
}
MUTED_TEXT = {"light": "#6b6a66", "dark": "#a3a29c"}  # 5.4:1 and 7.4:1
REFERENCE_GRAY = "#898781"  # bars only (3.6:1 light, 5.3:1 dark): a reference, not a series
CONTEXT_GRAY = REFERENCE_GRAY
LEVEL_COLORS = {level: SERIES_BLUE for level in ["I", "II", "III", "IV"]}
LEVEL_COLORS["Not leveled"] = REFERENCE_GRAY  # the axis names each bar; gray = no level


def theme() -> str:
    """'light' or 'dark', the viewer's active Streamlit theme (light if unknown)."""
    try:
        kind = st.context.theme.type
    except AttributeError:
        kind = None
    return kind if kind in ("light", "dark") else "light"


def muted_text() -> str:
    """Gray for de-emphasized text that still clears 4.5:1 in the current theme."""
    return MUTED_TEXT[theme()]


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


def text_col(label: str, help: str | None = None, pinned: bool = False, width=None):
    return st.column_config.TextColumn(label, help=help, pinned=pinned, width=width)


NONE_CAPTION = "None = not enough full-time or leveled LCAs to compute that value."


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
    for key in ("employer", "lookup_choice"):  # keep the chosen employer across pages
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]
    st.session_state["_on_lookup"] = False  # Employer lookup sets it while it runs


def sync_url() -> None:
    """Write the current filters to the URL so the view can be shared or bookmarked.

    The ?employer= parameter belongs to Employer lookup only; other pages drop it.
    """
    filters = {k: st.session_state.get(k, v) for k, v in FILTER_DEFAULTS.items()}
    wanted = encode_query(filters)
    if {k: st.query_params.get(k) for k in wanted} != wanted:
        st.query_params.update(wanted)
    if not st.session_state.get("_on_lookup") and "employer" in st.query_params:
        del st.query_params["employer"]


def open_employer(group: str, switch: bool = True) -> None:
    """Show `group` in Employer lookup (click-through from a table row).

    switch=False when already on Employer lookup (call it before the employer selectbox).
    """
    st.session_state["employer"] = group
    st.session_state["lookup_choice"] = group
    if switch:
        st.switch_page("views/employer_lookup.py")


def sponsor_column_config(year_cols: list[str]) -> dict:
    """Headers, units, formats and help text for every sponsor column."""
    config = {
        "display_name": text_col(
            "Employer",
            "Brand-level group; see Employer lookup for legal entities",
            pinned=True,
            width="medium",
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


def reset_filters() -> None:
    """Put every shared filter back to its default (button callback)."""
    for key, value in FILTER_DEFAULTS.items():
        st.session_state[key] = value


def year_ramp(years: list[int]) -> list[str]:
    """One ramp step per fiscal year, spread across the current theme's ramp."""
    steps = YEAR_RAMPS[theme()]
    if len(years) == 1:
        return [SERIES_BLUE]
    idx = [round(i * (len(steps) - 1) / (len(years) - 1)) for i in range(len(years))]
    return [steps[i] for i in idx]


CATEGORY_TITLES = {"soc_family": "Role family", "family": "Role family"}


def cases_by_year_chart(df: pd.DataFrame, category: str) -> alt.Chart:
    """Horizontal bars of certified LCAs per category, one bar per fiscal year."""
    years = sorted(df["fiscal_year"].unique().tolist())
    order = df.groupby(category)["cases"].sum().sort_values(ascending=False).index.tolist()
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4, height={"band": 0.9})
        .encode(
            y=alt.Y(f"{category}:N", sort=order, title=None, axis=alt.Axis(labelLimit=260)),
            yOffset=alt.YOffset("fiscal_year:O", sort=years),
            x=alt.X("cases:Q", title="Certified LCAs"),
            color=alt.Color(
                "fiscal_year:O",
                title="Fiscal year",
                scale=alt.Scale(domain=years, range=year_ramp(years)),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip(f"{category}:N", title=CATEGORY_TITLES.get(category, category)),
                alt.Tooltip("fiscal_year:O", title="Fiscal year"),
                alt.Tooltip("cases:Q", title="Certified LCAs", format=","),
            ],
        )
        .properties(height=alt.Step(14))
    )


REFERENCE_GRAY = "#898781"  # muted ink: marks a reference bar, not a data series


def pct_change_chart(d: pd.DataFrame, reference: str, first: int, last: int) -> alt.Chart:
    """Horizontal bars of % change per family; `reference` is gray and labelled as such.

    Families with no LCAs in the first year have no % change and are left out.
    """
    d = d.dropna(subset=["pct_change"])
    d = d.assign(
        label=d["family"].where(d["family"] != reference, reference + " · reference"),
        kind=(d["family"] == reference).map({True: "Reference", False: "Role family"}),
        text=d["pct_change"].map(lambda v: f"{v:+.0%}"),
    )
    order = d.sort_values("pct_change", ascending=False)["label"].tolist()
    base = alt.Chart(d).encode(
        y=alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=320)),
        x=alt.X(
            "pct_change:Q",
            title=f"Change in certified LCAs, FY{first} → FY{last}",
            axis=alt.Axis(format="+.0%"),
        ),
    )
    bars = base.mark_bar(cornerRadiusEnd=4, height={"band": 0.7}).encode(
        color=alt.Color(
            "kind:N",
            scale=alt.Scale(
                domain=["Role family", "Reference"], range=[SERIES_BLUE, REFERENCE_GRAY]
            ),
            legend=alt.Legend(title=None, orient="top"),
        ),
        tooltip=[
            alt.Tooltip("family:N", title="Role family"),
            alt.Tooltip("first:Q", title=f"FY{first} certified LCAs", format=","),
            alt.Tooltip("last:Q", title=f"FY{last} certified LCAs", format=","),
            alt.Tooltip("text:N", title="Change"),
        ],
    )
    # Value labels just past each bar's end: right of positive bars, left of negative ones.
    pos = base.transform_filter("datum.pct_change >= 0").mark_text(align="left", dx=4)
    neg = base.transform_filter("datum.pct_change < 0").mark_text(align="right", dx=-4)
    labels = alt.layer(
        *[layer.encode(text="text:N", color=alt.value(muted_text())) for layer in (pos, neg)]
    )
    rule = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=REFERENCE_GRAY).encode(x="x:Q")
    return (bars + labels + rule).properties(height=alt.Step(26))


def family_totals_chart(by: pd.DataFrame, target_families: list[str]) -> alt.Chart:
    """One bar per role family (all loaded years), target families blue, others gray.

    by: rows of soc_family, fiscal_year, cases. Zero rows are dropped; sorted by total.
    """
    wide = by.pivot_table(
        index="soc_family", columns="fiscal_year", values="cases", aggfunc="sum", fill_value=0
    )
    years = sorted(wide.columns)
    d = pd.DataFrame({"soc_family": wide.index, "total": wide.sum(axis=1).to_numpy()})
    for y in years:
        d[f"fy{y}"] = wide[y].to_numpy()
    d = d[d["total"] > 0]
    d["kind"] = (
        d["soc_family"]
        .isin(target_families)
        .map({True: "Target role family", False: "Other roles (context)"})
    )
    order = d.sort_values("total", ascending=False)["soc_family"].tolist()
    return (
        alt.Chart(d)
        .mark_bar(cornerRadiusEnd=4, height={"band": 0.7})
        .encode(
            y=alt.Y("soc_family:N", sort=order, title=None, axis=alt.Axis(labelLimit=260)),
            x=alt.X("total:Q", title="Certified LCAs"),
            color=alt.Color(
                "kind:N",
                scale=alt.Scale(
                    domain=["Target role family", "Other roles (context)"],
                    range=[SERIES_BLUE, CONTEXT_GRAY],
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[alt.Tooltip("soc_family:N", title="Role family")]
            + [alt.Tooltip("total:Q", title="Certified LCAs", format=",")]
            + [alt.Tooltip(f"fy{y}:Q", title=f"FY{y}", format=",") for y in years],
        )
        .properties(height=alt.Step(24))
    )


def level_chart(levels: pd.DataFrame) -> alt.Chart:
    """Share of certified LCAs by wage level I-IV plus 'Not leveled' (counts on hover)."""
    order = list(LEVEL_COLORS)
    d = levels.groupby("level", as_index=False)["cases"].sum()
    d["share"] = d["cases"] / d["cases"].sum()
    return (
        alt.Chart(d)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("level:N", sort=order, title="Wage level", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("share:Q", title="Share", axis=alt.Axis(format="%")),
            color=alt.Color(
                "level:N",
                scale=alt.Scale(domain=order, range=list(LEVEL_COLORS.values())),
                legend=None,  # the axis names each bar
            ),
            tooltip=[
                alt.Tooltip("level:N", title="Wage level"),
                alt.Tooltip("share:Q", title="Share", format=".0%"),
                alt.Tooltip("cases:Q", title="Certified LCAs", format=","),
            ],
        )
        .properties(height=260)
    )
