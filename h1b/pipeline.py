"""CLI entry point.

python -m h1b.pipeline inspect data/raw/<file>.xlsx
python -m h1b.pipeline run --input data/raw/<file>.xlsx --fy 2025
python -m h1b.pipeline run --demo
python -m h1b.pipeline clean [--fy 2025]     # rebuild data/processed from data/interim
python -m h1b.pipeline scorecard
python -m h1b.pipeline publish [--demo]     # slim tables for the Streamlit app -> data/app/
"""

import argparse
import re
from pathlib import Path

import pandas as pd

from h1b.clean import clean_lca
from h1b.config import (
    APP_DIR,
    DEMO_DIR,
    INTERIM_DIR,
    OVERRIDES_FILE,
    PROCESSED_DIR,
    REPORTS_DIR,
    TARGET_FAMILIES,
)
from h1b.groups import add_parent_group, build_parent_groups, load_overrides, merge_review
from h1b.ingest import ingest, normalize_col, read_raw
from h1b.publish import app_family_groups, publish_app_data
from h1b.scorecard import (
    analysis_groups,
    consistent_sponsors,
    dedupe_across_years,
    employer_scorecard,
    family_scorecards,
    family_trends,
)


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


def load_grouped(
    processed_dir: Path, overrides_path: Path | None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """All processed years, deduped across years, with a parent_group column.

    Returns (rows, parent_groups). Groups use every row of every year, so they don't
    depend on any family filter.
    """
    files = sorted(processed_dir.glob("lca_fy*.parquet"))
    if not files:
        raise FileNotFoundError(f"No processed files in {processed_dir}. Run `run` first.")
    df = dedupe_across_years(pd.concat([pd.read_parquet(f) for f in files], ignore_index=True))
    parent_groups = build_parent_groups(df, load_overrides(overrides_path))
    return add_parent_group(df, parent_groups), parent_groups


def publish(
    processed_dir: Path = PROCESSED_DIR,
    out_dir: Path = APP_DIR,
    overrides_path: Path | None = OVERRIDES_FILE,
) -> dict[str, Path]:
    """Processed parquet -> slim precomputed tables for the Streamlit app."""
    df, parent_groups = load_grouped(processed_dir, overrides_path)
    groups = app_family_groups(sorted(df["soc_family"].unique()))
    return publish_app_data(df, parent_groups, groups, out_dir, overrides_path)


def build_scorecard(
    processed_dir: Path = PROCESSED_DIR,
    reports_dir: Path = REPORTS_DIR,
    families: list[str] | None = TARGET_FAMILIES,
    overrides_path: Path | None = OVERRIDES_FILE,
) -> pd.DataFrame:
    """Combine all processed years, group employers, and write the report CSVs."""
    df, parent_groups = load_grouped(processed_dir, overrides_path)
    reports_dir.mkdir(parents=True, exist_ok=True)
    parent_groups.to_csv(reports_dir / "parent_groups.csv", index=False)
    review = merge_review(parent_groups)
    review.to_csv(reports_dir / "merge_review.csv", index=False)
    card = employer_scorecard(df, families=families)
    out = reports_dir / "scorecard_target_roles.csv"
    card.to_csv(out, index=False)
    by_family = family_scorecards(df, families if families is not None else TARGET_FAMILIES)
    by_family.to_csv(reports_dir / "scorecard_by_family.csv", index=False)
    groups = analysis_groups(families if families is not None else TARGET_FAMILIES)
    family_trends(df, groups).to_csv(reports_dir / "family_trends.csv", index=False)
    sponsors = consistent_sponsors(df, groups)
    sponsors.to_csv(reports_dir / "consistent_sponsors.csv", index=False)
    years = sorted(df["fiscal_year"].unique().tolist())
    n_names, n_groups = len(parent_groups), parent_groups["parent_group"].nunique()
    print(f"[ok] parent groups: {n_names:,} employer names -> {n_groups:,} groups")
    print_merge_review(review)
    print(f"[ok] scorecard: {len(card):,} employer groups, FY {years} -> {out}")
    cols = [
        "parent_group",
        "n_entities",
        "cases",
        "new_hire_positions",
        "positions_per_case",
        "median_wage_floor",
    ]
    print(card[cols].head(10).to_string(index=False))
    return card


def print_merge_review(review: pd.DataFrame, top_n: int = 25) -> None:
    """Print the group members with the most warning signals (for review by eye)."""
    flagged = int(review["risk_flags"].gt(0).sum())
    print(
        f"[review] {len(review):,} members of multi-name groups, {flagged:,} with a warning "
        f"(reports/merge_review.csv); top {top_n}:"
    )
    cols = ["parent_group", "employer_norm", "rows", "primary_fein", "primary_state", "link"]
    cols += ["name_sim", "state_mismatch", "looks_like_person_or_title", "risk_flags"]
    print(review[cols].head(top_n).to_string(index=False))


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
    s_pub = sub.add_parser("publish", help="write slim app tables to data/app/")
    s_pub.add_argument("--demo", action="store_true", help="use demo data -> data/app/demo/")
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
    elif args.cmd == "publish":
        if args.demo:
            publish(PROCESSED_DIR / "demo", APP_DIR / "demo")
        else:
            publish()
    else:
        build_scorecard()


if __name__ == "__main__":
    main()
