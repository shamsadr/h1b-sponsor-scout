import pandas as pd

from h1b.scorecard import employer_scorecard


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
