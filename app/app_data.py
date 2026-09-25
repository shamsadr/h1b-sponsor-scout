"""Data helpers for the Streamlit app: load the published tables, filter, search, README text.

Pure pandas (no Streamlit), so they can be unit-tested. The app reads only the small
files written by `python -m h1b.pipeline publish` (data/app/), never the raw data.
"""

import json
import os
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
STATE_ALL = "ALL"  # must match h1b/publish.py
ANALYTICS_LABEL = "Analytics (combined)"  # must match h1b/config.py
TABLES = ["sponsors", "employer_breakdown", "employer_levels", "members"]
SHARE_COLS = ["share_above_pw", "level2plus_share", "withdrawn_rate"]


def data_dir() -> Path:
    """data/app/, or the folder in $H1B_APP_DATA (tests point it at a demo publish)."""
    return Path(os.environ.get("H1B_APP_DATA", ROOT / "data" / "app"))


def load_tables(folder: Path) -> dict:
    """{'sponsors': df, ..., 'family_trends': df, 'meta': dict} from a publish folder."""
    tables: dict = {name: pd.read_parquet(folder / f"{name}.parquet") for name in TABLES}
    for name in TABLES:  # plain strings are simpler to filter than categoricals
        df = tables[name]
        for col in df.select_dtypes("category").columns:
            df[col] = df[col].astype(str)
    tables["family_trends"] = pd.read_csv(folder / "family_trends.csv")
    tables["meta"] = json.loads((folder / "meta.json").read_text())
    return tables


def years_label(years: list[int]) -> str:
    """[2024, 2025] -> 'FY2024–FY2025'; [2025] -> 'FY2025'."""
    years = sorted(years)
    if len(years) == 1:
        return f"FY{years[0]}"
    return f"FY{years[0]}–FY{years[-1]}"


def footer_text(meta: dict) -> str:
    """The source / caveat line shown at the bottom of every page."""
    return (
        f"Source: U.S. DOL OFLC LCA disclosure data, {years_label(meta['fiscal_years'])}. "
        "An LCA shows intent to hire, not a hire or visa approval. "
        "Not legal or immigration advice."
    )


def filter_sponsors(
    sponsors: pd.DataFrame,
    family: str,
    state: str = STATE_ALL,
    min_cases: int = 5,
    consistent_only: bool = False,
    n_years: int = 1,
) -> pd.DataFrame:
    """Ranked sponsors for one family group and state.

    consistent_only keeps groups with certified cases in every loaded year
    (years_active == n_years).
    """
    d = sponsors[(sponsors["family"] == family) & (sponsors["state"] == state)]
    d = d[d["cases"] >= min_cases]
    if consistent_only:
        d = d[d["years_active"] == n_years]
    d = d.sort_values(["cases", "parent_group"], ascending=[False, True])
    return d.drop(columns=["family", "state"]).reset_index(drop=True)


def as_percent(df: pd.DataFrame) -> pd.DataFrame:
    """Share columns (0-1) -> *_pct columns (0-100) for display and download."""
    out = df.copy()
    for col in SHARE_COLS:
        if col in out.columns:
            out[col] = out[col] * 100
    return out.rename(
        columns={c: c.replace("share", "pct").replace("rate", "pct") for c in SHARE_COLS}
    )


def search_groups(members: pd.DataFrame, query: str, limit: int = 50) -> list[str]:
    """Groups whose label or any member name contains `query` (case-insensitive).

    Largest groups first, so 'MERRILL' finds BANK OF AMERICA through its member names.
    """
    q = query.strip().upper()
    if not q:
        return []
    hit = members["parent_group"].str.upper().str.contains(q, regex=False) | members[
        "employer_norm"
    ].str.contains(q, regex=False)
    sizes = members[hit].groupby("parent_group")["rows"].sum()
    top = sizes.reset_index().sort_values(["rows", "parent_group"], ascending=[False, True])
    return top["parent_group"].head(limit).tolist()


def readme_sections(headings: list[str], text: str | None = None) -> dict[str, str]:
    """{heading: markdown body} for '## heading' sections of the README.

    Raises KeyError if a heading is missing, so renaming one breaks a test, not the app.
    """
    text = README.read_text() if text is None else text
    parts = re.split(r"^## +(.+?)\s*$", text, flags=re.M)
    found = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    missing = [h for h in headings if h not in found]
    if missing:
        raise KeyError(f"README sections not found: {missing}")
    return {h: found[h] for h in headings}


def readme_bullet(bold_start: str, text: str | None = None) -> str:
    """The README bullet that starts with '- **<bold_start>', joined into one paragraph."""
    text = README.read_text() if text is None else text
    pattern = rf"^- \*\*{re.escape(bold_start)}.*?(?=^- |^#|\Z)"
    m = re.search(pattern, text, flags=re.M | re.S)
    if not m:
        raise KeyError(f"README bullet not found: {bold_start}")
    return " ".join(m.group(0)[2:].split())
