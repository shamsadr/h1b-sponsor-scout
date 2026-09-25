"""Project-wide constants: columns we keep, wage unit factors, SOC role families."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
INTERIM_DIR = ROOT / "data" / "interim"
PROCESSED_DIR = ROOT / "data" / "processed"
DEMO_DIR = ROOT / "data" / "demo"
REPORTS_DIR = ROOT / "reports"
REFERENCE_DIR = ROOT / "data" / "reference"  # small hand-made files, committed to git
OVERRIDES_FILE = REFERENCE_DIR / "employer_overrides.csv"
APP_DIR = ROOT / "data" / "app"  # slim precomputed tables for the Streamlit app, committed
MAX_APP_MB = 20  # publish fails if data/app/ would be bigger than this

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
    "WAGE_RATE_OF_PAY_TO",
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
    "17-2112": "Industrial Engineering",  # .00 IE, .01 Human Factors, .03 Manufacturing
    "17-2112.02": "Validation Eng (context)",
    "13-1081": "Supply Chain / Logistics",
    "11-3071": "Supply Chain / Logistics",
    "13-1111": "Business / Mgmt Analyst",
    "13-1161": "Business / Mgmt Analyst",
    "15-1211": "IT Systems Analyst (context)",
    "15-1252": "Software (context)",
}
# Families tagged "(context)" are kept for comparison but are not target roles.
TARGET_FAMILIES = sorted(f for f in set(SOC_FAMILIES.values()) if not f.endswith("(context)"))

# Rollup of the analytics-flavored target families, reported alongside each family.
ANALYTICS_LABEL = "Analytics (combined)"
# Broader views offered in the app (h1b/publish.py): every target family, and every family.
ALL_TARGET_LABEL = "All target roles"
ALL_OCCUPATIONS_LABEL = "All occupations"
ANALYTICS_COMBINED = [
    "Operations Research",
    "Statistics / Decision Science",
    "Data Science / BI",
    "Quant / Finance",
]

# Parent-company grouping (h1b/groups.py).
# FEINs used as placeholders on filings for unrelated employers: never link on them.
PLACEHOLDER_FEINS = {"12-3456789"}
FEIN_PATTERN = r"^\d{2}-\d{7}$"  # anything else (e.g. '1231231231') is ignored
# Don't link on a FEIN whose names form more than this many unrelated clusters
# (state university systems, law-firm FEINs typed on client filings).
MAX_UNRELATED_PER_FEIN = 2
NAME_SIMILARITY = 0.85  # difflib ratio at or above which two names count as related
# Dropped from employer_norm when building the name key used for name edges.
GENERIC_NAME_TOKENS = {"US", "USA", "AMERICA", "AMERICAS", "NA", "SERVICES", "GROUP", "HOLDINGS"}
# No name edge for short/generic keys ('GLOBAL SERVICES' -> 'GLOBAL').
MIN_NAME_KEY_TOKENS, MIN_NAME_KEY_CHARS = 2, 6

# Merge review (reports/merge_review.csv): warning signals for members of a group.
NAME_SIM_WARN = 0.5  # difflib ratio to the group label below this -> flag
# Last word of a name that looks like a job title ('SYSTEMS ANALYST') ...
TITLE_WORDS = {
    "ANALYST",
    "ENGINEER",
    "DEVELOPER",
    "PROGRAMMER",
    "SCIENTIST",
    "ARCHITECT",
    "ADMINISTRATOR",
    "SPECIALIST",
    "MANAGER",
    "ACCOUNTANT",
}
# ... or a person with a professional suffix ('JOHN SMITH MD').
PERSON_SUFFIXES = {"MD", "DDS", "DMD", "DVM", "CPA", "ESQ", "PHD"}
