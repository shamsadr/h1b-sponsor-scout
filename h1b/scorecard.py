"""Employer-level scorecard metrics (each shown separately -- no black-box score)."""

import pandas as pd

LEVELS = {"I", "II", "III", "IV"}


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
            "top_state": g["WORKSITE_STATE"].agg(_mode),
        }
    )
    card["median_wage"] = clean_wage.groupby("employer_norm")["annual_wage"].median()
    card["median_wage_premium"] = clean_wage.groupby("employer_norm")["wage_premium"].median()
    card["level2plus_share"] = (
        leveled.assign(_hi=leveled["pw_level"] != "I").groupby("employer_norm")["_hi"].mean()
    )
    card["denial_rate"] = denial
    card["withdrawn_rate"] = withdrawn.groupby(d["employer_norm"]).mean()
    # Flags are per-filing self-attestations, so report share/count, not a label.
    card["h1b_dependent_share"] = g["h1b_dependent"].mean()
    card["willful_violator_count"] = g["willful_violator"].sum()

    card = card[card["positions"] >= min_positions]
    return card.sort_values(["positions", "years_active"], ascending=False).reset_index()
