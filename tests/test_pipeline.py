"""End-to-end sanity check on the synthetic demo data."""

from h1b.config import DEMO_DIR
from h1b.pipeline import build_scorecard, process_file


def test_demo_end_to_end(tmp_path):
    for fy in (2024, 2025):
        process_file(DEMO_DIR / f"lca_demo_FY{fy}.csv", fy, out_dir=tmp_path)
    card = build_scorecard(processed_dir=tmp_path, reports_dir=tmp_path)

    assert (tmp_path / "scorecard_target_roles.csv").exists()
    assert 1 <= len(card) <= 5  # 5 fake employers in demo data
    assert card["positions"].gt(0).all()
    assert card["years_active"].between(1, 2).all()
    assert card["median_wage"].between(20_000, 1_000_000).all()  # outlier excluded
    assert card["level2plus_share"].dropna().between(0, 1).all()
