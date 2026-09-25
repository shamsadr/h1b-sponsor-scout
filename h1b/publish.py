"""Publish slim, precomputed tables for the Streamlit app (data/app/).

The app only reads these files, so every number it shows comes from the same
scorecard functions as the CLI reports.
"""

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from h1b.config import (
    ALL_OCCUPATIONS_LABEL,
    ALL_TARGET_LABEL,
    MAX_APP_MB,
    ROOT,
    TARGET_FAMILIES,
)
from h1b.groups import load_overrides, override_display_names, usable_feins
from h1b.scorecard import LEVELS, analysis_groups, employer_scorecard, family_trends

STATE_ALL = "ALL"  # the 'all states' row in sponsors.parquet
NOT_LEVELED = "Not leveled"
LEVEL_ORDER = ["I", "II", "III", "IV", NOT_LEVELED]

# Cases first among the numbers, so the app table leads with them. One cases_fy{year}
# column per loaded year follows "cases" (see sponsor_columns).
SPONSOR_COLS = [
    "family",
    "state",
    "parent_group",
    "display_name",
    "cases",
    "years_active",
    "median_wage_floor",
    "share_above_pw",
    "level2plus_share",
    "n_leveled",
    "withdrawn_rate",
    "positions",
    "n_entities",
    "n_feins",
    "top_soc_title",
    "top_state",
]
BREAKDOWN_COLS = ["parent_group", "fiscal_year", "soc_family", "cases", "filings", "withdrawn"]
LEVEL_COLS = ["parent_group", "soc_family", "level", "cases"]
MEMBER_COLS = ["parent_group", "employer_norm", "primary_fein", "primary_state", "rows", "link"]
GROUP_COLS = ["parent_group", "display_name", "rows", "n_names", "primary_state"]
TREND_COLS = ["family", "fiscal_year", "cases"]


def _status(df: pd.DataFrame) -> pd.Series:
    return df["CASE_STATUS"].astype("string").str.strip()


def app_family_groups(all_families: list[str]) -> dict[str, list[str]]:
    """Role groups offered in the app: each target family, the analytics rollup,
    all target roles, and all occupations (every soc_family, including 'Other')."""
    groups = analysis_groups(TARGET_FAMILIES)
    groups[ALL_TARGET_LABEL] = list(TARGET_FAMILIES)
    groups[ALL_OCCUPATIONS_LABEL] = sorted(all_families)
    return groups


def sponsor_columns(years: list[int]) -> list[str]:
    """SPONSOR_COLS with one cases_fy{year} column per loaded year right after 'cases'."""
    i = SPONSOR_COLS.index("cases") + 1
    return SPONSOR_COLS[:i] + [f"cases_fy{y}" for y in years] + SPONSOR_COLS[i:]


def _per_group_extras(certified: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """Certified cases per fiscal year, and distinct usable filing FEINs, per group."""
    per_year = certified.groupby(["parent_group", "fiscal_year"]).size().unstack(fill_value=0)
    per_year = per_year.reindex(columns=years, fill_value=0)
    per_year.columns = [f"cases_fy{y}" for y in years]
    feins = usable_feins(certified["EMPLOYER_FEIN"]).groupby(certified["parent_group"]).nunique()
    return per_year.assign(n_feins=feins)


def sponsors_table(
    df: pd.DataFrame, groups: dict[str, list[str]], names: pd.Series | None = None
) -> pd.DataFrame:
    """Scorecard for every family group x worksite state (plus STATE_ALL).

    names: parent_group -> display_name (see display_names); defaults to the group key.
    """
    years = sorted(int(y) for y in df["fiscal_year"].unique())
    certified_all = df[_status(df).eq("Certified").fillna(False)]
    parts = []
    for name, fams in groups.items():
        d = df[df["soc_family"].isin(fams)]
        c = certified_all[certified_all["soc_family"].isin(fams)]
        states = sorted(d["WORKSITE_STATE"].dropna().astype(str).str.strip().unique())
        for state in [STATE_ALL] + [s for s in states if s]:
            rows = d if state == STATE_ALL else d[d["WORKSITE_STATE"].astype(str) == state]
            card = employer_scorecard(rows)
            if card.empty:
                continue
            cert = c if state == STATE_ALL else c[c["WORKSITE_STATE"].astype(str) == state]
            card = card.join(_per_group_extras(cert, years), on="parent_group")
            parts.append(card.assign(family=name, state=state))
    out = pd.concat(parts, ignore_index=True)
    shown = names if names is not None else pd.Series(dtype="object")
    out["display_name"] = out["parent_group"].map(shown).fillna(out["parent_group"])
    out = out[sponsor_columns(years)]
    out = out.sort_values(
        ["family", "state", "cases", "parent_group"], ascending=[True, True, False, True]
    )
    return out.reset_index(drop=True)


def employer_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Certified cases, all filings and withdrawals per group, fiscal year and family."""
    status = _status(df)
    d = df.assign(
        _cert=status.eq("Certified").fillna(False),
        _wd=status.isin({"Withdrawn", "Certified - Withdrawn"}).fillna(False),
    )
    g = d.groupby(["parent_group", "fiscal_year", "soc_family"])
    out = g.agg(cases=("_cert", "sum"), filings=("_cert", "size"), withdrawn=("_wd", "sum"))
    return out.reset_index()[BREAKDOWN_COLS]


def employer_levels(df: pd.DataFrame) -> pd.DataFrame:
    """Certified cases per group, family and wage level (I-IV or 'Not leveled')."""
    c = df[_status(df).eq("Certified").fillna(False)]
    level = c["pw_level"].astype("string").where(c["pw_level"].isin(LEVELS), NOT_LEVELED)
    out = c.assign(level=level).groupby(["parent_group", "soc_family", "level"]).size()
    return out.rename("cases").reset_index()[LEVEL_COLS]


def _name_key(name: str) -> str:
    """Case- and punctuation-insensitive form, for spotting look-alike names."""
    return re.sub(r"[^a-z0-9]", "", name.casefold())


# Legal suffixes stripped from the END of a filed name, for display only. Each may follow a
# comma and end with a period: 'Tiger Analytics, Inc.' -> 'Tiger Analytics'.
LEGAL_SUFFIXES = [
    r"Inc",
    r"Incorporated",
    r"L\.?L\.?C",
    r"L\.?L\.?P",
    r"L\.?P",
    r"Ltd",
    r"Limited",
    r"Corp",
    r"Corporation",
    r"P\.?L\.?L\.?C",
    r"P\.?C",
    r"N\.?A",
    r"&\s*Co",
]
_SUFFIX_RE = re.compile(r"[\s,]+(?:" + "|".join(LEGAL_SUFFIXES) + r")\.?\s*$", re.IGNORECASE)


def strip_legal_suffix(name: str) -> str:
    """'Goldman Sachs & Co. LLC' -> 'Goldman Sachs'. Repeats while a suffix ends the name;
    keeps the name unchanged if stripping would leave nothing. Casing is never changed."""
    out = name.strip()
    while True:
        shorter = _SUFFIX_RE.sub("", out).rstrip(" ,")
        if shorter == out or not shorter:
            return out
        out = shorter


def is_all_caps(name: str) -> bool:
    """True when a name has letters and none of them is lowercase ('KFORCE INC.')."""
    return any(c.isalpha() for c in name) and not any(c.islower() for c in name)


def display_names(
    df: pd.DataFrame, parent_groups: pd.DataFrame, labels: dict[str, str]
) -> pd.DataFrame:
    """One unique display name per parent_group.

    1. The override display_name for that group's label (labels: {parent_group: name}).
    2. Otherwise the most frequent raw EMPLOYER_NAME as filed that is not all caps (ties:
       alphabetical), or the most frequent all-caps name if that is all there is. Names are
       never re-cased, so 'IBM' and 'EY' stay as filed. Trailing legal suffixes are stripped
       for display (strip_legal_suffix).
    Look-alike names (same letters and digits, ignoring case and punctuation) are made
    unique: override names and then larger groups keep the plain name; later ones get
    ' (ST)', then ' (ST, FEIN)', then ' [parent_group]'.
    Columns: GROUP_COLS.
    """
    raw = df["EMPLOYER_NAME"].astype("string").str.strip()
    counts = (
        pd.DataFrame({"parent_group": df["parent_group"], "name": raw})
        .dropna()
        .groupby(["parent_group", "name"])
        .size()
        .rename("n")
        .reset_index()
    )
    counts["caps"] = counts["name"].map(is_all_caps)
    counts = (
        counts.sort_values(
            ["parent_group", "caps", "n", "name"], ascending=[True, True, False, True]
        )
        .drop_duplicates("parent_group")
        .set_index("parent_group")["name"]
        .map(strip_legal_suffix)
    )
    g = parent_groups.sort_values(["rows", "employer_norm"], ascending=[False, True])
    lead = g.drop_duplicates("parent_group").set_index("parent_group")
    out = pd.DataFrame(
        {
            "rows": parent_groups.groupby("parent_group")["rows"].sum(),
            "n_names": parent_groups.groupby("parent_group").size(),
        }
    )
    out["primary_state"] = lead["primary_state"]
    out["primary_fein"] = lead["primary_fein"]
    out["is_override"] = out.index.isin(list(labels))
    base = pd.Series(labels).reindex(out.index)
    out["base"] = base.fillna(counts.reindex(out.index)).fillna(pd.Series(out.index, out.index))
    out = out.reset_index(names="parent_group").sort_values(
        ["is_override", "rows", "parent_group"], ascending=[False, False, True]
    )
    used: set[str] = set()
    names = []
    for r in out.itertuples():
        state = r.primary_state if isinstance(r.primary_state, str) else None
        fein = r.primary_fein if isinstance(r.primary_fein, str) else None
        tries = [r.base]
        if state:
            tries.append(f"{r.base} ({state})")
            if fein:
                tries.append(f"{r.base} ({state}, {fein})")
        tries.append(f"{r.base} [{r.parent_group}]")
        name = next(t for t in tries if _name_key(t) not in used) if not r.is_override else r.base
        used.add(_name_key(name))
        names.append(name)
    out["display_name"] = names
    return out.sort_values("parent_group")[GROUP_COLS].reset_index(drop=True)


def _git_commit() -> str:
    """Short commit hash of the code that built the data, '-dirty' if it had local edits."""
    try:
        out = subprocess.run(
            ["git", "describe", "--always", "--dirty"], cwd=ROOT, capture_output=True, text=True
        )
        return out.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def _sha256(path: Path | None) -> str | None:
    if path is None or not Path(path).exists():
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _slim(df: pd.DataFrame, categories: list[str]) -> pd.DataFrame:
    """Categorical text columns keep the parquet files small."""
    return df.astype({c: "category" for c in categories})


def publish_app_data(
    df: pd.DataFrame,
    parent_groups: pd.DataFrame,
    groups: dict[str, list[str]],
    out_dir: Path,
    overrides_path: Path | None = None,
    max_mb: float = MAX_APP_MB,
) -> dict[str, Path]:
    """Write the app tables to out_dir and return {name: path}.

    df: deduped LCA rows with parent_group, all families.
    groups: role groups for the sponsor tables, e.g. app_family_groups(...).
    Trends cover the target families and the analytics rollup only. The lookup tables
    (groups, breakdown, levels, members) cover every group, so any sponsor row can be
    opened in Employer lookup. Raises ValueError if the files add up to more than max_mb.
    """
    target = df[df["soc_family"].isin(TARGET_FAMILIES)]
    labels = override_display_names(load_overrides(overrides_path))
    group_table = display_names(df, parent_groups, labels)
    names = group_table.set_index("parent_group")["display_name"]
    sponsors = sponsors_table(df, groups, names)
    cats = ["family", "state", "parent_group", "display_name", "top_soc_title"]
    tables = {
        "sponsors.parquet": _slim(sponsors, cats),
        "groups.parquet": group_table,
        "employer_breakdown.parquet": _slim(employer_breakdown(df), ["parent_group"]),
        "employer_levels.parquet": _slim(employer_levels(df), ["parent_group"]),
        "members.parquet": parent_groups[MEMBER_COLS].reset_index(drop=True),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, table in tables.items():
        paths[name] = out_dir / name
        table.to_parquet(paths[name], index=False, compression="zstd")
    paths["family_trends.csv"] = out_dir / "family_trends.csv"
    trends = family_trends(df, analysis_groups(TARGET_FAMILIES))[TREND_COLS]
    trends.to_csv(paths["family_trends.csv"], index=False)
    meta = {
        "fiscal_years": sorted(int(y) for y in df["fiscal_year"].unique()),
        "built_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "git_commit": _git_commit(),
        "source_rows": int(len(df)),
        "target_rows": int(len(target)),
        "n_names": int(len(parent_groups)),
        "n_groups": int(parent_groups["parent_group"].nunique()),
        "overrides_sha256": _sha256(overrides_path),
    }
    paths["meta.json"] = out_dir / "meta.json"
    paths["meta.json"].write_text(json.dumps(meta, indent=2) + "\n")

    total_mb = sum(p.stat().st_size for p in paths.values()) / 1e6
    if total_mb > max_mb:
        raise ValueError(f"App data is {total_mb:.1f} MB, over the {max_mb} MB limit")
    print(f"[ok] app data: {total_mb:.2f} MB -> {out_dir}")
    return paths
