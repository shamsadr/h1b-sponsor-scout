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
