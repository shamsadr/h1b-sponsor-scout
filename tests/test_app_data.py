"""Pure helpers behind the Streamlit app (no Streamlit needed)."""

import pandas as pd
import pytest

from app.app_data import (
    ANALYTICS_LABEL,
    STATE_ALL,
    as_percent,
    filter_sponsors,
    footer_text,
    readme_bullet,
    readme_sections,
    search_groups,
    years_label,
)
from h1b import config, publish


def sponsors(**cols) -> pd.DataFrame:
    base = {
        "family": "Operations Research",
        "state": STATE_ALL,
        "parent_group": ["A", "B", "C", "D"],
        "cases": [50, 30, 8, 3],
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


def test_consistent_only_keeps_groups_active_in_every_loaded_year():
    df = sponsors()
    everyone = filter_sponsors(df, "Operations Research", min_cases=1, n_years=2)
    assert everyone["parent_group"].tolist() == ["A", "B", "C", "D"]
    consistent = filter_sponsors(
        df, "Operations Research", min_cases=1, consistent_only=True, n_years=2
    )
    assert consistent["parent_group"].tolist() == ["A", "C", "D"]  # B has 1 of 2 years
    one_year = filter_sponsors(
        df, "Operations Research", min_cases=1, consistent_only=True, n_years=1
    )
    assert one_year["parent_group"].tolist() == ["B"]


def test_filter_sponsors_min_cases_state_and_ranking():
    df = pd.concat(
        [sponsors(), sponsors(state="TX", parent_group=["A", "B", "C", "D"], cases=[1, 9, 9, 6])],
        ignore_index=True,
    )
    out = filter_sponsors(df, "Operations Research", min_cases=5, n_years=2)
    assert out["parent_group"].tolist() == ["A", "B", "C"]  # D has 3 cases < 5
    assert "family" not in out.columns and "state" not in out.columns
    tx = filter_sponsors(df, "Operations Research", state="TX", min_cases=5, n_years=2)
    assert tx["parent_group"].tolist() == ["B", "C", "D"]  # ties broken by name
    assert filter_sponsors(df, "Quant / Finance", n_years=2).empty


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
