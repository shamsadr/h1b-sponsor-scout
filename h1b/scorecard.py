"""Employer-level scorecard metrics (each shown separately -- no black-box score)."""

import pandas as pd

from h1b.config import ANALYTICS_COMBINED, ANALYTICS_LABEL

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
    df: pd.DataFrame,
    families: list[str] | None = None,
    min_positions: int = 1,
    key: str = "parent_group",
) -> pd.DataFrame:
    """Aggregate cleaned LCA rows to one row per employer group.

    families: keep only these soc_family values (None = all).
    key: 'parent_group' (see h1b/groups.py) or 'employer_norm' (one row per name).
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
    denial = decided.assign(_den=denied).groupby(key)["_den"].mean()

    clean_wage = certified[certified["full_time"] & ~certified["wage_outlier"]]
    premium = clean_wage[clean_wage["wage_premium"].notna()]
    leveled = certified[certified["pw_level"].isin(LEVELS)]

    g = certified.groupby(key)
    card = pd.DataFrame(
        {
            "employer_name": g["EMPLOYER_NAME"].agg(_mode),
            "n_entities": g["employer_norm"].nunique(),
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
    card["median_wage_floor"] = clean_wage.groupby(key)["annual_wage"].median()
    # Medians of the premium collapse to 0 (many pay exactly the PW), so use a share.
    card["share_above_pw"] = (
        premium.assign(_above=premium["wage_premium"] > 0.01).groupby(key)["_above"].mean()
    )
    card["range_share"] = g["annual_wage_to"].agg(lambda s: s.notna().mean())
    card["n_leveled"] = leveled.groupby(key).size()
    card["n_leveled"] = card["n_leveled"].fillna(0).astype(int)
    card["level2plus_share"] = (
        leveled.assign(_hi=leveled["pw_level"] != "I").groupby(key)["_hi"].mean()
    )
    card["denial_rate"] = denial
    card["withdrawn_rate"] = withdrawn.groupby(d[key]).mean()
    # Flags are per-filing self-attestations, so report share/count, not a label.
    card["h1b_dependent_share"] = g["h1b_dependent"].mean()
    card["willful_violator_count"] = g["willful_violator"].sum()

    # Positions are worker counts requested per LCA, so a few bulk LCAs can dominate them.
    card["positions_per_case"] = card["positions"] / card["cases"]
    card["bulk_filer"] = card["positions_per_case"] > BULK_POSITIONS_PER_CASE

    card = card[card["positions"] >= min_positions]
    return card.sort_values(["cases", "new_hire_positions"], ascending=False).reset_index()


def family_scorecards(
    df: pd.DataFrame, families: list[str], top_n: int = 25, key: str = "parent_group"
) -> pd.DataFrame:
    """Top `top_n` employers by cases within each family, stacked with a 'family' column."""
    parts = []
    for fam in families:
        card = employer_scorecard(df, families=[fam], key=key).head(top_n)
        if not card.empty:
            parts.append(card.assign(family=fam))
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    return out[["family"] + [c for c in out.columns if c != "family"]]


def analysis_groups(families: list[str]) -> dict[str, list[str]]:
    """Each family on its own, plus the combined analytics rollup: {label: [soc_family, ...]}."""
    groups = {fam: [fam] for fam in families}
    groups[ANALYTICS_LABEL] = list(ANALYTICS_COMBINED)
    return groups


def family_trends(df: pd.DataFrame, groups: dict[str, list[str]]) -> pd.DataFrame:
    """Certified cases per group and fiscal year (long format: family, fiscal_year, cases).

    Expects one row per case (see dedupe_across_years). Every loaded year appears for every
    group, with 0 where there were no certified cases.
    """
    status = df["CASE_STATUS"].astype("string").str.strip()
    certified = df[status.eq("Certified").fillna(False)]
    years = sorted(df["fiscal_year"].unique().tolist())
    rows = []
    for name, fams in groups.items():
        counts = certified[certified["soc_family"].isin(fams)].groupby("fiscal_year").size()
        rows += [(name, year, int(counts.get(year, 0))) for year in years]
    return pd.DataFrame(rows, columns=["family", "fiscal_year", "cases"])


def consistent_sponsors(
    df: pd.DataFrame,
    groups: dict[str, list[str]],
    min_cases: int = 10,
    key: str = "parent_group",
) -> pd.DataFrame:
    """Employers with >= min_cases certified cases in EVERY loaded year, per group.

    Columns: group, <key>, employer_name, cases_fy{year}..., total_cases.
    """
    status = df["CASE_STATUS"].astype("string").str.strip()
    certified = df[status.eq("Certified").fillna(False)]
    years = sorted(df["fiscal_year"].unique().tolist())
    year_cols = [f"cases_fy{y}" for y in years]
    parts = []
    for name, fams in groups.items():
        c = certified[certified["soc_family"].isin(fams)]
        per_year = c.groupby([key, "fiscal_year"]).size().unstack(fill_value=0)
        per_year = per_year.reindex(columns=years, fill_value=0)
        keep = per_year[(per_year >= min_cases).all(axis=1)]
        if keep.empty:
            continue
        out = keep.set_axis(year_cols, axis=1)
        out["total_cases"] = out.sum(axis=1)
        out.insert(0, "employer_name", c.groupby(key)["EMPLOYER_NAME"].agg(_mode))
        out.insert(0, "group", name)
        parts.append(out.sort_values("total_cases", ascending=False).reset_index())
    columns = ["group", key, "employer_name"] + year_cols + ["total_cases"]
    if not parts:
        return pd.DataFrame(columns=columns)
    return pd.concat(parts, ignore_index=True)[columns]
