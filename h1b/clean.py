"""Cleaning: dedupe, filter to H-1B, annualize wages, normalize employers, map SOCs."""

import re

import pandas as pd

from h1b.config import SOC_FAMILIES, WAGE_MAX, WAGE_MIN, WAGE_UNIT_FACTORS

_SUFFIXES = re.compile(
    r"\b(INC|INCORPORATED|L L C|LLC|LLP|LP|LTD|LIMITED|CORP|CORPORATION|"
    r"CO|COMPANY|PLLC|PC|THE)\b"
)


def normalize_employer_name(name) -> str:
    """'Deloitte Consulting, L.L.C.' -> 'DELOITTE CONSULTING'."""
    if name is None or pd.isna(name):
        return ""
    s = str(name).upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = _SUFFIXES.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def to_number(s: pd.Series) -> pd.Series:
    """'$85,000.00' -> 85000.0; junk -> NaN."""
    cleaned = s.astype("string").str.replace(r"[$,\s]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce").astype("float64")  # plain NaN, not pd.NA


def annualize(amount: pd.Series, unit: pd.Series) -> pd.Series:
    """Convert wage amounts to annual using the unit column (Hour/Week/...)."""
    factor = unit.astype("string").str.strip().str.title().map(WAGE_UNIT_FACTORS)
    return to_number(amount) * pd.to_numeric(factor, errors="coerce").astype("float64")


def map_soc_family(code) -> str:
    """'15-2031.00' -> 'Operations Research'; unknown -> 'Other'."""
    if code is None or pd.isna(code):
        return "Other"
    c = str(code).strip()
    return SOC_FAMILIES.get(c, SOC_FAMILIES.get(c[:7], "Other"))


def _flag(s: pd.Series) -> pd.Series:
    """'Y'/'Yes'/'1' -> True, else False."""
    return s.astype("string").str.strip().str.upper().isin({"Y", "YES", "1"}).fillna(False)


def clean_lca(df: pd.DataFrame, fiscal_year: int) -> pd.DataFrame:
    """Turn standardized raw LCA rows into an analysis-ready table."""
    if df.empty:
        raise ValueError("Input DataFrame is empty")
    out = df.copy()

    # 1) Dedupe: keep the latest decision per case (quarterly files overlap).
    out["DECISION_DATE"] = pd.to_datetime(out["DECISION_DATE"], errors="coerce")
    out = out.sort_values("DECISION_DATE").drop_duplicates("CASE_NUMBER", keep="last")

    # 2) H-1B only (drops E-3 and H-1B1).
    out = out[out["VISA_CLASS"].astype("string").str.strip() == "H-1B"].copy()

    # 3) Wages.
    out["annual_wage"] = annualize(out["WAGE_RATE_OF_PAY_FROM"], out["WAGE_UNIT_OF_PAY"])
    out["annual_wage_to"] = annualize(out["WAGE_RATE_OF_PAY_TO"], out["WAGE_UNIT_OF_PAY"])
    out["annual_pw"] = annualize(out["PREVAILING_WAGE"], out["PW_UNIT_OF_PAY"])
    out["wage_premium"] = out["annual_wage"] / out["annual_pw"] - 1
    out["full_time"] = _flag(out["FULL_TIME_POSITION"])
    out["wage_outlier"] = ~out["annual_wage"].between(WAGE_MIN, WAGE_MAX)

    # 4) Counts and hiring signal.
    out["positions"] = to_number(out["TOTAL_WORKER_POSITIONS"]).fillna(1).clip(lower=1)
    new = to_number(out["NEW_EMPLOYMENT"]).fillna(0) + to_number(out["CHANGE_EMPLOYER"]).fillna(0)
    out["new_hire_positions"] = new

    # 5) Labels.
    out["employer_norm"] = out["EMPLOYER_NAME"].map(normalize_employer_name)
    out["soc_family"] = out["SOC_CODE"].map(map_soc_family)
    out["pw_level"] = out["PW_WAGE_LEVEL"].astype("string").str.strip().str.upper()
    out["h1b_dependent"] = _flag(out["H_1B_DEPENDENT"])
    out["willful_violator"] = _flag(out["WILLFUL_VIOLATOR"])
    out["fiscal_year"] = int(fiscal_year)
    return out.reset_index(drop=True)
