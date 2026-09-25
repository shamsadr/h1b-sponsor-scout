"""Publish slim, precomputed tables for the Streamlit app (data/app/).

The app only reads these files, so every number it shows comes from the same
scorecard functions as the CLI reports.
"""

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from h1b.config import MAX_APP_MB, ROOT
from h1b.scorecard import LEVELS, employer_scorecard, family_trends

STATE_ALL = "ALL"  # the 'all states' row in sponsors.parquet
NOT_LEVELED = "Not leveled"
LEVEL_ORDER = ["I", "II", "III", "IV", NOT_LEVELED]

# Cases first among the numbers, so the app table leads with them.
SPONSOR_COLS = [
    "family",
    "state",
    "parent_group",
    "cases",
    "years_active",
    "median_wage_floor",
    "share_above_pw",
    "level2plus_share",
    "n_leveled",
    "withdrawn_rate",
    "positions",
    "n_entities",
    "top_soc_title",
    "top_state",
]
BREAKDOWN_COLS = ["parent_group", "fiscal_year", "soc_family", "cases", "filings", "withdrawn"]
LEVEL_COLS = ["parent_group", "soc_family", "level", "cases"]
MEMBER_COLS = ["parent_group", "employer_norm", "primary_fein", "primary_state", "rows", "link"]
TREND_COLS = ["family", "fiscal_year", "cases"]


def _status(df: pd.DataFrame) -> pd.Series:
    return df["CASE_STATUS"].astype("string").str.strip()


def sponsors_table(df: pd.DataFrame, groups: dict[str, list[str]]) -> pd.DataFrame:
    """Scorecard for every family group x worksite state (plus STATE_ALL)."""
    parts = []
    for name, fams in groups.items():
        d = df[df["soc_family"].isin(fams)]
        states = sorted(d["WORKSITE_STATE"].dropna().astype(str).str.strip().unique())
        for state in [STATE_ALL] + [s for s in states if s]:
            rows = d if state == STATE_ALL else d[d["WORKSITE_STATE"].astype(str) == state]
            card = employer_scorecard(rows)
            if not card.empty:
                parts.append(card.assign(family=name, state=state))
    out = pd.concat(parts, ignore_index=True)[SPONSOR_COLS]
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

    df: deduped LCA rows with parent_group (all families; filtered to `groups` here).
    groups: {label: [soc_family, ...]}, e.g. analysis_groups(TARGET_FAMILIES).
    Raises ValueError if the files add up to more than max_mb.
    """
    families = sorted({f for fams in groups.values() for f in fams})
    target = df[df["soc_family"].isin(families)]
    sponsors = sponsors_table(target, groups)
    members = parent_groups[parent_groups["parent_group"].isin(sponsors["parent_group"])]
    tables = {
        "sponsors.parquet": _slim(sponsors, ["family", "state", "parent_group", "top_soc_title"]),
        "employer_breakdown.parquet": _slim(employer_breakdown(target), ["parent_group"]),
        "employer_levels.parquet": _slim(employer_levels(target), ["parent_group"]),
        "members.parquet": members[MEMBER_COLS].reset_index(drop=True),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, table in tables.items():
        paths[name] = out_dir / name
        table.to_parquet(paths[name], index=False, compression="zstd")
    paths["family_trends.csv"] = out_dir / "family_trends.csv"
    family_trends(df, groups)[TREND_COLS].to_csv(paths["family_trends.csv"], index=False)
    meta = {
        "fiscal_years": sorted(int(y) for y in df["fiscal_year"].unique()),
        "built_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "git_commit": _git_commit(),
        "source_rows": int(len(df)),
        "target_rows": int(len(target)),
        "overrides_sha256": _sha256(overrides_path),
    }
    paths["meta.json"] = out_dir / "meta.json"
    paths["meta.json"].write_text(json.dumps(meta, indent=2) + "\n")

    total_mb = sum(p.stat().st_size for p in paths.values()) / 1e6
    if total_mb > max_mb:
        raise ValueError(f"App data is {total_mb:.1f} MB, over the {max_mb} MB limit")
    print(f"[ok] app data: {total_mb:.2f} MB -> {out_dir}")
    return paths
