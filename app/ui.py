"""Shared pieces of the Streamlit app: cached data and the two chart builders."""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from app_data import data_dir, load_tables

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
