"""CLI entry point.

python -m h1b.pipeline inspect data/raw/<file>.xlsx
python -m h1b.pipeline run --input data/raw/<file>.xlsx --fy 2025
python -m h1b.pipeline run --demo
python -m h1b.pipeline clean [--fy 2025]     # rebuild data/processed from data/interim
python -m h1b.pipeline scorecard
"""

import argparse
import re
from pathlib import Path

import pandas as pd

from h1b.clean import clean_lca
from h1b.config import DEMO_DIR, INTERIM_DIR, PROCESSED_DIR, REPORTS_DIR, TARGET_FAMILIES
from h1b.ingest import ingest, normalize_col, read_raw
from h1b.scorecard import employer_scorecard, family_scorecards


def inspect_file(path: Path) -> list[str]:
    """Print normalized headers of a raw file (first 5 rows read)."""
    cols = [normalize_col(c) for c in read_raw(path, nrows=5).columns]
    print(f"{path.name}: {len(cols)} columns")
    for c in cols:
        print("  ", c)
    return cols


def write_interim(paths: list[Path], fy: int, interim_dir: Path = INTERIM_DIR) -> Path:
    """Raw file(s) for ONE fiscal year -> one standardized, uncleaned interim parquet.

    Headers are normalized and only the needed columns kept, but nothing is deduped
    or cast, so `clean` can be re-run without re-reading the slow xlsx files.
    """
    frames = []
    for path in paths:
        raw, missing = ingest(path)
        if missing:
            print(f"[warn] {path.name}: optional columns missing -> NA: {missing}")
        frames.append(raw)
    combined = pd.concat(frames, ignore_index=True)
    interim_dir.mkdir(parents=True, exist_ok=True)
    out = interim_dir / f"lca_raw_fy{fy}.parquet"
    combined.to_parquet(out, index=False)
    names = ", ".join(p.name for p in paths)
    print(f"[ok] interim FY{fy} ({names}): {len(combined):,} rows -> {out}")
    return out


def clean_interim(
    interim_dir: Path = INTERIM_DIR, out_dir: Path = PROCESSED_DIR, fy: int | None = None
) -> list[Path]:
    """Interim parquet(s) -> cleaned lca_fy{fy}.parquet in out_dir (all years, or one `fy`).

    Cases repeated across quarterly files are deduped on CASE_NUMBER (latest decision kept).
    """
    pattern = f"lca_raw_fy{fy}.parquet" if fy else "lca_raw_fy*.parquet"
    files = sorted(interim_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No interim files matching {pattern} in {interim_dir}. Run `run`.")
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for f in files:
        year = int(re.search(r"fy(\d{4})", f.name).group(1))
        raw = pd.read_parquet(f)
        df = clean_lca(raw, year)
        out = out_dir / f"lca_fy{year}.parquet"
        df.to_parquet(out, index=False)
        print(f"[ok] clean FY{year}: {len(raw):,} interim rows -> {len(df):,} H-1B rows -> {out}")
        outputs.append(out)
    return outputs


def process_files(
    paths: list[Path],
    fy: int,
    out_dir: Path = PROCESSED_DIR,
    interim_dir: Path = INTERIM_DIR,
) -> Path:
    """Raw file(s) for ONE fiscal year -> interim parquet -> cleaned parquet. Returns the latter."""
    write_interim(paths, fy, interim_dir)
    return clean_interim(interim_dir, out_dir, fy=fy)[0]


def build_scorecard(
    processed_dir: Path = PROCESSED_DIR,
    reports_dir: Path = REPORTS_DIR,
    families: list[str] | None = TARGET_FAMILIES,
) -> pd.DataFrame:
    """Combine all processed years; write the target-role and per-family scorecard CSVs."""
    files = sorted(processed_dir.glob("lca_fy*.parquet"))
    if not files:
        raise FileNotFoundError(f"No processed files in {processed_dir}. Run `run` first.")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    card = employer_scorecard(df, families=families)
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / "scorecard_target_roles.csv"
    card.to_csv(out, index=False)
    by_family = family_scorecards(df, families if families is not None else TARGET_FAMILIES)
    by_family.to_csv(reports_dir / "scorecard_by_family.csv", index=False)
    years = sorted(df["fiscal_year"].unique().tolist())
    print(f"[ok] scorecard: {len(card):,} employers, FY {years} -> {out}")
    cols = [
        "employer_name",
        "cases",
        "new_hire_positions",
        "positions_per_case",
        "median_wage_floor",
    ]
    print(card[cols].head(10).to_string(index=False))
    return card


def _fy_from_name(path: Path) -> int:
    m = re.search(r"FY(\d{4})", path.name, flags=re.I)
    if not m:
        raise ValueError(f"Can't infer fiscal year from '{path.name}'; pass --fy")
    return int(m.group(1))


def group_by_fy(paths: list[Path], fy: int | None = None) -> dict[int, list[Path]]:
    """Group input files by fiscal year (from filenames, or all under `fy` if given)."""
    groups: dict[int, list[Path]] = {}
    for path in paths:
        groups.setdefault(fy or _fy_from_name(path), []).append(path)
    return groups


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="h1b")
    sub = p.add_subparsers(dest="cmd", required=True)
    s_insp = sub.add_parser("inspect", help="print a raw file's headers")
    s_insp.add_argument("path", type=Path)
    s_run = sub.add_parser("run", help="clean raw file(s) to parquet, then scorecard")
    s_run.add_argument("--input", type=Path, nargs="*", default=[])
    s_run.add_argument("--fy", type=int, help="fiscal year (default: parsed from filename)")
    s_run.add_argument("--demo", action="store_true", help="use synthetic demo data")
    s_clean = sub.add_parser("clean", help="rebuild processed parquet from interim (no xlsx)")
    s_clean.add_argument("--fy", type=int, help="only this fiscal year (default: all)")
    s_clean.add_argument("--demo", action="store_true", help="use the demo folders")
    sub.add_parser("scorecard", help="rebuild scorecard from processed parquet")
    args = p.parse_args(argv)

    if args.cmd == "inspect":
        inspect_file(args.path)
    elif args.cmd == "run":
        inputs = sorted(DEMO_DIR.glob("lca_demo_FY*.csv")) if args.demo else args.input
        if not inputs:
            p.error("give --input FILE(s) or --demo")
        # Demo outputs go to separate folders so they never mix with real data.
        proc = PROCESSED_DIR / "demo" if args.demo else PROCESSED_DIR
        interim = INTERIM_DIR / "demo" if args.demo else INTERIM_DIR
        rep = REPORTS_DIR / "demo" if args.demo else REPORTS_DIR
        for year, files in sorted(group_by_fy(inputs, args.fy).items()):
            process_files(files, year, out_dir=proc, interim_dir=interim)
        build_scorecard(processed_dir=proc, reports_dir=rep)
    elif args.cmd == "clean":
        proc = PROCESSED_DIR / "demo" if args.demo else PROCESSED_DIR
        interim = INTERIM_DIR / "demo" if args.demo else INTERIM_DIR
        clean_interim(interim, proc, fy=args.fy)
    else:
        build_scorecard()


if __name__ == "__main__":
    main()
