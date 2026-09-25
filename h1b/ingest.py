"""Read raw DOL LCA files (xlsx or csv) into a DataFrame with standardized columns."""

import re
from pathlib import Path

import pandas as pd

from h1b.config import COLUMN_ALIASES, OPTIONAL_COLS, REQUIRED_COLS


def normalize_col(name: str) -> str:
    """'H-1B_DEPENDENT ' -> 'H_1B_DEPENDENT'."""
    return re.sub(r"[^A-Z0-9]+", "_", str(name).strip().upper()).strip("_")


def read_raw(path: str | Path, nrows: int | None = None) -> pd.DataFrame:
    """Read an LCA file as all-string columns (we cast types ourselves later)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str, nrows=nrows, engine="openpyxl")
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str, nrows=nrows)
    raise ValueError(f"Unsupported file type '{suffix}' (use .xlsx or .csv)")


def standardize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Normalize headers, apply aliases, keep only needed columns.

    Returns (df, missing_optional_cols). Raises ValueError if required columns
    are missing, listing what *is* present so you can add an alias.
    """
    df = df.rename(columns=normalize_col).rename(columns=COLUMN_ALIASES)
    missing_req = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing_req:
        raise ValueError(
            f"Missing required columns {missing_req}. "
            f"Columns present: {sorted(df.columns)}. "
            "Add a mapping to COLUMN_ALIASES in h1b/config.py."
        )
    missing_opt = [c for c in OPTIONAL_COLS if c not in df.columns]
    for c in missing_opt:
        df[c] = pd.NA
    return df[REQUIRED_COLS + OPTIONAL_COLS].copy(), missing_opt


def ingest(path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    """Read + standardize one raw file."""
    return standardize_columns(read_raw(path))
