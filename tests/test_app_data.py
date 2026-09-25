"""Pure helpers behind the Streamlit app (no Streamlit needed)."""

import pandas as pd
import pytest

from app_data import (
    ALIAS_PREFIX,
    ALL_OCCUPATIONS_LABEL,
    ALL_TARGET_LABEL,
    ANALYTICS_LABEL,
    CURATED_SETS,
    FAMILY_DESCRIPTIONS,
    FAMILY_ORDER,
    FILTER_DEFAULTS,
    ROOT,
    STATE_ALL,
    STATE_NAMES,
    as_percent,
    consistent_definition,
    encode_query,
    filter_sponsors,
    footer_text,
    load_curated_sets,
    lookup_options,
    parse_query,
    readme_bullet,
    readme_sections,
    resolve_option,
    search_groups,
    state_label,
    state_options,
    status_line,
    top_groups,
    year_columns,
    years_label,
)
from h1b import config, publish


def sponsors(**cols) -> pd.DataFrame:
    base = {
        "family": "Operations Research",
        "state": STATE_ALL,
        "parent_group": ["A", "B", "C", "D"],
        "display_name": ["Acme", "Beta", "Cyan", "Delta"],
        "cases": [50, 30, 8, 3],
        "cases_fy2024": [30, 30, 4, 1],
        "cases_fy2025": [20, 0, 4, 2],
        "years_active": [2, 1, 2, 2],
        "share_above_pw": [0.5, 0.2, 1.0, 0.0],
        "level2plus_share": [0.9, 0.1, 0.5, 1.0],
        "withdrawn_rate": [0.1, 0.0, 0.0, 0.25],
    }
    base.update(cols)
    return pd.DataFrame(base)


def test_constants_match_the_pipeline():
    assert STATE_ALL == publish.STATE_ALL
    assert ANALYTICS_LABEL == config.ANALYTICS_LABEL
    assert ALL_TARGET_LABEL == config.ALL_TARGET_LABEL
    assert ALL_OCCUPATIONS_LABEL == config.ALL_OCCUPATIONS_LABEL


def test_consistent_needs_n_cases_in_every_year_not_in_total():
    # 12 cases in FY24 and 3 in FY25: 15 in total, but only 3 in the weaker year.
    df = sponsors(
        parent_group=["X", "Y", "Z", "W"],
        display_name=["X", "Y", "Z", "W"],
        cases=[15, 10, 6, 2],
        cases_fy2024=[12, 5, 3, 1],
        cases_fy2025=[3, 5, 3, 1],
    )

    def names(n, consistent):
        out = filter_sponsors(df, "Operations Research", min_cases=n, consistent_only=consistent)
        return out["parent_group"].tolist()

    assert "X" not in names(5, True)  # fails at N=5 (FY25 has 3)
    assert "X" in names(3, True)  # passes at N=3
    assert names(5, True) == ["Y"]
    assert names(5, False) == ["X", "Y", "Z"]  # unchecked: N applies to the total


def test_filter_sponsors_min_cases_state_and_ranking():
    df = pd.concat(
        [sponsors(), sponsors(state="TX", cases=[1, 9, 9, 6])],
        ignore_index=True,
    )
    out = filter_sponsors(df, "Operations Research", min_cases=5)
    assert out["parent_group"].tolist() == ["A", "B", "C"]  # D has 3 cases < 5
    assert "family" not in out.columns and "state" not in out.columns
    tx = filter_sponsors(df, "Operations Research", state="TX", min_cases=5)
    assert tx["display_name"].tolist() == ["Beta", "Cyan", "Delta"]  # ties broken by name
    assert filter_sponsors(df, "Quant / Finance").empty


def test_year_columns_and_consistent_definition():
    assert year_columns(sponsors()) == ["cases_fy2024", "cases_fy2025"]
    text = consistent_definition(10, [2025, 2024])
    assert text == (
        "Filed at least 10 certified LCAs in this role group in every loaded fiscal year "
        "(FY2024 and FY2025)."
    )


def test_status_line():
    assert status_line(312, ANALYTICS_LABEL, "AZ", True, 5) == (
        "Showing **312 employers** · Analytics (combined) · Arizona · consistent only · "
        "min 5 cases/year"
    )
    assert status_line(1, "Operations Research", STATE_ALL, False, 3) == (
        "Showing **1 employer** · Operations Research · All states · min 3 cases"
    )


def test_state_labels_and_order():
    assert state_label("AZ") == "Arizona (AZ)"
    assert state_label(STATE_ALL) == "All states"
    assert state_label("ZZ") == "ZZ"
    assert state_options(["TX", STATE_ALL, "AZ", "AK"]) == [STATE_ALL, "AK", "AZ", "TX"]
    assert state_options(["NY", "NC", "ND"]) == [STATE_ALL, "NY", "NC", "ND"]  # by full name


def test_committed_data_states_families_and_descriptions():
    folder = ROOT / "data" / "app"
    if not (folder / "sponsors.parquet").exists():
        pytest.skip("data/app/ not published yet")
    s = pd.read_parquet(folder / "sponsors.parquet", columns=["family", "state"])
    codes = set(s["state"].astype(str)) - {STATE_ALL}
    assert codes <= set(STATE_NAMES), codes - set(STATE_NAMES)  # every code has a full name
    assert set(s["family"].astype(str)) == set(FAMILY_ORDER)
    assert set(FAMILY_DESCRIPTIONS) == set(FAMILY_ORDER)
    assert FAMILY_ORDER[0] == ANALYTICS_LABEL and FAMILY_ORDER[-1] == ALL_OCCUPATIONS_LABEL


def test_as_percent_scales_and_renames_share_columns():
    out = as_percent(sponsors())
    assert {"pct_above_pw", "level2plus_pct", "withdrawn_pct"} <= set(out.columns)
    assert out["pct_above_pw"].tolist() == [50.0, 20.0, 100.0, 0.0]
    assert out["cases"].tolist() == [50, 30, 8, 3]


def test_search_groups_matches_labels_and_member_names_case_insensitive():
    members = pd.DataFrame(
        {
            "parent_group": ["BANK OF AMERICA", "BANK OF AMERICA", "MERRILL EDGE LABS"],
            "employer_norm": ["BANK OF AMERICA N A", "MERRILL LYNCH", "MERRILL EDGE LABS"],
            "rows": [1000, 87, 3],
        }
    )
    assert search_groups(members, "merrill") == ["BANK OF AMERICA", "MERRILL EDGE LABS"]
    assert search_groups(members, "  ") == []
    assert search_groups(members, "zzz") == []


def test_readme_sections_and_bullets_exist():
    headings = ["Scorecard columns", "Employer grouping", "Methodology decisions", "Limitations"]
    sections = readme_sections(headings)
    assert list(sections) == headings and all(sections.values())
    assert readme_bullet("Employers substitute SOC codes").startswith("**Employers substitute")
    assert "right-censored" in readme_bullet("Withdrawals are right-censored")
    with pytest.raises(KeyError):
        readme_sections(["No such heading"])


def test_readme_helpers_on_small_text():
    text = "# T\n## A\nalpha\n- **One** first\n  more\n- **Two** second\n## B\nbeta\n"
    assert readme_sections(["A", "B"], text) == {
        "A": "alpha\n- **One** first\n  more\n- **Two** second",
        "B": "beta",
    }
    assert readme_bullet("One", text) == "**One** first more"


def test_footer_reads_years_from_meta():
    text = footer_text({"fiscal_years": [2025, 2024]})
    assert text.startswith("Source: U.S. DOL OFLC LCA disclosure data, FY2024–FY2025.")
    assert "Not legal or immigration advice." in text
    assert years_label([2025]) == "FY2025"


def test_query_params_round_trip_and_bad_values_fall_back():
    families, states = [ANALYTICS_LABEL, "Operations Research"], [STATE_ALL, "AZ"]
    filters = {"family": "Operations Research", "state": "AZ", "min_cases": 3, "consistent": True}
    params = encode_query(filters)
    assert params == {"role": "Operations Research", "state": "AZ", "min": "3", "consistent": "1"}
    assert parse_query(params, families, states) == filters
    assert parse_query({}, families, states) == FILTER_DEFAULTS
    bad = {"role": "Astronaut", "state": "ZZ", "min": "abc", "consistent": "maybe"}
    assert parse_query(bad, families, states) == FILTER_DEFAULTS
    assert parse_query({"min": "0"}, families, states)["min_cases"] == 5  # out of range
    assert parse_query({"min": "101"}, families, states)["min_cases"] == 5
    assert parse_query({"state": "az"}, families, states)["state"] == "AZ"  # case-insensitive


def lookup_frames():
    sponsors = pd.DataFrame(
        {
            "family": ["Quant / Finance"] * 3 + ["Operations Research"],
            "state": [STATE_ALL] * 4,
            "parent_group": ["BANK OF AMERICA", "GOLDMAN SACHS", "TINY", "GOLDMAN SACHS"],
            "display_name": ["Bank of America", "Goldman Sachs", "Tiny Co", "Goldman Sachs"],
            "cases": [851, 1907, 3, 50],
        }
    )
    groups = sponsors.drop_duplicates("parent_group")[["parent_group", "display_name"]]
    members = pd.DataFrame(
        {
            "parent_group": ["BANK OF AMERICA", "BANK OF AMERICA", "GOLDMAN SACHS", "TINY"],
            "employer_norm": ["BANK OF AMERICA", "MERRILL LYNCH", "GOLDMAN SACHS AND", "TINY"],
            "rows": [1322, 87, 2461, 3],
        }
    )
    return sponsors, groups, members


def test_lookup_options_list_groups_by_size_then_member_aliases():
    sponsors, groups, members = lookup_frames()
    keys, labels = lookup_options(sponsors, groups, members, "Quant / Finance")
    assert keys[:3] == ["GOLDMAN SACHS", "BANK OF AMERICA", "TINY"]
    alias = ALIAS_PREFIX + "MERRILL LYNCH"
    assert alias in keys and labels[alias] == "MERRILL LYNCH → Bank of America"
    assert ALIAS_PREFIX + "BANK OF AMERICA" not in keys  # same as the display name
    assert ALIAS_PREFIX + "TINY" not in keys  # single-name group: nothing to alias
    assert resolve_option(alias, members) == "BANK OF AMERICA"
    assert resolve_option("GOLDMAN SACHS", members) == "GOLDMAN SACHS"
    assert resolve_option(None, members) is None
    only_or, _ = lookup_options(sponsors, groups, members, "Operations Research")
    assert only_or == ["GOLDMAN SACHS"]  # only groups with LCAs in the chosen role group


def test_top_groups_and_curated_sets(tmp_path):
    sponsors, _, _ = lookup_frames()
    assert top_groups(sponsors, "Quant / Finance", n=2) == ["GOLDMAN SACHS", "BANK OF AMERICA"]
    path = tmp_path / "sets.csv"
    path.write_text(
        "set_name,parent_group,display_name\n"
        "Banks,GOLDMAN SACHS,Goldman Sachs\n"
        "Banks,NOT PUBLISHED,Nope\n"
        "Banks,BANK OF AMERICA,Bank of America\n"
        "Empty,NOT PUBLISHED,Nope\n"
    )
    sets = load_curated_sets(path, ["GOLDMAN SACHS", "BANK OF AMERICA"])
    assert sets == {"Banks": ["GOLDMAN SACHS", "BANK OF AMERICA"]}  # file order, unknown dropped
    assert load_curated_sets(tmp_path / "missing.csv", []) == {}


def test_every_curated_set_entry_matches_an_existing_group():
    groups_file = ROOT / "data" / "app" / "groups.parquet"
    if not groups_file.exists():
        pytest.skip("data/app/ not published yet")
    groups = set(pd.read_parquet(groups_file, columns=["parent_group"])["parent_group"])
    curated = pd.read_csv(CURATED_SETS, dtype=str)
    assert list(curated.columns) == ["set_name", "parent_group", "display_name"]
    missing = sorted(set(curated["parent_group"]) - groups)
    assert not missing, missing
    assert not curated.duplicated(["set_name", "parent_group"]).any()
