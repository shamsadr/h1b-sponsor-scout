import math

import pandas as pd
import pytest

from h1b.clean import annualize, clean_lca, map_soc_family, normalize_employer_name
from h1b.config import SOC_FAMILIES, TARGET_FAMILIES
from h1b.ingest import standardize_columns


def test_annualize_units():
    amt = pd.Series(["50", "$90,000.00", "4000", "100", "abc"])
    unit = pd.Series(["Hour", "Year", "Month", "Parsec", "Year"])
    out = annualize(amt, unit)
    assert out[0] == 104_000
    assert out[1] == 90_000
    assert out[2] == 48_000
    assert math.isnan(out[3]) and math.isnan(out[4])  # bad unit / bad number


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Deloitte Consulting, L.L.C.", "DELOITTE CONSULTING"),
        ("Acme Analytics, Inc.", "ACME ANALYTICS"),
        ("The Boeing Company", "BOEING"),
        (None, ""),
    ],
)
def test_normalize_employer_name(raw, expected):
    assert normalize_employer_name(raw) == expected


def test_map_soc_family():
    assert map_soc_family("15-2031.00") == "Operations Research"
    assert map_soc_family("13-2099.01") == "Quant / Finance"
    assert map_soc_family("13-2099.00") == "Other"
    assert map_soc_family(None) == "Other"


def test_missing_required_column_raises():
    with pytest.raises(ValueError, match="Missing required"):
        standardize_columns(pd.DataFrame({"CASE_NUMBER": ["1"]}))


def test_clean_dedupes_and_filters_visa():
    raw = pd.DataFrame(
        {
            "CASE_NUMBER": ["A", "A", "B"],
            "CASE_STATUS": ["Certified", "Certified - Withdrawn", "Certified"],
            "DECISION_DATE": ["2025-01-01", "2025-02-01", "2025-01-01"],
            "VISA_CLASS": ["H-1B", "H-1B", "E-3 Australian"],
            "EMPLOYER_NAME": ["X Inc", "X Inc", "Y"],
            "SOC_CODE": ["15-2031.00"] * 3,
            "WAGE_RATE_OF_PAY_FROM": ["100000"] * 3,
            "WAGE_UNIT_OF_PAY": ["Year"] * 3,
        }
    )
    std, _ = standardize_columns(raw)
    out = clean_lca(std, 2025)
    assert len(out) == 1  # A deduped, B dropped (not H-1B)
    assert out.loc[0, "CASE_STATUS"] == "Certified - Withdrawn"  # latest kept
    assert out.loc[0, "employer_norm"] == "X"


def test_clean_annualizes_wage_to():
    raw = pd.DataFrame(
        {
            "CASE_NUMBER": ["A", "B"],
            "CASE_STATUS": ["Certified"] * 2,
            "DECISION_DATE": ["2025-01-01"] * 2,
            "VISA_CLASS": ["H-1B"] * 2,
            "EMPLOYER_NAME": ["X"] * 2,
            "SOC_CODE": ["15-2031.00"] * 2,
            "WAGE_RATE_OF_PAY_FROM": ["50", "100000"],
            "WAGE_RATE_OF_PAY_TO": ["60", None],
            "WAGE_UNIT_OF_PAY": ["Hour", "Year"],
        }
    )
    std, _ = standardize_columns(raw)
    out = clean_lca(std, 2025).set_index("CASE_NUMBER")
    assert out.loc["A", "annual_wage_to"] == 60 * 2080
    assert math.isnan(out.loc["B", "annual_wage_to"])  # blank TO stays NaN


def test_families_split_it_analysts_and_supply_chain():
    assert map_soc_family("15-1211.00") == "IT Systems Analyst (context)"
    assert map_soc_family("13-1081.02") == "Supply Chain / Logistics"
    assert map_soc_family("17-2112.00") == "Industrial Engineering"


def test_target_families_exclude_context_families():
    assert "Supply Chain / Logistics" in TARGET_FAMILIES
    assert "Industrial Engineering" in TARGET_FAMILIES
    assert not [f for f in TARGET_FAMILIES if f.endswith("(context)")]
    assert {"Software (context)", "IT Systems Analyst (context)"} <= set(SOC_FAMILIES.values())


@pytest.mark.parametrize(
    "code, family",
    [
        ("17-2112.00", "Industrial Engineering"),
        ("17-2112.01", "Industrial Engineering"),
        ("17-2112.03", "Industrial Engineering"),
        ("17-2112", "Industrial Engineering"),  # some filings omit the detail suffix
        ("17-2112.02", "Validation Eng (context)"),
    ],
)
def test_17_2112_detail_codes(code, family):
    assert map_soc_family(code) == family


def test_validation_eng_is_context_not_target():
    assert "Validation Eng (context)" in SOC_FAMILIES.values()
    assert "Validation Eng (context)" not in TARGET_FAMILIES


@pytest.mark.parametrize("code", ["11-3071", "11-3071.00", "11-3071.04", "13-1081.02"])
def test_supply_chain_codes(code):
    assert map_soc_family(code) == "Supply Chain / Logistics"
