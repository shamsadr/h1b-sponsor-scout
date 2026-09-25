import pandas as pd

from h1b.scorecard import employer_scorecard


def make_rows(n: int = 1, **overrides) -> pd.DataFrame:
    """n cleaned-looking LCA rows for one employer; override any column (scalar or list)."""
    base = {
        "CASE_STATUS": "Certified",
        "EMPLOYER_NAME": "X Inc",
        "employer_norm": "X",
        "positions": 1.0,
        "new_hire_positions": 0.0,
        "fiscal_year": 2025,
        "soc_family": "Operations Research",
        "WORKSITE_STATE": "TX",
        "full_time": True,
        "wage_outlier": False,
        "annual_wage": 100_000.0,
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
    assert row["median_wage"] == 110_000  # withdrawn/denied wages ignored
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
