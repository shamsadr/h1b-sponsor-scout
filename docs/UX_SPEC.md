# UX Spec: H-1B Sponsor Scout app (v2)

**Primary user:** an international student (F-1/OPT) looking for employers that sponsor
H-1B in their target role. They are not a data expert and they skim.
**Primary task:** "Show me employers that reliably sponsor my kind of role, ideally near me,
and tell me if they pay well." It should take under 30 seconds from opening the app.

Design principles, from HFE and Nielsen's usability heuristics:
- Recognition over recall
- Visibility of system status
- Consistency and standards
- Progressive disclosure
- Error prevention and recovery
- Plain language

---

## P0: must have

### 1. Formatting consistency (every page)
- Money: `$137,900`, rounded to the nearest dollar, thousands separators, no decimals, right-aligned.
- Percentages: whole numbers, e.g. `84%`. Show `—` when there is no value, never `nan`, `None` or `0%`.
- Counts: thousands separators (`1,423`).
- Use one shared formatting helper (in app/ui.py) and `st.column_config` for all tables. No
  per-page ad hoc formatting.

### 2. Display names
- Add `display_name` to published data. Rules, in order:
  1. The override label, if the group has one. Add a `display_name` column to
     `data/reference/employer_overrides.csv` with proper casing, e.g. "Amazon", "Goldman Sachs",
     "Bank of America", "Citi", "Deloitte", "EY", "Capital One", "RELX".
  2. Otherwise, the most frequent raw `EMPLOYER_NAME` as filed, e.g. "Tesla, Inc.".
- Never auto-title-case, because it breaks names like IBM, EY and PwC.
- Keep `parent_group` as the internal key. Users never see the normalized key except in the
  member-names table.

### 3. Role family dropdown
Options, in this order:
1. Analytics (combined), the **default**
2. Operations Research, Statistics / Decision Science, Data Science / BI, Quant / Finance
3. Industrial Engineering, Supply Chain / Logistics, Business / Mgmt Analyst
4. **All target roles** (union of all target families)
5. **All occupations (any H-1B role)**, visually separated or labeled so it's clearly the broad view

Each option gets a one-line description shown under the dropdown, e.g. "Analytics (combined) =
OR + Statistics + Data Science/BI + Quant/Finance SOC codes."

### 4. "Consistent sponsors only": one definition everywhere
- Definition: **"Filed at least N certified LCAs in this role group in *every* loaded fiscal
  year (FY2024 and FY2025)"**, where N is the minimum-cases slider value.
- This requires per-year case counts in the published sponsors data (`cases_fy2024`,
  `cases_fy2025`, …) so the check runs per year, not on the total.
- The UI shows a checkbox with a `help=` tooltip containing the definition, plus a
  one-line caption under it.
- Align `reports/consistent_sponsors.csv` with this definition, using N = 10, and say so in the README.

### 5. Status line and empty states
- Above the table: "Showing **312 employers** · Analytics (combined) · Arizona · consistent only · min 5 cases/year".
- When there are no results: "No employers match these filters. Try lowering the minimum cases or
  unchecking 'Consistent sponsors only'." Include a one-click **Reset filters** button.

---

## P1: should have

### 6. Find sponsors table: plain language and progressive disclosure
Default columns, in order:

| Column | Header | Help text (tooltip) |
|---|---|---|
| display_name | Employer | Brand-level group; see Employer lookup for legal entities |
| cases | Certified LCAs | Certified labor condition applications, i.e. intent to hire, not hires |
| cases per year | FY2024 / FY2025 | Certified LCAs by fiscal year |
| median_wage_floor | Median offered wage | Median lower bound of the offered pay range, annualized |
| share_above_pw | Pays above prevailing wage | Share of LCAs offering >1% above the DOL prevailing wage |
| level2plus_share | Level II+ share | Share at wage Level II–IV. From FY2027 these get more lottery entries |

Behind a **"Show advanced columns"** toggle: withdrawn rate (with a right-censoring note),
n_leveled, top SOC title, number of legal entities, positions.

### 7. State filter
- Show full names with codes, e.g. "Arizona (AZ)", sorted alphabetically, with "All states" first.
- Caption: "Worksite state of the job, not company headquarters."

### 8. Employer lookup: recognition over recall
- Replace the free-text box with a **searchable selectbox** of display names. It must also match
  member names, so typing "Merrill" finds Bank of America.
- **Quick picks** (pills or buttons) above the selectbox:
  - "Top in [current role family]": the 8 highest-case employers, computed from data.
  - **Curated sets**, labeled "(curated)" and defined in `data/reference/curated_sets.csv` with
    columns set_name, display_name. Starting sets: Big Tech, Banks & Quant, Consulting (Big 4 / MBB),
    Analytics consultancies, Manufacturing / EV. Values must match existing groups; add a test for this.
- The employer page shows a summary card first: display name, total certified LCAs, years
  active, median wage, and Level II+ share. Charts and the member-names table come below it.

### 9. Shared state and shareable links
- Role family, state, min cases and the consistent filter persist across pages (session_state).
- Reflect them in the URL (`st.query_params`) so a filtered view can be shared or bookmarked.

### 10. Click-through
- Selecting a row in Find sponsors opens that employer in Employer lookup, if the installed
  Streamlit version supports dataframe row selection. Otherwise, show an "Open in Employer
  lookup" selectbox under the table.

---

## P2: nice to have

### 11. Home / "How to use" page (new first page)
- 3 steps: pick your role → narrow by state → check consistency and pay.
- 3 headline numbers from findings.md, e.g. records analyzed, employer groups, consistent analytics sponsors.
- A short glossary: LCA, prevailing wage, wage level I–IV, SOC code, fiscal year.
- Data freshness: fiscal years covered and build date (from meta.json).

### 12. Accessibility and polish
- Never rely on color alone; charts have labels or legends.
- Units in headers where they aren't obvious.
- Wide layout; tables use full width; no horizontal scroll for default columns on a laptop.
- The footer disclaimer stays on every page.

---

## Acceptance criteria and tests
- Formatting helper unit tests: money, percent and missing-value cases.
- display_name: override label wins; otherwise the most frequent raw name; test that "IBM"-style names aren't title-cased.
- Consistent filter: an employer with 12 cases in FY24 and 3 in FY25 fails at N=5 and passes at N=3.
- Every curated-set entry matches an existing group.
- AppTest: every page loads on demo data with default filters and with a filter that returns zero rows (the empty state renders).
- Published data stays under 20 MB. Report sizes before and after adding "All target roles" and
  "All occupations". If "All occupations" would exceed the limit, include only groups with ≥ 2
  cases for that option and state this in the UI caption.
- Manual check: screenshot every page with real data, in light and dark mode.
