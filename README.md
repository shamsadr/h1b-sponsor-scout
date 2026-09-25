# H-1B Sponsor Scout

**Problem.** International students (F-1 → OPT → H-1B) need to know which employers
*actually* sponsor H-1B in their target roles, at what wage level, and consistently
over time. The official data is split across agencies and hard to use raw.

**Approach.** Build a reproducible pipeline on public U.S. Department of Labor (DOL)
LCA disclosure data (FY2019 → present). It cleans and dedupes cases, annualizes wages,
normalizes employer names, maps SOC codes to role families (OR, Data/BI, Quant, IE,
Business Analyst), and produces a transparent employer scorecard. Each metric is shown
separately; there is no single black-box score.

**Status.** Phase 1 of 5: ingest → clean → scorecard, running on synthetic demo data.
Next phases: real FY2019–FY2026 data, the USCIS Employer Data Hub join, PERM
green-card data, and a Streamlit app.

**Results.** _TBD: filled in after real data is loaded._ Demo output is synthetic.

## How to run
```bash
conda env create -f environment.yml
conda activate h1b
python -m h1b.pipeline run --demo       # synthetic data -> reports/demo/
pytest -q                               # tests
```

With real data (download from DOL OFLC "Performance Data" → Disclosure Data → LCA):
```bash
python -m h1b.pipeline inspect data/raw/LCA_Disclosure_Data_FY2025_Q4.xlsx
python -m h1b.pipeline run --input data/raw/LCA_Disclosure_Data_FY2025_Q4.xlsx
```

## Scorecard columns
| column | meaning |
|---|---|
| positions | certified LCA worker positions in target role families |
| new_hire_positions | positions flagged new employment or change of employer |
| years_active | number of fiscal years with ≥1 certified LCA |
| median_wage | median annualized offered wage (full-time, outliers excluded) |
| median_wage_premium | offered wage ÷ prevailing wage − 1 |
| level2plus_share | share of leveled cases at wage Level II–IV (these get more lottery entries from FY2027) |
| denial_rate | Denied ÷ (Certified + Denied) |
| h1b_dependent / willful_violator | any LCA flagged Y |

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
