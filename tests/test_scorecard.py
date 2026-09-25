import pandas as pd

from h1b.config import ANALYTICS_COMBINED, ANALYTICS_LABEL
from h1b.scorecard import (
    analysis_groups,
    consistent_sponsors,
    dedupe_across_years,
    employer_scorecard,
    family_scorecards,
    family_trends,
)


def make_rows(n: int = 1, **overrides) -> pd.DataFrame:
    """n cleaned-looking LCA rows for one employer; override any column (scalar or list)."""
    base = {
        "CASE_STATUS": "Certified",
        "EMPLOYER_NAME": "X Inc",
        "SOC_TITLE": "Operations Research Analysts",
        "employer_norm": "X",
        "positions": 1.0,
        "new_hire_positions": 0.0,
        "fiscal_year": 2025,
        "soc_family": "Operations Research",
        "WORKSITE_STATE": "TX",
        "full_time": True,
        "wage_outlier": False,
        "annual_wage": 100_000.0,
        "annual_wage_to": float("nan"),
        "wage_premium": 0.10,
        "pw_level": "II",
        "h1b_dependent": False,
        "willful_violator": False,
    }
    base.update(overrides)
    return pd.DataFrame({k: v if isinstance(v, list) else [v] * n for k, v in base.items()})


def test_only_certified_counts_and_withdrawn_rate():
    status = ["Certified", "Certified", "Withdrawn", "Certified - Withdrawn", "Denied"]
    df = make_rows(
        5,
        CASE_STATUS=status,
        positions=[1.0, 2.0, 10.0, 20.0, 40.0],
        annual_wage=[100_000.0, 120_000.0, 1e6 - 1, 1e6 - 1, 1e6 - 1],
        pw_level=["I", "II", "IV", "IV", "IV"],
    )
    row = employer_scorecard(df).iloc[0]
    assert row["cases"] == 2  # only strict 'Certified'
    assert row["positions"] == 3
    assert row["median_wage_floor"] == 110_000  # withdrawn/denied wages ignored
    assert row["level2plus_share"] == 0.5  # levels from certified rows only
    assert row["withdrawn_rate"] == 2 / 5  # (Withdrawn + Certified - Withdrawn) / all rows
    assert row["denial_rate"] == 1 / 4  # Denied / (Certified* + Denied), unchanged


def test_flags_are_share_and_count_not_any():
    df = make_rows(
        100,
        willful_violator=[True] + [False] * 99,
        h1b_dependent=[True] * 25 + [False] * 75,
    )
    row = employer_scorecard(df).iloc[0]
    assert row["willful_violator_count"] == 1  # one 'Yes' row, not a blanket True
    assert row["h1b_dependent_share"] == 0.25
    assert "willful_violator" not in employer_scorecard(df).columns


def test_share_above_pw_is_zero_when_paying_exactly_pw():
    df = make_rows(10, wage_premium=0.0)
    assert employer_scorecard(df).iloc[0]["share_above_pw"] == 0

    mixed = make_rows(4, wage_premium=[0.0, 0.005, 0.02, 0.30])  # 1% threshold
    assert employer_scorecard(mixed).iloc[0]["share_above_pw"] == 0.5


def test_range_share_and_n_leveled():
    df = make_rows(
        4,
        annual_wage_to=[120_000.0, float("nan"), float("nan"), 130_000.0],
        pw_level=["I", "II", None, None],
    )
    row = employer_scorecard(df).iloc[0]
    assert row["range_share"] == 0.5  # share of rows with a TO wage
    assert row["n_leveled"] == 2  # rows with a wage level I-IV


def test_top_soc_title_is_most_common_certified_title():
    df = make_rows(
        4,
        SOC_TITLE=["Logisticians", "Logisticians", "Purchasing Agents", "Purchasing Agents"],
        CASE_STATUS=["Certified", "Certified", "Certified", "Denied"],
    )
    assert employer_scorecard(df).iloc[0]["top_soc_title"] == "Logisticians"


def test_sorted_by_cases_then_new_hires_with_bulk_filer_flag():
    a = make_rows(2, employer_norm="A", EMPLOYER_NAME="A", positions=[40.0, 40.0])  # 40/case
    b = make_rows(3, employer_norm="B", EMPLOYER_NAME="B", new_hire_positions=[1.0, 1.0, 1.0])
    c = make_rows(3, employer_norm="C", EMPLOYER_NAME="C", new_hire_positions=[5.0, 5.0, 5.0])
    card = employer_scorecard(pd.concat([a, b, c], ignore_index=True))

    assert card["employer_norm"].tolist() == ["C", "B", "A"]  # cases desc, then new hires desc
    by = card.set_index("employer_norm")
    assert by.loc["A", "positions_per_case"] == 40
    assert by.loc["A", "bulk_filer"]
    assert by.loc["B", "positions_per_case"] == 1
    assert not by.loc["B", "bulk_filer"]


def test_bulk_filer_threshold_is_strictly_above_five():
    df = make_rows(2, positions=[5.0, 5.0])  # exactly 5 per case
    assert not employer_scorecard(df).iloc[0]["bulk_filer"]


def test_family_scorecards_top_n_per_family_with_family_column():
    frames = []
    for fam, n_emp in [("Operations Research", 4), ("Quant / Finance", 2), ("Other", 3)]:
        for i in range(n_emp):  # employer i has i+1 cases
            frames.append(
                make_rows(
                    i + 1, soc_family=fam, employer_norm=f"{fam[:2]}{i}", EMPLOYER_NAME=f"E{i}"
                )
            )
    df = pd.concat(frames, ignore_index=True)

    out = family_scorecards(df, ["Operations Research", "Quant / Finance"], top_n=3)
    assert out.columns[0] == "family"
    assert set(out["family"]) == {"Operations Research", "Quant / Finance"}  # 'Other' skipped
    counts = out["family"].value_counts()
    assert counts["Operations Research"] == 3 and counts["Quant / Finance"] == 2  # capped at top_n
    ops = out[out["family"] == "Operations Research"]
    assert ops["cases"].tolist() == [4, 3, 2]  # top by cases


def test_case_certified_then_withdrawn_counts_once_as_first_year_and_withdrawn():
    fy24 = make_rows(
        2,
        CASE_NUMBER=["A", "B"],
        DECISION_DATE=list(pd.to_datetime(["2024-03-01", "2024-04-01"])),
        fiscal_year=2024,
    )
    fy25 = make_rows(
        1,
        CASE_NUMBER=["A"],
        DECISION_DATE=list(pd.to_datetime(["2025-01-10"])),
        fiscal_year=2025,
        CASE_STATUS="Certified - Withdrawn",
    )
    out = dedupe_across_years(pd.concat([fy24, fy25], ignore_index=True))

    assert sorted(out["CASE_NUMBER"]) == ["A", "B"]  # A appears once
    a = out[out["CASE_NUMBER"] == "A"].iloc[0]
    assert a["CASE_STATUS"] == "Certified - Withdrawn"  # latest decision wins
    assert a["fiscal_year"] == 2024  # earliest year it appears
    assert out[out["CASE_NUMBER"] == "B"].iloc[0]["CASE_STATUS"] == "Certified"

    card = employer_scorecard(out).iloc[0]
    assert card["cases"] == 1  # only B is still certified
    assert card["withdrawn_rate"] == 0.5  # A counted once, as withdrawn


def test_dedupe_across_years_leaves_unique_cases_alone():
    df = make_rows(
        3,
        CASE_NUMBER=["A", "B", "C"],
        DECISION_DATE=list(pd.to_datetime(["2024-01-01", "2025-01-01", "2025-02-01"])),
        fiscal_year=[2024, 2025, 2025],
    )
    out = dedupe_across_years(df)
    assert len(out) == 3
    assert sorted(out["fiscal_year"]) == [2024, 2025, 2025]


def test_analytics_combined_membership():
    assert set(ANALYTICS_COMBINED) == {
        "Operations Research",
        "Statistics / Decision Science",
        "Data Science / BI",
        "Quant / Finance",
    }
    groups = analysis_groups(["Operations Research", "Supply Chain / Logistics"])
    assert groups["Operations Research"] == ["Operations Research"]
    assert groups[ANALYTICS_LABEL] == ANALYTICS_COMBINED


def test_family_trends_counts_certified_cases_by_year_with_rollup():
    parts = [
        make_rows(3, soc_family="Operations Research", fiscal_year=2024),
        make_rows(2, soc_family="Operations Research", fiscal_year=2025),
        make_rows(4, soc_family="Data Science / BI", fiscal_year=2025),
        make_rows(5, soc_family="Supply Chain / Logistics", fiscal_year=2024),
        make_rows(7, soc_family="Operations Research", fiscal_year=2025, CASE_STATUS="Withdrawn"),
        make_rows(9, soc_family="Other", fiscal_year=2025),
    ]
    out = family_trends(
        pd.concat(parts, ignore_index=True),
        analysis_groups(["Operations Research", "Data Science / BI", "Supply Chain / Logistics"]),
    )
    got = {(r.family, r.fiscal_year): r.cases for r in out.itertuples()}

    assert got[("Operations Research", 2024)] == 3
    assert got[("Operations Research", 2025)] == 2  # withdrawn rows are not counted
    assert got[("Data Science / BI", 2024)] == 0  # zero-filled for every loaded year
    assert got[("Supply Chain / Logistics", 2024)] == 5
    assert got[(ANALYTICS_LABEL, 2024)] == 3  # OR only
    assert got[(ANALYTICS_LABEL, 2025)] == 6  # OR 2 + DS 4
    assert not any(k[0] == "Other" for k in got)


def test_consistent_sponsors_need_min_cases_in_every_loaded_year():
    def emp(name, fam, n24, n25, status="Certified"):
        kw = dict(employer_norm=name, EMPLOYER_NAME=name, soc_family=fam, CASE_STATUS=status)
        return [make_rows(n24, fiscal_year=2024, **kw), make_rows(n25, fiscal_year=2025, **kw)]

    parts = (
        emp("STEADY", "Operations Research", 12, 15)
        + emp("FADING", "Operations Research", 12, 5)  # only 5 in 2025
        + emp("SPLIT", "Operations Research", 6, 6)  # 6 OR + 6 DS each year
        + emp("SPLIT", "Data Science / BI", 6, 6)
        + emp("WITHDRAWN", "Operations Research", 20, 20, status="Withdrawn")  # not certified
    )
    df = pd.concat(parts, ignore_index=True)
    groups = analysis_groups(["Operations Research", "Data Science / BI"])
    out = consistent_sponsors(df, groups, min_cases=10)

    def names(group):
        return out[out["group"] == group]["employer_norm"].tolist()

    assert names("Operations Research") == ["STEADY"]
    assert names("Data Science / BI") == []
    assert names(ANALYTICS_LABEL) == ["STEADY", "SPLIT"]  # rollup adds up SPLIT's 12 per year
    row = out[(out["group"] == "Operations Research")].iloc[0]
    assert (row["cases_fy2024"], row["cases_fy2025"], row["total_cases"]) == (12, 15, 27)
    assert list(out.columns) == [
        "group",
        "employer_norm",
        "employer_name",
        "cases_fy2024",
        "cases_fy2025",
        "total_cases",
    ]
