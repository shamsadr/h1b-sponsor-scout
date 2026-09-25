"""The publish step: schema and consistency of the files the Streamlit app reads."""

import json

import pandas as pd
import pytest

from h1b.config import DEMO_DIR, MAX_APP_MB, ROOT, TARGET_FAMILIES
from h1b.pipeline import load_grouped, process_files, publish
from h1b.publish import (
    BREAKDOWN_COLS,
    LEVEL_COLS,
    LEVEL_ORDER,
    MEMBER_COLS,
    SPONSOR_COLS,
    STATE_ALL,
    TREND_COLS,
    publish_app_data,
)
from h1b.scorecard import analysis_groups


@pytest.fixture(scope="module")
def demo_processed(tmp_path_factory):
    out = tmp_path_factory.mktemp("processed")
    for fy in (2024, 2025):
        process_files([DEMO_DIR / f"lca_demo_FY{fy}.csv"], fy, out_dir=out, interim_dir=out / "i")
    return out


@pytest.fixture(scope="module")
def published(demo_processed, tmp_path_factory):
    out = tmp_path_factory.mktemp("app")
    publish(processed_dir=demo_processed, out_dir=out)
    return out


def read(folder, name):
    path = folder / name
    return pd.read_csv(path) if name.endswith(".csv") else pd.read_parquet(path)


def test_publish_writes_expected_columns(published):
    expected = {
        "sponsors.parquet": SPONSOR_COLS,
        "employer_breakdown.parquet": BREAKDOWN_COLS,
        "employer_levels.parquet": LEVEL_COLS,
        "members.parquet": MEMBER_COLS,
        "family_trends.csv": TREND_COLS,
    }
    for name, cols in expected.items():
        assert list(read(published, name).columns) == cols, name
    sponsors = read(published, "sponsors.parquet")
    assert sponsors.columns[3] == "cases"  # first numeric column
    for col in ["cases", "years_active", "n_leveled", "n_entities"]:
        assert pd.api.types.is_integer_dtype(sponsors[col]), col
    assert set(read(published, "employer_levels.parquet")["level"]) <= set(LEVEL_ORDER)


def test_sponsors_one_row_per_family_state_group_with_all_states(published):
    sponsors = read(published, "sponsors.parquet")
    assert not sponsors.duplicated(["family", "state", "parent_group"]).any()
    families = set(analysis_groups(TARGET_FAMILIES))
    assert set(sponsors["family"]) <= families
    for fam, d in sponsors.groupby("family", observed=True):
        assert STATE_ALL in set(d["state"]), fam
        per_state = d[d["state"] != STATE_ALL].groupby("parent_group", observed=True)["cases"]
        all_states = d[d["state"] == STATE_ALL].set_index("parent_group")["cases"]
        assert (per_state.sum() == all_states.reindex(per_state.sum().index)).all()


def test_published_totals_agree_across_files(published):
    sponsors = read(published, "sponsors.parquet")
    all_rows = sponsors[sponsors["state"] == STATE_ALL]
    from_sponsors = all_rows.groupby("family", observed=True)["cases"].sum()
    from_trends = read(published, "family_trends.csv").groupby("family")["cases"].sum()
    for fam, cases in from_sponsors.items():
        assert cases == from_trends[fam], fam
    breakdown = read(published, "employer_breakdown.parquet")
    by_family = breakdown.groupby("soc_family")["cases"].sum()
    for fam in TARGET_FAMILIES:
        if fam in from_sponsors.index:
            assert by_family[fam] == from_sponsors[fam], fam
    members = read(published, "members.parquet")
    assert set(sponsors["parent_group"]) <= set(members["parent_group"])


def test_meta_json(published):
    meta = json.loads((published / "meta.json").read_text())
    assert meta["fiscal_years"] == [2024, 2025]
    assert {"built_at", "git_commit", "source_rows", "target_rows", "overrides_sha256"} <= set(meta)
    assert meta["target_rows"] <= meta["source_rows"]


def test_publish_refuses_oversized_output(demo_processed, tmp_path):
    df, parent_groups = load_grouped(demo_processed, None)
    with pytest.raises(ValueError, match="MB"):
        publish_app_data(
            df, parent_groups, analysis_groups(TARGET_FAMILIES), tmp_path, max_mb=0.0001
        )


def test_committed_app_data_is_small_and_matches_schema():
    folder = ROOT / "data" / "app"
    if not (folder / "meta.json").exists():
        pytest.skip("data/app/ not published yet")
    names = [
        "sponsors.parquet",
        "employer_breakdown.parquet",
        "employer_levels.parquet",
        "members.parquet",
        "family_trends.csv",
        "meta.json",
    ]
    assert sum((folder / n).stat().st_size for n in names) / 1e6 < MAX_APP_MB
    assert list(read(folder, "sponsors.parquet").columns) == SPONSOR_COLS
    assert list(read(folder, "members.parquet").columns) == MEMBER_COLS
