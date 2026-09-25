"""End-to-end sanity check on the synthetic demo data."""

import pandas as pd
import pytest

from h1b.config import DEMO_DIR
from h1b.pipeline import build_scorecard, clean_interim, group_by_fy, process_files


def test_demo_end_to_end(tmp_path):
    for fy in (2024, 2025):
        process_files(
            [DEMO_DIR / f"lca_demo_FY{fy}.csv"],
            fy,
            out_dir=tmp_path,
            interim_dir=tmp_path / "interim",
        )
    card = build_scorecard(processed_dir=tmp_path, reports_dir=tmp_path)

    assert (tmp_path / "scorecard_target_roles.csv").exists()
    by_family = pd.read_csv(tmp_path / "scorecard_by_family.csv")
    assert by_family.columns[0] == "family" and len(by_family) > 0
    assert 1 <= len(card) <= 5  # 5 fake employers in demo data
    assert card["positions"].gt(0).all()
    assert card["years_active"].between(1, 2).all()
    assert card["median_wage_floor"].between(20_000, 1_000_000).all()  # outlier excluded
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
    out = process_files([q1, q2], 2025, out_dir=tmp_path, interim_dir=tmp_path / "interim")

    df = pd.read_parquet(out)
    assert out.name == "lca_fy2025.parquet"
    assert sorted(df["CASE_NUMBER"]) == ["A", "B", "C"]  # union, no duplicates
    b_date = df.loc[df["CASE_NUMBER"] == "B", "DECISION_DATE"].iloc[0]
    assert b_date == pd.Timestamp("2025-01-15")  # latest decision kept


def test_run_writes_uncleaned_interim_then_clean_rebuilds_from_it(tmp_path):
    q1 = _write_lca_csv(tmp_path / "LCA_FY2025_Q1.csv", [("A", "2024-11-01"), ("B", "2024-12-01")])
    q2 = _write_lca_csv(tmp_path / "LCA_FY2025_Q2.csv", [("B", "2025-01-15"), ("C", "2025-02-01")])
    interim, processed = tmp_path / "interim", tmp_path / "processed"
    process_files([q1, q2], 2025, out_dir=processed, interim_dir=interim)

    raw = pd.read_parquet(interim / "lca_raw_fy2025.parquet")
    assert len(raw) == 4  # standardized but NOT deduped (B appears twice)
    assert "annual_wage" not in raw.columns  # no cleaning columns yet

    q1.unlink(), q2.unlink()  # clean must not need the source files
    (processed / "lca_fy2025.parquet").unlink()
    out = clean_interim(interim, processed)
    assert [p.name for p in out] == ["lca_fy2025.parquet"]
    assert sorted(pd.read_parquet(out[0])["CASE_NUMBER"]) == ["A", "B", "C"]


def test_clean_twice_gives_identical_output(tmp_path):
    src = _write_lca_csv(tmp_path / "LCA_FY2025_Q1.csv", [("A", "2024-11-01"), ("B", "2024-12-01")])
    interim, processed = tmp_path / "interim", tmp_path / "processed"
    process_files([src], 2025, out_dir=processed, interim_dir=interim)

    first = pd.read_parquet(clean_interim(interim, processed)[0])
    second = pd.read_parquet(clean_interim(interim, processed)[0])
    pd.testing.assert_frame_equal(first, second)


def test_clean_interim_errors_when_no_interim_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="interim"):
        clean_interim(tmp_path / "interim", tmp_path / "processed")


def test_build_scorecard_dedupes_cases_across_years(tmp_path):
    fy24 = _write_lca_csv(
        tmp_path / "LCA_FY2024_Q1.csv", [("A", "2024-03-01"), ("B", "2024-04-01")]
    )
    fy25 = _write_lca_csv(
        tmp_path / "LCA_FY2025_Q1.csv", [("A", "2025-01-10"), ("C", "2025-02-01")]
    )
    pd.read_csv(fy25).assign(CASE_STATUS=["Certified - Withdrawn", "Certified"]).to_csv(
        fy25, index=False
    )
    processed = tmp_path / "processed"
    process_files([fy24], 2024, out_dir=processed, interim_dir=tmp_path / "i")
    process_files([fy25], 2025, out_dir=processed, interim_dir=tmp_path / "i")

    card = build_scorecard(processed_dir=processed, reports_dir=tmp_path / "r", families=None)
    row = card.iloc[0]
    assert row["cases"] == 2  # B (FY24) and C (FY25); A is now withdrawn
    assert row["withdrawn_rate"] == 1 / 3  # A counted once
