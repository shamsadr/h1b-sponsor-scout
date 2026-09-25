import math

import pandas as pd
import pytest

from h1b.clean import annualize, clean_lca, map_soc_family, normalize_employer_name
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
