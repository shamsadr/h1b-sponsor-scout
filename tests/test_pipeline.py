"""End-to-end sanity check on the synthetic demo data."""

import pandas as pd

from h1b.config import DEMO_DIR
from h1b.pipeline import build_scorecard, group_by_fy, process_files


def test_demo_end_to_end(tmp_path):
    for fy in (2024, 2025):
        process_files([DEMO_DIR / f"lca_demo_FY{fy}.csv"], fy, out_dir=tmp_path)
    card = build_scorecard(processed_dir=tmp_path, reports_dir=tmp_path)

    assert (tmp_path / "scorecard_target_roles.csv").exists()
    assert 1 <= len(card) <= 5  # 5 fake employers in demo data
    assert card["positions"].gt(0).all()
    assert card["years_active"].between(1, 2).all()
    assert card["median_wage"].between(20_000, 1_000_000).all()  # outlier excluded
    assert card["level2plus_share"].dropna().between(0, 1).all()


def _write_lca_csv(path, cases):
    """Write a minimal LCA csv with the required columns; cases = [(case, decision_date)]."""
    rows = [
        {
            "CASE_NUMBER": c,
            "CASE_STATUS": "Certified",
            "DECISION_DATE": d,
            "VISA_CLASS": "H-1B",
            "EMPLOYER_NAME": "X Inc",
            "SOC_CODE": "15-2031.00",
            "WAGE_RATE_OF_PAY_FROM": "100000",
            "WAGE_UNIT_OF_PAY": "Year",
        }
        for c, d in cases
    ]
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_group_by_fy_uses_filename_or_override(tmp_path):
    a, b, c = (
        tmp_path / n for n in ("LCA_FY2024_Q4.csv", "LCA_FY2025_Q1.csv", "LCA_FY2025_Q2.csv")
    )
    assert group_by_fy([a, b, c]) == {2024: [a], 2025: [b, c]}
    assert group_by_fy([a, b], fy=2030) == {2030: [a, b]}


def test_process_files_merges_overlapping_quarters(tmp_path):
    q1 = _write_lca_csv(tmp_path / "LCA_FY2025_Q1.csv", [("A", "2024-11-01"), ("B", "2024-12-01")])
    q2 = _write_lca_csv(tmp_path / "LCA_FY2025_Q2.csv", [("B", "2025-01-15"), ("C", "2025-02-01")])
    out = process_files([q1, q2], 2025, out_dir=tmp_path)

    df = pd.read_parquet(out)
    assert out.name == "lca_fy2025.parquet"
    assert sorted(df["CASE_NUMBER"]) == ["A", "B", "C"]  # union, no duplicates
    b_date = df.loc[df["CASE_NUMBER"] == "B", "DECISION_DATE"].iloc[0]
    assert b_date == pd.Timestamp("2025-01-15")  # latest decision kept
