"""The publish step: schema and consistency of the files the Streamlit app reads."""

import json

import pandas as pd
import pytest

from h1b.config import (
    ALL_OCCUPATIONS_LABEL,
    ALL_TARGET_LABEL,
    DEMO_DIR,
    MAX_APP_MB,
    ROOT,
    TARGET_FAMILIES,
)
from h1b.pipeline import load_grouped, process_files, publish
from h1b.publish import (
    BREAKDOWN_COLS,
    GROUP_COLS,
    LEVEL_COLS,
    LEVEL_ORDER,
    MEMBER_COLS,
    STATE_ALL,
    TREND_COLS,
    display_names,
    publish_app_data,
    sponsor_columns,
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
        "sponsors.parquet": sponsor_columns([2024, 2025]),
        "groups.parquet": GROUP_COLS,
        "employer_breakdown.parquet": BREAKDOWN_COLS,
        "employer_levels.parquet": LEVEL_COLS,
        "members.parquet": MEMBER_COLS,
        "family_trends.csv": TREND_COLS,
    }
    for name, cols in expected.items():
        assert list(read(published, name).columns) == cols, name
    sponsors = read(published, "sponsors.parquet")
    assert sponsors.columns[4] == "cases"  # first numeric column, after display_name
    for col in ["cases", "cases_fy2024", "cases_fy2025", "years_active", "n_leveled", "n_feins"]:
        assert pd.api.types.is_integer_dtype(sponsors[col]), col
    assert set(read(published, "employer_levels.parquet")["level"]) <= set(LEVEL_ORDER)


def test_sponsors_one_row_per_family_state_group_with_all_states(published):
    sponsors = read(published, "sponsors.parquet")
    assert not sponsors.duplicated(["family", "state", "parent_group"]).any()
    families = set(analysis_groups(TARGET_FAMILIES)) | {ALL_TARGET_LABEL, ALL_OCCUPATIONS_LABEL}
    assert set(sponsors["family"]) <= families
    assert {ALL_TARGET_LABEL, ALL_OCCUPATIONS_LABEL} <= set(sponsors["family"])
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
    for fam, cases in from_trends.items():  # trends cover target families + analytics
        assert cases == from_sponsors.get(fam, 0), fam
    breakdown = read(published, "employer_breakdown.parquet")
    by_family = breakdown.groupby("soc_family")["cases"].sum()
    for fam in TARGET_FAMILIES:
        if fam in from_sponsors.index:
            assert by_family[fam] == from_sponsors[fam], fam
    members = read(published, "members.parquet")
    groups = read(published, "groups.parquet")
    assert set(sponsors["parent_group"]) <= set(members["parent_group"])  # any row can be opened
    assert set(sponsors["parent_group"]) <= set(groups["parent_group"])
    assert set(breakdown["parent_group"]) == set(groups["parent_group"])


def test_per_year_cases_add_up_and_broad_families_contain_the_narrow_ones(published):
    sponsors = read(published, "sponsors.parquet")
    assert (sponsors["cases_fy2024"] + sponsors["cases_fy2025"] == sponsors["cases"]).all()
    all_states = sponsors[sponsors["state"] == STATE_ALL]
    by = all_states.pivot_table(
        index="parent_group", columns="family", values="cases", aggfunc="sum", observed=True
    ).fillna(0)
    targets = [f for f in TARGET_FAMILIES if f in by.columns]
    assert (by[targets].sum(axis=1) == by[ALL_TARGET_LABEL]).all()
    assert (by[ALL_OCCUPATIONS_LABEL] >= by[ALL_TARGET_LABEL]).all()
    assert (all_states["n_feins"] >= 1).all()  # demo rows all carry a usable FEIN


def test_display_names_are_unique_and_follow_the_rules():
    df = pd.DataFrame(
        {
            "parent_group": ["AMAZON"] * 3 + ["IBM"] * 2 + ["ACME A", "ACME B", "ACME B"],
            "EMPLOYER_NAME": [
                "Amazon.com Services LLC",
                "Amazon.com Services LLC",
                "Amazon Web Services, Inc.",
                "IBM Corporation",
                "IBM Corporation",
                "Acme, LLC",
                "ACME LLC",
                "ACME LLC",
            ],
        }
    )
    parent_groups = pd.DataFrame(
        {
            "parent_group": ["AMAZON", "IBM", "ACME A", "ACME B"],
            "employer_norm": ["AMAZON COM SERVICES", "IBM", "ACME A", "ACME B"],
            "primary_fein": ["11-1111111", "22-2222222", "33-3333333", "44-4444444"],
            "primary_state": ["WA", "NY", "AZ", "TX"],
            "rows": [3, 2, 1, 2],
        }
    )
    out = display_names(df, parent_groups, {"AMAZON": "Amazon"}).set_index("parent_group")
    assert list(out.columns) == GROUP_COLS[1:]
    assert out.loc["AMAZON", "display_name"] == "Amazon"  # override label wins
    assert out.loc["IBM", "display_name"] == "IBM Corporation"  # raw name, not 'Ibm Corporation'
    assert out.loc["ACME B", "display_name"] == "ACME LLC"  # larger look-alike keeps it
    assert out.loc["ACME A", "display_name"] == "Acme, LLC (AZ)"
    assert out["display_name"].is_unique


def test_raw_name_that_matches_an_override_name_gets_a_suffix():
    df = pd.DataFrame(
        {"parent_group": ["CITI", "CITI (56-1928771)"], "EMPLOYER_NAME": ["Citibank", "CITI"]}
    )
    parent_groups = pd.DataFrame(
        {
            "parent_group": ["CITI", "CITI (56-1928771)"],
            "employer_norm": ["CITIBANK N A", "CITI"],
            "primary_fein": ["13-5266470", "56-1928771"],
            "primary_state": ["NY", "NC"],
            "rows": [1, 9],  # the look-alike is bigger, but the override name still wins
        }
    )
    out = display_names(df, parent_groups, {"CITI": "Citi"}).set_index("parent_group")
    assert out.loc["CITI", "display_name"] == "Citi"
    assert out.loc["CITI (56-1928771)", "display_name"] == "CITI (NC)"


def test_meta_json(published):
    meta = json.loads((published / "meta.json").read_text())
    assert meta["fiscal_years"] == [2024, 2025]
    keys = {"built_at", "git_commit", "source_rows", "target_rows", "overrides_sha256"}
    assert keys | {"n_names", "n_groups"} <= set(meta)
    assert meta["target_rows"] <= meta["source_rows"]
    assert meta["n_groups"] <= meta["n_names"]


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
        "groups.parquet",
        "employer_breakdown.parquet",
        "employer_levels.parquet",
        "members.parquet",
        "family_trends.csv",
        "meta.json",
    ]
    assert sum((folder / n).stat().st_size for n in names) / 1e6 < MAX_APP_MB
    years = json.loads((folder / "meta.json").read_text())["fiscal_years"]
    assert list(read(folder, "sponsors.parquet").columns) == sponsor_columns(years)
    assert list(read(folder, "members.parquet").columns) == MEMBER_COLS
    assert read(folder, "groups.parquet")["display_name"].is_unique
