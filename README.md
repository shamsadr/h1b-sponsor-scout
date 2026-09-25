# H-1B Sponsor Scout

**Live app:** <URL — add after deploy>

**Problem.** International students (F-1 → OPT → H-1B) need to know which employers
*actually* sponsor H-1B in their target roles, at what wage level, and consistently
over time. The official data is split across agencies and hard to use raw.

**Approach.** Build a reproducible pipeline on public U.S. Department of Labor (DOL)
LCA disclosure data (FY2019 → present). It cleans and dedupes cases, annualizes wages,
normalizes employer names, maps SOC codes to role families (OR, Data/BI, Quant, IE,
Supply Chain/Logistics, Business Analyst; IT systems analysts and software are kept only as
"(context)" families, outside the target roles), and produces a transparent employer scorecard. Each metric is shown
separately; there is no single black-box score.

**Status.** Real FY2024–FY2025 data runs through ingest → clean → employer grouping →
scorecard, and a Streamlit app reads precomputed tables from it. Next: earlier fiscal years
(FY2019–FY2023), the USCIS Employer Data Hub join and PERM green-card data.

**Results** (DOL LCA data for FY2024–FY2025; how each number was measured is in
`notes/findings.md`):
- **Records processed:** 561,037 LCA rows for FY2024 and 596,552 for FY2025, from eight quarterly
  DOL files. After removing duplicates and keeping only H-1B filings, 1,118,768 unique cases remain
  across both years.
- **Employer names → groups:** across FY2024–FY2025, 88,665 distinct employer names collapse into
  84,911 employer groups, using shared tax IDs (FEINs), matching names and a hand-checked overrides
  file. For example, 10 Amazon names, including Amazon.com Services and AWS, become one AMAZON group.
- **Analytics hiring grew:** certified LCAs in analytics roles (operations research, statistics,
  data science / BI, quant) rose from 47,051 in FY2024 to 55,734 in FY2025, +18.5%. Read FY2025 as
  an upper bound: its cases have had less time to be withdrawn.
- **Consistent sponsors:** 477 employer groups had at least 10 certified analytics cases in both
  FY2024 and FY2025.
- **Many offers sit exactly at the prevailing wage:** in FY2025, about 35% of certified H-1B filings
  (185,025 of the 536,249 that could be compared, all roles) offered exactly the prevailing wage.
- **Job codes shift, so trends are partly labeling:** Amazon.com Services' certified cases rose from
  14,249 in FY2024 to 15,192 in FY2025, yet its Operations Research cases fell from 1,283 to 541
  and Statistics from 402 to 229, while Business Intelligence Analyst cases rose from 1,394 to 1,810.
- **What these numbers are not:** an LCA shows an employer's intent to hire. It is not a hire or a
  visa approval.

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
python -m h1b.pipeline clean          # re-clean from data/interim without re-reading the xlsx
python -m h1b.pipeline scorecard      # rebuild the scorecards from data/processed
python -m h1b.pipeline publish        # slim tables for the app -> data/app/ (commit them)
```
Files are grouped by the `FYxxxx` in their filename (or pass `--fy` if all share one year).

## Streamlit app
```bash
streamlit run app/streamlit_app.py    # reads data/app/ only (about 2.6 MB, committed)
```
Pages:
- **Find sponsors:** a ranked table for a role group and a worksite state. Role groups are
  Analytics (combined) (the default), each target family, "All target roles" and "All occupations
  (any H-1B role)". A status line shows the result count and filters, and an empty result
  offers **Reset filters**. The default columns are certified LCAs (total and per fiscal year),
  median offered wage, share above the prevailing wage and Level II+ share. Withdrawn rate, filing
  names, legal entities (FEINs) and more are behind "Show advanced columns". The table can be
  downloaded as CSV.

  **Consistent sponsors** (one definition, used by the app and `reports/consistent_sponsors.csv`):
  *filed at least N certified LCAs in this role group in every loaded fiscal year (FY2024 and
  FY2025)*. In the app, N is the "Minimum certified LCAs" slider. Without the checkbox, N applies
  to the total. The report uses N = 10.
- **Employer lookup:** search a group or any member name to see certified cases by family and year,
  the wage-level mix and the member names.
- **Trends:** certified cases per family and year, with the SOC-substitution and withdrawal caveats.
- **Methodology & limitations:** rendered from this README.

`publish` precomputes the scorecard for every role group × worksite state (plus all states)
with the same functions as the reports, so the app does no heavy computation. The role groups are
each target family, Analytics (combined), "All target roles" and "All occupations" (every H-1B
role, including software and "Other"). Each row also carries certified cases per fiscal year
(`cases_fy2024`, `cases_fy2025`, …) and the number of distinct filing FEINs. The lookup tables
(`groups`, `employer_breakdown`, `employer_levels`, `members`) cover every employer group, so any
row can be opened in Employer lookup. `publish` fails if `data/app/` would exceed 20 MB (it is
13.2 MB for FY2024–FY2025), and `meta.json` records the fiscal years, build date, name and group
counts, and the commit the data was built from (`-dirty` if the code had uncommitted edits).

**Display names.** The app shows each group by its `display_name`: the override's
`display_name` (e.g. "Goldman Sachs", "Citi"), otherwise the most frequent raw `EMPLOYER_NAME` as
filed (e.g. "Tesla, Inc."). Names are never re-cased, so "IBM" and "EY" stay as filed. Names that
look alike ignoring case and punctuation get the employer state, then the FEIN, appended
("Acme, LLC (AZ)"), so every display name is unique. `parent_group` stays the internal key.

**Deploy (Streamlit Community Cloud):** repo `shamsadr/h1b-sponsor-scout`, branch `main`, main
file `app/streamlit_app.py`, Python 3.12. Cloud installs the lean `app/requirements.txt`
(streamlit ≥ 1.55, pandas ≥ 2.1.4, pyarrow ≥ 14.0.2, the tested minimums; 1.55 is the first
version that shows money as `$137,900`). To update the site,
run `publish`, commit `data/app/`, and push.

## Scorecard columns
One row per `parent_group` (see "Employer grouping" below). `employer_scorecard(..., key="employer_norm")`
still gives one row per normalized name.
Positions, wages and levels use strict `CASE_STATUS == 'Certified'` rows only.
The table is sorted by `cases`, then `new_hire_positions`.
`reports/scorecard_by_family.csv` has the same columns for the top 25 employers by cases in each
target family, with a leading `family` column.

| column | meaning |
|---|---|
| parent_group | employer group label (a hiring brand, e.g. `AMAZON`, or the group's largest name) |
| employer_name | most common raw `EMPLOYER_NAME` in the group's certified cases |
| n_entities | number of normalized employer names in the group with certified cases |
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

## Employer grouping
Each normalized employer name (`employer_norm`) is a node in a graph (`h1b/groups.py`). Groups
are the connected components, and their label is the `parent_group` column.

- **Name edge:** two names have the same name key, i.e. `employer_norm` without generic words (US,
  USA, America, NA, Services, Group, Holdings, a trailing "and") and without spaces. So
  `GOLDMAN SACHS SERVICES` and `GOLDMAN SACHS AND` (from "& Co.") match. A key with fewer than
  2 words or 6 letters never links, so `GLOBAL SERVICES` and `GLOBAL GROUP` stay apart.
- **FEIN edge:** two names share a *primary* FEIN (the one each name uses most), so a stray FEIN
  on a few filings can't bridge two companies. No edge for placeholder FEINs (`12-3456789`),
  malformed ones, or a FEIN whose names form more than 2 unrelated clusters (names are related if
  they share a first word or are ≥ 0.85 similar by `difflib`). This cuts state university
  systems and law-firm FEINs typed on client filings.
- **Manual overrides:** `data/reference/employer_overrides.csv` (committed) holds `merge` rows
  (join a name to a `parent_group` label, with an optional `display_name` for the app) and `split`
  rows (the name gets no automatic edges).
- **Merge rule: one hiring brand a candidate would apply to, not corporate ownership.** Amazon
  therefore covers the Amazon-branded entities (Amazon.com Services, AWS, Amazon Data Services,
  Amazon Development Center, Amazon Advertising, Payments, Retail, Studios, ...) but not Twitch,
  Zappos or Whole Foods. Subsidiaries file under their own
  FEINs, so brand groups like these come only from overrides.
- **Label clashes:** if a group without overrides has the same name as an override label, its
  primary FEIN is appended to its label (the 4-row employer named `CITI` becomes
  `CITI (56-1928771)`, separate from the `CITI` brand group).
- **Review files:** `reports/parent_groups.csv` lists every name with its group, primary FEIN and
  state, and the edge types that linked it. `reports/merge_review.csv` has one row per member of a
  multi-name group. Its `risk_flags` column counts four warning signals:
  - `name_sim < 0.5`: `name_sim` is the difflib similarity of the name to the group label
  - linked by name only, with a primary FEIN different from the group's main FEIN
  - `state_mismatch`: the member's main `EMPLOYER_STATE` differs from the group's
  - `looks_like_person_or_title`: the name ends in a job title word ("SYSTEMS ANALYST", up to
    3 words) or a professional suffix (MD, DDS, CPA, ...)

  Rows are sorted by `risk_flags`, then rows, and the top 25 are printed after each run.
  Members placed by an override are hand-reviewed: `reviewed=True` and `risk_flags=0`, with the
  signal columns still filled in.

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
- **Cases are deduped across years.** The scorecard loads every processed year and keeps one
  row per `CASE_NUMBER`: the record with the latest `DECISION_DATE`, assigned to the earliest
  fiscal year the case appears in. A case certified in FY2024 and withdrawn in the FY2025 file
  therefore counts once, as an FY2024 case with a withdrawn status. In our data 8,662 cases
  (1,169 in target families) were recorded this way.
- **Withdrawals are right-censored in the latest year.** DOL records a withdrawal in the file of
  the year it happens, so cases first seen in the newest loaded year have had no time to be
  withdrawn. Among cases first seen in FY2024, 9.0% ended up withdrawn (`Withdrawn` or
  `Certified - Withdrawn`), against 5.4% of those first seen in FY2025, and all 8,662 FY2024
  cases re-recorded in FY2025 are `Certified - Withdrawn`. Compare `withdrawn_rate` across years
  only once the later year's data is complete, and read the latest year's certified counts as an
  upper bound.
- **Employers substitute SOC codes, so family trends are partly classification.** Amazon.com
  Services had 14,249 certified cases in FY2024 and 15,192 in FY2025. Its Operations Research
  (15-2031) cases fell from 1,283 to 541 and Statistics (15-2041) from 402 to 229, while
  Business Intelligence Analysts (15-2051, Data Science / BI) rose from 1,394 to 1,810 and Project
  Management Specialists (13-1082) from 21 to 235. Moves among the four families in
  "Analytics (combined)" net out of that rollup, so use it alongside the single-family trends
  (for Amazon the rollup went from 3,118 to 2,682 cases).

## Reports
Written to `reports/` by `run` and `scorecard` (git-ignored, regenerate any time).

| file | contents |
|---|---|
| scorecard_target_roles.csv | one row per employer, columns above, target families only |
| scorecard_by_family.csv | same columns, top 25 employers by cases in each target family |
| family_trends.csv | certified cases per family and fiscal year, plus an "Analytics (combined)" rollup of OR, Statistics / Decision Science, Data Science / BI and Quant / Finance |
| parent_groups.csv | one row per `employer_norm`: parent_group, primary_fein, primary_state, rows, link (`name` / `fein` / `override` / `none`) |
| merge_review.csv | one row per member of a multi-name group: name_sim, link, state_mismatch, looks_like_person_or_title, row_share, reviewed, risk_flags |
| consistent_sponsors.csv | employer groups with ≥10 certified cases in every loaded year (the "Consistent sponsors" definition with N = 10), per family and for the analytics rollup, with one `cases_fy{year}` column per year |

## Limitations
- An LCA is an employer's intent to hire. It is not a petition, an approval, or a hire.
- Wage level depends on the SOC code the employer chose. It is not a measure of skill.
- Employer groups come from name rules, shared FEINs and a hand-kept overrides file. Only a few
  brands are merged by hand so far, and names in years without `EMPLOYER_FEIN` can join only
  through name edges.
- The demo data is synthetic, with fake employers.

## Layout
Data layers: `data/raw` (DOL xlsx) → `data/interim` (standardized, uncleaned parquet) →
`data/processed` (cleaned, deduped parquet) → `reports/`. Only `run` reads the xlsx.
```
h1b/config.py      constants: columns, SOC families, wage units
h1b/ingest.py      read xlsx/csv, standardize headers
h1b/clean.py       dedupe, filter, annualize, normalize, map SOC
h1b/groups.py      parent-company grouping (name + FEIN graph, overrides)
h1b/scorecard.py   employer aggregation
h1b/publish.py     slim precomputed tables for the app
h1b/pipeline.py    CLI entry point
app/streamlit_app.py   navigation + footer; pages in app/views/, shared charts in app/ui.py
app/app_data.py        pure helpers: load, filter, search, README sections
data/app/              published app tables (committed)
data/reference/employer_overrides.csv   manual merges and splits
scripts/make_demo_data.py
tests/
```
