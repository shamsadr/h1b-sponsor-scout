# CLAUDE.md — H-1B Sponsor Scout

## What this project is
Pipeline over public DOL LCA disclosure data (FY2019–present) that ranks employers
sponsoring H-1B in OR / Data-BI / Quant / IE / Business-Analyst roles.
Flow: `h1b/ingest.py` → `data/interim` → `h1b/clean.py` → `data/processed` → `h1b/scorecard.py`,
CLI in `h1b/pipeline.py` (`run` reads xlsx; `clean` and `scorecard` re-run from parquet).

## Owner context
Grad student, coding-rusty. Explain changes briefly (what + why) and keep code simple,
modular, with type hints and docstrings. Offer Option A (simple) vs Option B (scalable)
when there's a real tradeoff.

## Environment
- macOS Apple Silicon, venv `.venv` (`requirements.txt`), Python 3.11+ (developed on 3.14)
- Setup: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run from repo root: `python -m h1b.pipeline ...`

## Rules
- NEVER guess dataset column names. Run `python -m h1b.pipeline inspect <file>` and use
  the real headers. Put renames in `COLUMN_ALIASES` in `h1b/config.py`.
- NEVER read raw .xlsx files into context directly; they are ~80 MB. Inspect via the CLI
  or query parquet with pandas/DuckDB and print summaries.
- NEVER commit anything in `data/raw/`, `data/interim/` or `data/processed/`.
- Don't invent statistics or findings. README results come only from actual runs.
- Ask before adding new dependencies; update `requirements.txt` if approved.
- Make small changes; one phase or feature per commit.

## Definition of done (every change)
1. `pytest -q` passes, and new logic has a test
2. `black .` and `ruff check .` are clean
3. `python -m h1b.pipeline run --demo` still works
4. README updated if behavior or results changed

## Known data caveats
- An LCA shows intent to hire. It is not an approval or a hire. Dedupe on CASE_NUMBER (quarterly files overlap).
- EMPLOYER_FEIN exists only in recent files (~FY2024+). Older years need name matching.
- PW_WAGE_LEVEL is blank or N/A when the employer used a DOL determination or a private survey.

## Roadmap
1. Real data FY2019–FY2026, with column aliases per year
2. DuckDB layer, fuzzy employer matching (rapidfuzz), parent-company groups
3. USCIS Employer Data Hub join (approvals/denials)
4. PERM (green card + majors)
5. Streamlit app + findings write-up
