"""Employer lookup: pick an employer (quick picks or search), see a summary card, then detail."""

import streamlit as st

from app_data import (
    ALL_OCCUPATIONS_LABEL,
    CURATED_MIN_LCAS,
    CURATED_SETS,
    STATE_ALL,
    load_curated_sets,
    lookup_options,
    resolve_option,
    top_groups,
    years_label,
)
from ui import (
    cases_by_year_chart,
    count_col,
    data,
    fmt_count,
    fmt_money,
    fmt_pct,
    level_chart,
    text_col,
)

DATA = data()
SPONSORS, GROUPS, MEMBERS = DATA["sponsors"], DATA["groups"], DATA["members"]
YEARS = DATA["meta"]["fiscal_years"]
NAMES = GROUPS.set_index("parent_group")["display_name"]
BY_NAME = GROUPS.set_index("display_name")["parent_group"]


def name_of(group: str) -> str:
    return NAMES.get(group, group)


def choose(widget_key: str) -> None:
    """Quick-pick callback: open the picked group and clear the pick."""
    group = st.session_state.get(widget_key)
    if group:
        st.session_state["employer"] = group
        st.session_state["lookup_choice"] = group
    st.session_state[widget_key] = None


def chose_in_selectbox() -> None:
    st.session_state["employer"] = resolve_option(st.session_state.get("lookup_choice"), MEMBERS)


def summary_card(group: str, family: str) -> None:
    """Display name, certified LCAs, years active, median wage and Level II+ share."""
    row = SPONSORS[
        (SPONSORS["parent_group"] == group)
        & (SPONSORS["family"] == family)
        & (SPONSORS["state"] == STATE_ALL)
    ]
    scope = family
    if row.empty:  # no certified LCAs in the current role group: show the broad view
        scope = ALL_OCCUPATIONS_LABEL
        row = SPONSORS[
            (SPONSORS["parent_group"] == group)
            & (SPONSORS["family"] == scope)
            & (SPONSORS["state"] == STATE_ALL)
        ]
    with st.container(border=True):
        st.subheader(name_of(group))
        if row.empty:
            st.write("No certified LCAs in the loaded years.")
            return
        r = row.iloc[0]
        st.caption(f"{scope} · all states · {years_label(YEARS)}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Certified LCAs", fmt_count(r["cases"]))
        m2.metric("Years active", f"{int(r['years_active'])} of {len(YEARS)}")
        m3.metric("Median offered wage", fmt_money(r["median_wage_floor"]))
        m4.metric("Level II+ share", fmt_pct(r["level2plus_share"]))
        per_year = " · ".join(f"FY{y}: {fmt_count(r[f'cases_fy{y}'])}" for y in YEARS)
        st.caption(
            f"{per_year} · {fmt_count(r['n_entities'])} filing names · "
            f"{fmt_count(r['n_feins'])} legal entities (FEINs)"
        )


def detail(group: str) -> None:
    """Cases by role family and year, wage-level mix, member names."""
    b = DATA["employer_breakdown"]
    b = b[b["parent_group"] == group]
    left, right = st.columns(2)
    with left:
        st.subheader("Certified LCAs by role family and year")
        by = b.groupby(["soc_family", "fiscal_year"], as_index=False)["cases"].sum()
        by = by[by["cases"] > 0]
        if by.empty:
            st.write("No certified LCAs.")
        else:
            st.altair_chart(cases_by_year_chart(by, "soc_family"), width="stretch")
            with st.expander("Table"):
                wide = by.pivot(index="soc_family", columns="fiscal_year", values="cases")
                wide = wide.fillna(0).astype(int)
                wide.columns = [f"FY{y}" for y in wide.columns]
                st.dataframe(wide, column_config={c: count_col(c) for c in wide.columns})
    with right:
        st.subheader("Wage-level mix (certified, all roles)")
        lv = DATA["employer_levels"]
        lv = lv[lv["parent_group"] == group]
        if lv.empty:
            st.write("No certified LCAs.")
        else:
            st.altair_chart(level_chart(lv), width="stretch")
            st.caption(
                "Level depends on the SOC code the employer chose; 'Not leveled' means a DOL "
                "determination or private survey was used."
            )
    st.subheader("Member names")
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
        picked_set = st.pills(
            "Curated sets",
            list(sets),
            format_func=lambda s: f"{s} (curated)",
            key="pick_set",
        )
        st.caption(
            f"Curated sets list employers with at least {CURATED_MIN_LCAS} certified "
            f"target-role LCAs in {years_label(YEARS)}."
        )
        if picked_set:
            st.pills(
                picked_set,
                sets[picked_set],
                format_func=name_of,
                key="pick_member",
                on_change=choose,
                args=("pick_member",),
            )

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
