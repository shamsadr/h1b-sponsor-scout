"""Employer lookup: pick an employer (quick picks, curated sets or search), then see a summary
card and detail for it."""

import streamlit as st

from app_data import (
    ALL_OCCUPATIONS_LABEL,
    CURATED_MIN_LCAS,
    CURATED_SETS,
    STATE_ALL,
    TARGET_FAMILIES,
    as_percent,
    curated_table,
    load_curated_sets,
    lookup_options,
    plural,
    resolve_option,
    top_groups,
    year_columns,
    years_label,
)
from ui import (
    MUTED_GRAY,
    count_col,
    data,
    family_totals_chart,
    fmt_count,
    fmt_money,
    fmt_pct,
    level_chart,
    open_employer,
    pct_col,
    sponsor_column_config,
    text_col,
)

DATA = data()
SPONSORS, GROUPS, MEMBERS = DATA["sponsors"], DATA["groups"], DATA["members"]
YEARS = DATA["meta"]["fiscal_years"]
NAMES = GROUPS.set_index("parent_group")["display_name"]
BY_NAME = GROUPS.set_index("display_name")["parent_group"]
LEVEL_NOTE = (
    "From FY2027 the H-1B lottery gives Level II–IV registrations more entries than Level I. "
    "'Not leveled' means a DOL determination or private survey set the prevailing wage."
)


def name_of(group: str) -> str:
    return NAMES.get(group, group)


def sponsor_row(group: str, family: str):
    """The all-states sponsor row for `group` in `family`, or None."""
    row = SPONSORS[
        (SPONSORS["parent_group"] == group)
        & (SPONSORS["family"] == family)
        & (SPONSORS["state"] == STATE_ALL)
    ]
    return None if row.empty else row.iloc[0]


def choose(widget_key: str) -> None:
    """Quick-pick callback: open the picked group and clear the pick."""
    group = st.session_state.get(widget_key)
    if group:
        st.session_state["employer"] = group
        st.session_state["lookup_choice"] = group
    st.session_state[widget_key] = None


def chose_in_selectbox() -> None:
    st.session_state["employer"] = resolve_option(st.session_state.get("lookup_choice"), MEMBERS)


def set_comparison(set_name: str, members: list[str], family: str) -> None:
    """Table of a curated set's members in `family`; selecting a row opens that employer."""
    table = curated_table(SPONSORS, NAMES, members, family)
    shown = as_percent(table)
    years = year_columns(shown)
    cols = ["display_name", "cases", *years, "median_wage_floor", "pct_above_pw"]
    cols += ["level2plus_pct", "note"]
    zero = shown["cases"].eq(0)
    gray = MUTED_GRAY  # de-emphasized; the Note column says why
    styled = shown[cols].style.apply(
        lambda r: [f"color: {gray}" if zero[r.name] else "" for _ in r], axis=1
    )
    config = sponsor_column_config(years) | {"note": text_col("Note", width="medium")}
    event = st.dataframe(
        styled,
        hide_index=True,
        width="stretch",
        height=35 * (len(shown) + 1) + 3,  # every member visible, no inner scroll
        column_config=config,
        on_select="rerun",
        selection_mode="single-row",
        key=f"set_table_{set_name}",
    )
    st.caption(
        f"{set_name} in {family}, all states, {years_label(YEARS)}. Select a row to open it."
    )
    rows = event.selection.rows
    picked = table.iloc[rows[0]]["parent_group"] if rows else None
    if picked and st.session_state.get("_set_pick") != (set_name, picked):
        st.session_state["_set_pick"] = (set_name, picked)  # act once per new selection
        open_employer(picked, switch=False)


def summary_card(group: str, family: str) -> None:
    """Certified LCAs in the role family and in all roles, years active, wage and level."""
    row = sponsor_row(group, family)
    everything = sponsor_row(group, ALL_OCCUPATIONS_LABEL)
    scope = row if row is not None else everything
    scope_name = family if row is not None else "all roles"
    with st.container(border=True):
        st.subheader(name_of(group))
        if everything is None:
            st.write("No certified LCAs in the loaded years.")
            return
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric(f"Certified LCAs in {family}", fmt_count(0 if row is None else row["cases"]))
        m2.metric("Certified LCAs — all roles", fmt_count(everything["cases"]))
        m3.metric("Years active", f"{int(scope['years_active'])} of {len(YEARS)}")
        m4.metric("Median offered wage", fmt_money(scope["median_wage_floor"]))
        m5.metric("Level II+ share", fmt_pct(scope["level2plus_share"]))
        per_year = " · ".join(f"FY{y}: {fmt_count(scope[f'cases_fy{y}'])}" for y in YEARS)
        st.caption(
            f"Years active, wage and Level II+ share: {scope_name}, all states, "
            f"{years_label(YEARS)}. {per_year} · "
            f"{plural(int(scope['n_entities']), 'filing name')} · "
            f"{plural(int(scope['n_feins']), 'legal entity', 'legal entities')} (FEINs)"
        )


def detail(group: str) -> None:
    """LCAs by role family, wage-level mix, and how the group was built."""
    b = DATA["employer_breakdown"]
    b = b[b["parent_group"] == group]
    left, right = st.columns(2)
    with left:
        st.subheader("LCAs by role family")
        by = b.groupby(["soc_family", "fiscal_year"], as_index=False)["cases"].sum()
        if by["cases"].sum() == 0:
            st.write("No certified LCAs.")
        else:
            st.altair_chart(family_totals_chart(by, TARGET_FAMILIES), width="stretch")
            st.caption(f"Certified LCAs, all roles and states, {years_label(YEARS)}.")
            with st.expander("Table"):
                wide = by[by["cases"] > 0].pivot(
                    index="soc_family", columns="fiscal_year", values="cases"
                )
                wide = wide.fillna(0).astype(int)
                wide.columns = [f"FY{y}" for y in wide.columns]
                wide.index.name = "Role family"
                st.dataframe(wide, column_config={c: count_col(c) for c in wide.columns})
    with right:
        st.subheader("Wage-level mix")
        lv = DATA["employer_levels"]
        lv = lv[lv["parent_group"] == group]
        if lv.empty:
            st.write("No certified LCAs.")
        else:
            st.altair_chart(level_chart(lv), width="stretch")
            st.caption(f"Share of certified LCAs, all roles, {years_label(YEARS)}. {LEVEL_NOTE}")
            with st.expander("Table"):
                t = lv.groupby("level")["cases"].sum()
                t = t.reindex(["I", "II", "III", "IV", "Not leveled"]).dropna().astype(int)
                table = t.rename("Certified LCAs").to_frame()
                table["Share"] = 100 * table["Certified LCAs"] / table["Certified LCAs"].sum()
                table.index.name = "Wage level"
                st.dataframe(
                    table,
                    column_config={
                        "Certified LCAs": count_col("Certified LCAs"),
                        "Share": pct_col("Share"),
                    },
                )
    with st.expander("How this employer group was built (technical)"):
        st.caption(
            "Filing names are joined into one group when they share a tax ID (FEIN), match "
            "after normalizing, or are merged by hand as one hiring brand."
        )
        members = MEMBERS[MEMBERS["parent_group"] == group]
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


def render() -> None:
    """Draw the page (a function, so an early return keeps the app footer)."""
    st.session_state["_on_lookup"] = True
    family = st.session_state["family"]
    if "employer" not in st.session_state:  # first visit: a shared link may name one
        from_url = st.query_params.get("employer")
        st.session_state["employer"] = BY_NAME.get(from_url) if from_url else None
        st.session_state["lookup_choice"] = st.session_state["employer"]

    st.title("Employer lookup")
    top = top_groups(SPONSORS, family)
    if top:
        st.pills(
            f"Top in {family}",
            top,
            format_func=name_of,
            key="pick_top",
            on_change=choose,
            args=("pick_top",),
        )
    sets = load_curated_sets(CURATED_SETS, NAMES.index)
    if sets:
        picked_set = st.pills("Curated sets", list(sets), key="pick_set")
        st.caption(
            f"Curated sets list employers with at least {CURATED_MIN_LCAS} certified "
            f"target-role LCAs in {years_label(YEARS)}."
        )
        if picked_set:
            set_comparison(picked_set, sets[picked_set], family)

    options, labels = lookup_options(SPONSORS, GROUPS, MEMBERS, family)
    employer = st.session_state.get("employer")
    choice = st.session_state.get("lookup_choice")
    for extra in {employer, choice} - {None} - set(options):  # e.g. picked from another family
        options.insert(0, extra)
        labels[extra] = name_of(extra)
    st.selectbox(
        "Employer",
        options,
        key="lookup_choice",
        index=None,
        format_func=lambda o: labels.get(o, o),
        placeholder="Type a name, e.g. Deloitte or Merrill",
        on_change=chose_in_selectbox,
        help="Searches employer names and every legal-entity name in each group.",
    )
    st.caption(f"Listing employers with certified LCAs in {family}.")
    if not employer:
        st.info("Pick a quick pick above, or type an employer name.")
        return
    st.query_params["employer"] = name_of(employer)
    summary_card(employer, family)
    detail(employer)


render()
