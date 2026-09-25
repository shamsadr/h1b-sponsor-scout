# H-1B Sponsor Scout

**Problem.** International students (F-1 → OPT → H-1B) need to know which employers
*actually* sponsor H-1B in their target roles, at what wage level, and consistently
over time. The official data is split across agencies and hard to use raw.

**Approach.** Build a reproducible pipeline on public U.S. Department of Labor (DOL)
LCA disclosure data (FY2019 → present). It cleans and dedupes cases, annualizes wages,
normalizes employer names, maps SOC codes to role families (OR, Data/BI, Quant, IE,
Supply Chain/Logistics, Business Analyst; IT systems analysts and software are kept only as
"(context)" families, outside the target roles), and produces a transparent employer scorecard. Each metric is shown
separately; there is no single black-box score.

**Status.** Phase 1 of 5: ingest → clean → scorecard, running on synthetic demo data.
Next phases: real FY2019–FY2026 data, the USCIS Employer Data Hub join, PERM
green-card data, and a Streamlit app.

**Results.** _TBD: filled in after real data is loaded._ Demo output is synthetic.

## How to run
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python -m h1b.pipeline run --demo       # synthetic data -> reports/demo/
pytest -q                               # tests
```

With real data (download from DOL OFLC "Performance Data" → Disclosure Data → LCA):
```bash
python -m h1b.pipeline inspect data/raw/LCA_Disclosure_Data_FY2025_Q4.xlsx
python -m h1b.pipeline run --input data/raw/LCA_Disclosure_Data_FY2025_Q*.xlsx
```
Files are grouped by the `FYxxxx` in their filename (or pass `--fy` if all share one year).

## Scorecard columns
Positions, wages and levels use strict `CASE_STATUS == 'Certified'` rows only.
The table is sorted by `cases`, then `new_hire_positions`.
`reports/scorecard_by_family.csv` has the same columns for the top 25 employers by cases in each
target family, with a leading `family` column.

| column | meaning |
|---|---|
| cases | certified LCAs in target role families |
| positions | certified LCA worker positions in target role families |
| top_soc_title | most common SOC title among the employer's certified cases |
| positions_per_case | positions ÷ cases |
| bulk_filer | true if positions_per_case > 5 (a few large LCAs can dominate `positions`) |
| new_hire_positions | positions flagged new employment or change of employer |
| years_active | number of fiscal years with ≥1 certified LCA |
| median_wage_floor | median annualized offered wage from `WAGE_RATE_OF_PAY_FROM` (full-time, outliers excluded) |
| share_above_pw | share of those cases with offered wage more than 1% above the prevailing wage |
| range_share | share of certified cases with a filled-in `WAGE_RATE_OF_PAY_TO` |
| n_leveled | certified cases with a wage level I–IV (the denominator for level2plus_share) |
| level2plus_share | share of leveled cases at wage Level II–IV (these get more lottery entries from FY2027) |
| denial_rate | Denied ÷ (Certified + Certified-Withdrawn + Denied) |
| withdrawn_rate | (Withdrawn + Certified-Withdrawn) ÷ all rows, any status |
| h1b_dependent_share | share of certified cases where the employer checked H-1B dependent |
| willful_violator_count | number of certified cases where the employer checked willful violator |

## Methodology decisions
- **Quarterly files are not cumulative.** The FY2025 Q4 file's `DECISION_DATE` runs only
  2025-07-01 to 2025-09-30, so a fiscal year needs all its quarterly files. `run` groups
  input files by fiscal year, concatenates them, and dedupes on `CASE_NUMBER` into one
  `lca_fy{fy}.parquet`.
- **Only strict `Certified` counts.** `Withdrawn` and `Certified - Withdrawn` cases are
  reported separately as `withdrawn_rate` because an LCA that was withdrawn is weaker
  evidence of intent to hire; `denial_rate` is kept as before.
- **`FROM` is the pay floor; `TO` is filled inconsistently.** Some employers always fill
  `WAGE_RATE_OF_PAY_TO` and others never do, so wages use `FROM` (`median_wage_floor`) and
  `range_share` shows how often a range is given.
- **`share_above_pw` replaces the median premium.** Many employers pay exactly the
  prevailing wage, so the median premium collapses to 0 and hides differences; the share
  of cases paying more than 1% above the prevailing wage separates them.
- **Flags are self-attestations, not employer labels.** `H_1B_DEPENDENT` and
  `WILLFUL_VIOLATOR` are answered on each filing and can differ between an employer's
  cases, so they are reported as a share or a count instead of a yes/no for the employer.

## Limitations
- An LCA is an employer's intent to hire. It is not a petition, an approval, or a hire.
- Wage level depends on the SOC code the employer chose. It is not a measure of skill.
- Employer names are normalized by rules only (no fuzzy matching or parent-company grouping yet).
- The demo data is synthetic, with fake employers.

## Layout
```
h1b/config.py      constants: columns, SOC families, wage units
h1b/ingest.py      read xlsx/csv, standardize headers
h1b/clean.py       dedupe, filter, annualize, normalize, map SOC
h1b/scorecard.py   employer aggregation
h1b/pipeline.py    CLI entry point
scripts/make_demo_data.py
tests/
```
