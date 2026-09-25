"""Project-wide constants: columns we keep, wage unit factors, SOC role families."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DEMO_DIR = ROOT / "data" / "demo"
REPORTS_DIR = ROOT / "reports"

# Columns the pipeline needs. Names are the *normalized* form
# (uppercase, non-alphanumerics -> "_"), e.g. "H-1B_DEPENDENT" -> "H_1B_DEPENDENT".
REQUIRED_COLS = [
    "CASE_NUMBER",
    "CASE_STATUS",
    "VISA_CLASS",
    "EMPLOYER_NAME",
    "SOC_CODE",
    "WAGE_RATE_OF_PAY_FROM",
    "WAGE_UNIT_OF_PAY",
]

# Nice-to-have columns: filled with NA if a given year's file lacks them
# (e.g. EMPLOYER_FEIN is absent from older LCA files).
OPTIONAL_COLS = [
    "DECISION_DATE",
    "JOB_TITLE",
    "SOC_TITLE",
    "FULL_TIME_POSITION",
    "TOTAL_WORKER_POSITIONS",
    "NEW_EMPLOYMENT",
    "CHANGE_EMPLOYER",
    "EMPLOYER_FEIN",
    "EMPLOYER_STATE",
    "WORKSITE_CITY",
    "WORKSITE_STATE",
    "PREVAILING_WAGE",
    "PW_UNIT_OF_PAY",
    "PW_WAGE_LEVEL",
    "H_1B_DEPENDENT",
    "WILLFUL_VIOLATOR",
]

# Older files may use different header names. Fill this in AFTER running
# `python -m h1b.pipeline inspect <file>` on each year -- don't guess.
# Format: {"OLD_NORMALIZED_NAME": "NEW_NORMALIZED_NAME"}
COLUMN_ALIASES: dict[str, str] = {}

# Multiply a wage by this factor to get an annual amount.
WAGE_UNIT_FACTORS = {
    "Hour": 2080,
    "Week": 52,
    "Bi-Weekly": 26,
    "Month": 12,
    "Year": 1,
}

# Plausible annual full-time wage range; outside -> flagged, not dropped.
WAGE_MIN, WAGE_MAX = 20_000, 1_000_000

# 2018 SOC codes -> role family. Exact detailed codes (with ".xx") are checked
# first, then the 7-char major code (e.g. "15-2031").
SOC_FAMILIES = {
    "15-2031": "Operations Research",
    "15-2041": "Statistics / Decision Science",
    "15-2011": "Statistics / Decision Science",
    "15-2051": "Data Science / BI",
    "13-2051": "Quant / Finance",
    "13-2054": "Quant / Finance",
    "13-2099.01": "Quant / Finance",
    "17-2112": "Industrial Engineering",
    "13-1081": "Industrial Engineering",
    "13-1111": "Business / Mgmt Analyst",
    "13-1161": "Business / Mgmt Analyst",
    "15-1211": "Business / Mgmt Analyst",
    "15-1252": "Software (context)",
}
TARGET_FAMILIES = sorted(set(SOC_FAMILIES.values()) - {"Software (context)"})
