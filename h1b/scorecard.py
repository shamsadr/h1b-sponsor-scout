"""Employer-level scorecard metrics (each shown separately -- no black-box score)."""

import pandas as pd

LEVELS = {"I", "II", "III", "IV"}
BULK_POSITIONS_PER_CASE = 5  # above this many positions per case -> bulk_filer


def dedupe_across_years(df: pd.DataFrame) -> pd.DataFrame:
    """One row per CASE_NUMBER across all loaded years.

    Keeps the record with the latest DECISION_DATE (so a later withdrawal replaces the
    original certification) but assigns the earliest fiscal_year the case appears in.
    """
    df = df.reset_index(drop=True)
    first_year = df.groupby("CASE_NUMBER")["fiscal_year"].transform("min")
    latest = (
        df.sort_values(["DECISION_DATE", "fiscal_year"], na_position="first")
        .drop_duplicates("CASE_NUMBER", keep="last")
        .sort_index()
    )
    latest["fiscal_year"] = first_year.loc[latest.index]
    return latest.reset_index(drop=True)


def _mode(s: pd.Series):
    s = s.dropna()
    return s.value_counts().idxmax() if len(s) else pd.NA


def employer_scorecard(
    df: pd.DataFrame, families: list[str] | None = None, min_positions: int = 1
) -> pd.DataFrame:
    """Aggregate cleaned LCA rows to one row per normalized employer.

    families: keep only these soc_family values (None = all).
    """
    d = df if families is None else df[df["soc_family"].isin(families)]
    if d.empty:
        return pd.DataFrame()

    status = d["CASE_STATUS"].astype("string").str.strip()
    certified = d[status.eq("Certified").fillna(False)]  # excludes 'Certified - Withdrawn'
    denied = status.eq("Denied").fillna(False)
    withdrawn = status.isin({"Withdrawn", "Certified - Withdrawn"})

    # Denial rate uses all decided cases (certified + denied).
    decided = d[status.str.startswith("Certified").fillna(False) | denied]
    denial = decided.assign(_den=denied).groupby("employer_norm")["_den"].mean()

    clean_wage = certified[certified["full_time"] & ~certified["wage_outlier"]]
    premium = clean_wage[clean_wage["wage_premium"].notna()]
    leveled = certified[certified["pw_level"].isin(LEVELS)]

    g = certified.groupby("employer_norm")
    card = pd.DataFrame(
        {
            "employer_name": g["EMPLOYER_NAME"].agg(_mode),
            "cases": g.size(),
            "positions": g["positions"].sum(),
            "new_hire_positions": g["new_hire_positions"].sum(),
            "years_active": g["fiscal_year"].nunique(),
            "top_family": g["soc_family"].agg(_mode),
            "top_soc_title": g["SOC_TITLE"].agg(_mode),
            "top_state": g["WORKSITE_STATE"].agg(_mode),
        }
    )
    # FROM is the pay floor; TO is only filled by some employers (see range_share).
    card["median_wage_floor"] = clean_wage.groupby("employer_norm")["annual_wage"].median()
    # Medians of the premium collapse to 0 (many pay exactly the PW), so use a share.
    card["share_above_pw"] = (
        premium.assign(_above=premium["wage_premium"] > 0.01)
        .groupby("employer_norm")["_above"]
        .mean()
    )
    card["range_share"] = g["annual_wage_to"].agg(lambda s: s.notna().mean())
    card["n_leveled"] = leveled.groupby("employer_norm").size()
    card["n_leveled"] = card["n_leveled"].fillna(0).astype(int)
    card["level2plus_share"] = (
        leveled.assign(_hi=leveled["pw_level"] != "I").groupby("employer_norm")["_hi"].mean()
    )
    card["denial_rate"] = denial
    card["withdrawn_rate"] = withdrawn.groupby(d["employer_norm"]).mean()
    # Flags are per-filing self-attestations, so report share/count, not a label.
    card["h1b_dependent_share"] = g["h1b_dependent"].mean()
    card["willful_violator_count"] = g["willful_violator"].sum()

    # Positions are worker counts requested per LCA, so a few bulk LCAs can dominate them.
    card["positions_per_case"] = card["positions"] / card["cases"]
    card["bulk_filer"] = card["positions_per_case"] > BULK_POSITIONS_PER_CASE

    card = card[card["positions"] >= min_positions]
    return card.sort_values(["cases", "new_hire_positions"], ascending=False).reset_index()


def family_scorecards(df: pd.DataFrame, families: list[str], top_n: int = 25) -> pd.DataFrame:
    """Top `top_n` employers by cases within each family, stacked with a 'family' column."""
    parts = []
    for fam in families:
        card = employer_scorecard(df, families=[fam]).head(top_n)
        if not card.empty:
            parts.append(card.assign(family=fam))
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    return out[["family"] + [c for c in out.columns if c != "family"]]
