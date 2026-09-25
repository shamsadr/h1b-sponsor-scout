"""Home: what the app is for, how to use it, three headline numbers, and a glossary."""

import streamlit as st

from app_data import PURPOSE, headline_numbers, years_label
from ui import data, fmt_count

DATA = data()
META = DATA["meta"]
FIND = "views/find_sponsors.py"
STEPS = [
    ("1. Pick your role family", "Analytics (combined), a single family, or all roles."),
    ("2. Narrow by worksite state", "Where the job is, not the company headquarters."),
    ("3. Check consistency and pay", "Filed every year? Median wage, Level II+ share."),
]
GLOSSARY = """
**LCA (Labor Condition Application).** A form an employer files with the U.S. Department of
Labor (DOL) before an H-1B petition, stating the job, worksite and wage. It shows intent to
hire, not a hire or a visa approval. This app counts **certified** LCAs.

**Prevailing wage.** The wage DOL sets for an occupation, level and area. The employer must pay
at least the higher of this and what it pays similar workers.

**Wage level I–IV.** Prevailing-wage tiers from entry level (I) to fully competent (IV). From
FY2027 the H-1B lottery gives Level II–IV registrations more entries than Level I.

**SOC code.** The Standard Occupational Classification code the employer picks for the job, e.g.
15-2051 for data scientists. The app groups codes into role families.

**Fiscal year (FY).** The U.S. federal fiscal year, October 1 to September 30. FY2025 runs from
October 1, 2024 to September 30, 2025.
"""


def open_find(filters: dict | None = None) -> None:
    """Set the shared filters (if given) and go to Find sponsors."""
    if filters:
        st.session_state.update(filters)
    st.switch_page(FIND)


st.title("H-1B Sponsor Scout")
st.write(PURPOSE)

for col, (step, hint) in zip(st.columns(3), STEPS, strict=True):
    col.markdown(f"**{step}**")
    col.caption(hint)

numbers = headline_numbers(DATA["sponsors"])
for i, (col, h) in enumerate(zip(st.columns(3), numbers, strict=True)):
    with col.container(border=True):
        st.metric(h["label"], fmt_count(h["value"]))
        st.caption(h["note"])
        if st.button("Show them in Find sponsors →", key=f"headline_{i}"):
            open_find(h["filters"])

if st.button("Find sponsors →", type="primary"):
    open_find()

st.caption(
    f"Data: DOL LCA disclosure files, {years_label(META['fiscal_years'])}, built "
    f"{META['built_at']}. {fmt_count(META['source_rows'])} LCA records, "
    f"{fmt_count(META['n_groups'])} employer groups."
)
with st.expander("Glossary"):
    st.markdown(GLOSSARY)
