# Findings log

Measured facts only, each dated. Source: `data/processed/lca_fy2025.parquet` built from the four
FY2025 quarterly LCA files (`LCA_Disclosure_Data_FY2025_Q1..Q4.xlsx`) unless stated otherwise.

## 2026-09-24 — FY2025

- **Quarterly files are not cumulative.** Each file's `DECISION_DATE` covers only its own quarter,
  with no null dates:

  | File | Rows | Min `DECISION_DATE` | Max `DECISION_DATE` |
  |---|---|---|---|
  | Q1 | 107,414 | 2024-10-01 | 2024-12-31 |
  | Q2 | 132,133 | 2025-01-01 | 2025-03-31 |
  | Q3 | 238,425 | 2025-04-01 | 2025-06-30 |
  | Q4 | 118,580 | 2025-07-01 | 2025-09-30 |

- **Rows after dedupe.** The four files hold 596,552 raw rows and 594,821 unique `CASE_NUMBER`s;
  1,731 cases appear in more than one file. After deduping on `CASE_NUMBER` and keeping
  `VISA_CLASS == 'H-1B'`, the parquet has 580,623 rows (dates 2024-10-01 to 2025-09-30, 0 duplicate
  case numbers). The 14,198 unique cases dropped are in the E-3 and H-1B1 (Chile, Singapore) visa
  classes.
- **Wage equals prevailing wage.** Among certified rows with both wages present and the same unit
  (536,249 of 537,796), `WAGE_RATE_OF_PAY_FROM == PREVAILING_WAGE` on 185,025 rows (34.5%).
- **`WAGE_RATE_OF_PAY_TO`** is filled on 32.1% of certified rows in the Q4 file (Apple 100%,
  Deloitte Consulting 0%; measured on Q4 only).
- **Positions skew from bulk LCAs.**
  - 95.3% of the 537,796 certified LCAs have `TOTAL_WORKER_POSITIONS` = 1.
  - LCAs with 50 or more positions: 1,482 certified LCAs hold 10.7% of the 873,986 certified positions.
  - In the target families, 183 of 79,881 certified LCAs have 50 or more positions and hold 12.5% of
    the 124,975 certified positions.
  - 37 of 18,663 target-family employers have more than 5 positions per case.
  - Examples: McKinsey & Company Inc. United States, 455 cases and 6,097 positions (13.4 per case);
    Goldman Sachs Services LLC, 132 cases and 3,696 positions (28.0); Goldman Sachs Bank USA,
    121 cases and 3,685 positions (30.5).
  - The six LCAs with the most positions are all `Giants Services Sprl LLC`, all Denied, with 250 to
    1,325 positions each.
- **SOC 15-1211 composition (all statuses).** 13,932 rows: Computer Systems Analysts 13,784,
  Health Informatics Specialists 130, other titles 18. Under the earlier mapping this code
  was 13,932 of the 26,147 rows in the "Business / Mgmt Analyst" family (13-1111: 6,714;
  13-1161: 5,501).
- **Industrial Engineering composition (all statuses).** SOC 17-2112 has 10,819 rows: Industrial
  Engineers 5,778, Validation Engineers 2,546, Manufacturing Engineers 2,192, Human Factors
  Engineers and Ergonomists 297, other 6. SOC 13-1081 has 2,922 rows: Logisticians 1,426,
  Logistics Analysts 998, Logistics Engineers 497, other 1. Under the earlier mapping both codes
  were in the "Industrial Engineering" family (13,741 rows).
- **Rows by `soc_family` (mapping before the 17-2112.02 and 11-3071 changes):** Other 300,760; Software (context) 180,149;
  Data Science / BI 33,346; IT Systems Analyst (context) 13,932; Quant / Finance 13,581;
  Business / Mgmt Analyst 12,215; Industrial Engineering 10,819; Operations Research 7,996;
  Statistics / Decision Science 4,903; Supply Chain / Logistics 2,922.

## 2026-09-24 — SOC detail codes and FY2024 schema

- **17-2112 detail codes (FY2025, all statuses, 10,819 rows):**

  | `SOC_CODE` | Rows | `SOC_TITLE` |
  |---|---|---|
  | 17-2112.00 | 5,749 | Industrial Engineers |
  | 17-2112.01 | 297 | Human Factors Engineers and Ergonomists |
  | 17-2112.02 | 2,548 | Validation Engineers (2,546), Validation Engineer (2) |
  | 17-2112.03 | 2,192 | Manufacturing Engineers |
  | 17-2112 (no suffix) | 32 | Industrial Engineers 28, Industrial Engineer 2, INDUSTRIAL ENGINEER 1, Quality Engineer 1 |
  | 17-21121.00 (malformed) | 1 | Industrial Engineers |

- **11-3071 (1,427 rows):** 11-3071.04 has 1,101 rows (Supply Chain Managers 1,098, plus 3 with other
  spellings or titles), 11-3071.00 has 325 (Transportation, Storage, and Distribution Managers),
  and 11-3071 with no suffix has 1.
- **13-1081 (2,922 rows):** 13-1081.00 has 1,415 (Logisticians), 13-1081.01 has 498 (Logistics
  Engineers), 13-1081.02 has 999 (Logistics Analysts 998, Logisticians 1), and 13-1081 with no
  suffix has 10 (Logisticians).
- **Rows by `soc_family` (current mapping, all statuses):** Other 299,333; Software (context)
  180,149; Data Science / BI 33,346; IT Systems Analyst (context) 13,932; Quant / Finance 13,581;
  Business / Mgmt Analyst 12,215; Industrial Engineering 8,271; Operations Research 7,996;
  Statistics / Decision Science 4,903; Supply Chain / Logistics 4,349; Validation Eng (context)
  2,548.
- **`clean` is reproducible.** Re-cleaning FY2025 from `data/interim/lca_raw_fy2025.parquet`
  (596,552 rows) twice gave identical 580,623-row output (same row hash both times).
- **FY2024 Q1 schema.** `LCA_Disclosure_Data_FY2024_Q1.xlsx` has 97 columns and FY2025 Q4 has 98.
  The only header in FY2025 Q4 but not FY2024 Q1 is `LAWFIRM_BUSINESS_FEIN`. FY2024 Q1 has all 7
  `REQUIRED_COLS` and all 17 `OPTIONAL_COLS`, so `COLUMN_ALIASES` is still empty. Only this one
  FY2024 file was inspected.

## 2026-09-24 — FY2024 and cross-year checks

Source: `lca_fy2024.parquet` and `lca_fy2025.parquet`, built from the eight quarterly files.

- **FY2024 quarterly files are not cumulative, and `EMPLOYER_FEIN` is filled on every row.**

  | File | Rows | Min `DECISION_DATE` | Max `DECISION_DATE` | Non-blank `EMPLOYER_FEIN` |
  |---|---|---|---|---|
  | Q1 | 99,692 | 2023-10-02 | 2023-12-31 | 100% |
  | Q2 | 123,978 | 2024-01-01 | 2024-03-31 | 100% |
  | Q3 | 216,470 | 2024-04-01 | 2024-06-30 | 100% |
  | Q4 | 120,897 | 2024-07-01 | 2024-09-30 | 100% |

- **FY2024 rows.** The four files hold 561,037 rows with 561,037 unique `CASE_NUMBER`s, so the
  within-year dedupe removed 0 (FY2025 had 1,731 cases in more than one file). Keeping
  `VISA_CLASS == 'H-1B'` leaves 546,807 rows (2023-10-02 to 2024-09-30, 0 duplicate case numbers).
  The 14,230 cases dropped are E-3 Australian 10,399, H-1B1 Chile 2,312 and H-1B1 Singapore 1,519.
- **Cross-year overlap.** 8,662 `CASE_NUMBER`s appear in both `lca_fy2024` and `lca_fy2025`. All 8,662
  are `Certified` in FY2024 and `Certified - Withdrawn` in FY2025, with the same employer and
  `soc_family` in both years. 1,169 of them are in the target families. The combined scorecard
  input has 0 duplicate `CASE_NUMBER`s among certified target-family rows.
- **How the scorecard treated them (before the cross-year dedupe was added).** `cases`, `positions` and wages use strict `Certified`, so each
  overlapping case is counted once (as its FY2024 certified record). The FY2025 record is included
  in `withdrawn_rate` and in the `denial_rate` denominator, so those cases appear in those
  denominators twice. Across all target-family rows the withdrawn share is 6.48% as scored and
  6.52% when only the latest record per case is kept.
- **Certified target-family cases, FY2024 vs FY2025 (before the cross-year dedupe):**

  | Family | FY2024 | FY2025 | Change |
  |---|---|---|---|
  | Business / Mgmt Analyst | 9,963 | 11,413 | +14.6% |
  | Data Science / BI | 23,685 | 31,465 | +32.8% |
  | Industrial Engineering | 6,398 | 7,640 | +19.4% |
  | Operations Research | 8,241 | 7,475 | -9.3% |
  | Quant / Finance | 11,248 | 12,388 | +10.1% |
  | Statistics / Decision Science | 4,756 | 4,406 | -7.4% |
  | Supply Chain / Logistics | 3,331 | 4,071 | +22.2% |
  | All target families | 67,622 | 78,858 | +16.6% |

  Certified H-1B rows in all families: 502,374 (FY2024) and 537,796 (FY2025), +7.1%.
- **Employers with at least 10 certified cases in both years** (by `employer_norm`, in the family):
  Business / Mgmt Analyst 55, Data Science / BI 226, Industrial Engineering 57, Operations
  Research 60, Quant / Finance 112, Statistics / Decision Science 65, Supply Chain / Logistics 20.
- **Employers' SOC choices differ by year.** Amazon.com Services had 14,249 certified cases in
  FY2024 and 15,192 in FY2025. Its 15-2031 cases went from 1,283 to 541, 15-2041 from 402 to 229,
  15-2051 from 1,394 to 1,810, and 13-1082 from 21 to 235. All SOC codes are in the same format in
  both years.

## 2026-09-24 — After the cross-year dedupe

Source: `lca_fy2024.parquet` + `lca_fy2025.parquet`, deduped on `CASE_NUMBER` (latest
`DECISION_DATE` kept, earliest fiscal year assigned).

- **Rows.** 1,127,430 rows before and 1,118,768 after, so 8,662 rows removed. All 8,662 cases were
  first seen in FY2024 and have `Certified - Withdrawn` as the latest status.
- **Status by first-appearance year (all families):** FY2024 has 493,712 Certified, 40,325
  Certified - Withdrawn, 8,836 Withdrawn and 3,934 Denied. FY2025 has 537,796 Certified, 21,449
  Certified - Withdrawn, 9,211 Withdrawn and 3,505 Denied.
- **Withdrawn share (`Withdrawn` + `Certified - Withdrawn`) by first-appearance year:** FY2024
  9.0% and FY2025 5.4% across all families; in the target families 8.3% (6,062 of 73,094) and
  5.0% (4,155 of 83,492).
- **Certified cases by family and fiscal year** (`reports/family_trends.csv`):

  | Family | FY2024 | FY2025 | Change |
  |---|---|---|---|
  | Analytics (combined) | 47,051 | 55,734 | +18.5% |
  | Business / Mgmt Analyst | 9,845 | 11,413 | +15.9% |
  | Data Science / BI | 23,294 | 31,465 | +35.1% |
  | Industrial Engineering | 6,267 | 7,640 | +21.9% |
  | Operations Research | 8,146 | 7,475 | -8.2% |
  | Quant / Finance | 10,962 | 12,388 | +13.0% |
  | Statistics / Decision Science | 4,649 | 4,406 | -5.2% |
  | Supply Chain / Logistics | 3,290 | 4,071 | +23.7% |

  The FY2025 counts are unchanged from before the dedupe; the FY2024 counts fell by 1,169 in total
  across the seven target families.
- **Consistent sponsors** (`reports/consistent_sponsors.csv`, at least 10 certified cases in both
  years, by `employer_norm`): Analytics (combined) 483, Business / Mgmt Analyst 55, Data Science /
  BI 223, Industrial Engineering 56, Operations Research 59, Quant / Finance 110, Statistics /
  Decision Science 64, Supply Chain / Logistics 20. The largest in the analytics rollup are
  Amazon.com Services (3,118 + 2,682 cases), Ernst & Young U.S. (2,447 + 1,897) and Microsoft
  (861 + 1,022).
- **Amazon.com Services SOC codes (certified cases, FY2024 → FY2025):** total 14,249 → 15,192;
  15-2031 1,283 → 541; 15-2041 402 → 229; 15-2051 1,394 → 1,810; 13-1082 21 → 235. Its analytics
  rollup total was 3,118 → 2,682.
- **Employers in the scorecard:** 26,778 for FY2024 + FY2025, down from 26,958 before the dedupe.
