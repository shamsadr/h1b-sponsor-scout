"""Data helpers for the Streamlit app: load the published tables, filter, search, README text.

Pure pandas (no Streamlit), so they can be unit-tested. The app reads only the small
files written by `python -m h1b.pipeline publish` (data/app/), never the raw data.
"""

import json
import os
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
STATE_ALL = "ALL"  # must match h1b/publish.py
ANALYTICS_LABEL = "Analytics (combined)"  # these three must match h1b/config.py
ALL_TARGET_LABEL = "All target roles"
ALL_OCCUPATIONS_LABEL = "All occupations"
TABLES = ["sponsors", "groups", "employer_breakdown", "employer_levels", "members"]

# Role-family dropdown: order and one-line descriptions (SOC codes from h1b/config.py).
FAMILY_ORDER = [
    ANALYTICS_LABEL,
    "Operations Research",
    "Statistics / Decision Science",
    "Data Science / BI",
    "Quant / Finance",
    "Industrial Engineering",
    "Supply Chain / Logistics",
    "Business / Mgmt Analyst",
    ALL_TARGET_LABEL,
    ALL_OCCUPATIONS_LABEL,
]
FAMILY_DESCRIPTIONS = {
    ANALYTICS_LABEL: "Operations Research + Statistics + Data Science/BI + Quant/Finance "
    "SOC codes.",
    "Operations Research": "Operations research analysts (SOC 15-2031).",
    "Statistics / Decision Science": "Statisticians (15-2041) and actuaries (15-2011).",
    "Data Science / BI": "Data scientists and business intelligence analysts (15-2051).",
    "Quant / Finance": "Financial and investment analysts (13-2051), financial risk specialists "
    "(13-2054) and quantitative analysts (13-2099.01).",
    "Industrial Engineering": "Industrial, human factors and manufacturing engineers (17-2112; "
    "validation engineers excluded).",
    "Supply Chain / Logistics": "Logisticians (13-1081) and transportation, storage, distribution "
    "and supply chain managers (11-3071).",
    "Business / Mgmt Analyst": "Management analysts (13-1111) and market research analysts "
    "(13-1161).",
    ALL_TARGET_LABEL: "All seven target families above combined.",
    ALL_OCCUPATIONS_LABEL: "Broad view: every H-1B LCA, including software developers and roles "
    "outside the target families.",
}

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "GU": "Guam", "MP": "Northern Mariana Islands", "PR": "Puerto Rico",
    "VI": "U.S. Virgin Islands",
}  # fmt: skip
SHARE_COLS = ["share_above_pw", "level2plus_share", "withdrawn_rate"]


def data_dir() -> Path:
    """data/app/, or the folder in $H1B_APP_DATA (tests point it at a demo publish)."""
    return Path(os.environ.get("H1B_APP_DATA", ROOT / "data" / "app"))


def load_tables(folder: Path) -> dict:
    """{'sponsors': df, ..., 'family_trends': df, 'meta': dict} from a publish folder."""
    tables: dict = {name: pd.read_parquet(folder / f"{name}.parquet") for name in TABLES}
    for name in TABLES:  # plain strings are simpler to filter than categoricals
        df = tables[name]
        for col in df.select_dtypes("category").columns:
            df[col] = df[col].astype(str)
    tables["family_trends"] = pd.read_csv(folder / "family_trends.csv")
    tables["meta"] = json.loads((folder / "meta.json").read_text())
    return tables


def years_label(years: list[int]) -> str:
    """[2024, 2025] -> 'FY2024–FY2025'; [2025] -> 'FY2025'."""
    years = sorted(years)
    if len(years) == 1:
        return f"FY{years[0]}"
    return f"FY{years[0]}–FY{years[-1]}"


def footer_text(meta: dict) -> str:
    """The source / caveat line shown at the bottom of every page."""
    return (
        f"Source: U.S. DOL OFLC LCA disclosure data, {years_label(meta['fiscal_years'])}. "
        "An LCA shows intent to hire, not a hire or visa approval. "
        "Not legal or immigration advice."
    )


def year_columns(df: pd.DataFrame) -> list[str]:
    """The published per-year case columns, oldest first: ['cases_fy2024', 'cases_fy2025']."""
    return sorted(c for c in df.columns if re.fullmatch(r"cases_fy\d{4}", c))


def state_label(code: str) -> str:
    """'AZ' -> 'Arizona (AZ)'; STATE_ALL -> 'All states'; unknown codes stay as they are."""
    if code == STATE_ALL:
        return "All states"
    return f"{STATE_NAMES[code]} ({code})" if code in STATE_NAMES else code


def state_options(codes) -> list[str]:
    """STATE_ALL first, then the codes sorted by full state name."""
    rest = sorted({c for c in codes if c != STATE_ALL}, key=lambda c: (state_label(c), c))
    return [STATE_ALL] + rest


def consistent_definition(min_cases: int, years: list[int]) -> str:
    """The one wording of 'consistent' used in the tooltip, caption and README."""
    fys = " and ".join(f"FY{y}" for y in sorted(years))
    return (
        f"Filed at least {min_cases} certified LCAs in this role group in every loaded "
        f"fiscal year ({fys})."
    )


def filter_sponsors(
    sponsors: pd.DataFrame,
    family: str,
    state: str = STATE_ALL,
    min_cases: int = 5,
    consistent_only: bool = False,
) -> pd.DataFrame:
    """Ranked sponsors for one role group and state.

    Without consistent_only, keep groups with at least min_cases certified LCAs in total.
    With it, keep groups with at least min_cases in EVERY loaded fiscal year (each
    cases_fy{year} column), the same rule as reports/consistent_sponsors.csv (N = 10).
    """
    d = sponsors[(sponsors["family"] == family) & (sponsors["state"] == state)]
    if consistent_only:
        d = d[(d[year_columns(d)] >= min_cases).all(axis=1)]
    else:
        d = d[d["cases"] >= min_cases]
    d = d.sort_values(["cases", "display_name"], ascending=[False, True])
    return d.drop(columns=["family", "state"]).reset_index(drop=True)


# Filters shared by every page (session_state keys) and their URL parameter names.
FILTER_DEFAULTS = {
    "family": ANALYTICS_LABEL,
    "state": STATE_ALL,
    "min_cases": 5,
    "consistent": False,
}
URL_KEYS = {"family": "role", "state": "state", "min_cases": "min", "consistent": "consistent"}
MIN_CASES_OPTIONS = [1, 3, 5, 10, 25, 50]  # the select-slider steps for "Minimum certified LCAs"


def parse_query(params: dict, families: list[str], states: list[str]) -> dict:
    """URL query parameters -> validated filter values; anything unknown falls back to default.

    params: {'role': 'Operations Research', 'state': 'AZ', 'min': '3', 'consistent': '1'}.
    """
    out = dict(FILTER_DEFAULTS)
    family = params.get(URL_KEYS["family"])
    if family in families:
        out["family"] = family
    state = str(params.get(URL_KEYS["state"], "")).upper()
    if state in states:
        out["state"] = state
    try:
        n = int(params.get(URL_KEYS["min_cases"], ""))
        if n in MIN_CASES_OPTIONS:
            out["min_cases"] = n
    except ValueError:
        pass
    flag = str(params.get(URL_KEYS["consistent"], "")).lower()
    out["consistent"] = flag in {"1", "true", "yes"}
    return out


def encode_query(filters: dict) -> dict[str, str]:
    """Filter values -> URL query parameters (the inverse of parse_query)."""
    return {
        URL_KEYS["family"]: str(filters["family"]),
        URL_KEYS["state"]: str(filters["state"]),
        URL_KEYS["min_cases"]: str(int(filters["min_cases"])),
        URL_KEYS["consistent"]: "1" if filters["consistent"] else "0",
    }


PURPOSE = (
    "For international students researching which employers sponsor H-1B in analytics, OR, "
    "quant and IE roles. It shows filing history, not current job openings or legal advice."
)


def headline_numbers(sponsors: pd.DataFrame) -> list[dict]:
    """The Home page's three numbers, each with the Find sponsors filters that reproduce it.

    [{'label', 'note', 'value': int, 'filters': {family, state, min_cases, consistent}}, ...]
    """
    specs = [
        ("employers with a certified LCA", "Any H-1B role.", ALL_OCCUPATIONS_LABEL, 1, False),
        ("analytics employers", "At least 1 certified analytics LCA.", ANALYTICS_LABEL, 1, False),
        (
            "consistent analytics sponsors",
            "10+ certified analytics LCAs every year.",
            ANALYTICS_LABEL,
            10,
            True,
        ),
    ]
    out = []
    for label, note, family, n, consistent in specs:
        filters = {"family": family, "state": STATE_ALL, "min_cases": n, "consistent": consistent}
        value = len(filter_sponsors(sponsors, family, STATE_ALL, n, consistent))
        out.append({"label": label, "note": note, "value": value, "filters": filters})
    return out


def status_line(n: int, family: str, state: str, consistent_only: bool, min_cases: int) -> str:
    """'Showing **312 employers** · Analytics (combined) · Arizona · consistent only · min 5
    cases/year' (markdown)."""
    noun = "employer" if n == 1 else "employers"
    parts = [f"Showing **{n:,} {noun}**", family]
    parts.append("All states" if state == STATE_ALL else STATE_NAMES.get(state, state))
    if consistent_only:
        parts += ["consistent only", f"min {min_cases} LCAs/year"]
    else:
        parts.append(f"min {min_cases} LCAs")
    return " · ".join(parts)


def as_percent(df: pd.DataFrame) -> pd.DataFrame:
    """Share columns (0-1) -> *_pct columns (0-100) for display and download."""
    out = df.copy()
    for col in SHARE_COLS:
        if col in out.columns:
            out[col] = out[col] * 100
    return out.rename(
        columns={c: c.replace("share", "pct").replace("rate", "pct") for c in SHARE_COLS}
    )


CURATED_SETS = ROOT / "data" / "reference" / "curated_sets.csv"
CURATED_MIN_LCAS = 25  # curated sets list employers with at least this many target-role LCAs
ALIAS_PREFIX = "alias:"  # selectbox option values for member names: 'alias:<employer_norm>'


def top_groups(sponsors: pd.DataFrame, family: str, n: int = 8) -> list[str]:
    """parent_groups with the most certified LCAs in `family` (all states)."""
    d = sponsors[(sponsors["family"] == family) & (sponsors["state"] == STATE_ALL)]
    d = d.sort_values(["cases", "display_name"], ascending=[False, True])
    return d["parent_group"].head(n).tolist()


def load_curated_sets(path: Path, known_groups) -> dict[str, list[str]]:
    """{set_name: [parent_group, ...]} from curated_sets.csv, in file order.

    Groups missing from the published data (e.g. the demo data) are left out; a set with
    none left is dropped. tests/ checks that every entry exists in the real data.
    """
    if not Path(path).exists():
        return {}
    df = pd.read_csv(path, dtype=str)
    known = set(known_groups)
    out: dict[str, list[str]] = {}
    for row in df.itertuples():
        if row.parent_group in known:
            out.setdefault(row.set_name, []).append(row.parent_group)
    return out


TARGET_FAMILIES = FAMILY_ORDER[1:8]  # the seven target families (no rollups)


def plural(n: int, singular: str, plural_form: str | None = None) -> str:
    """plural(1, 'legal entity', 'legal entities') -> '1 legal entity'; 3 -> '3 legal entities'."""
    word = singular if n == 1 else (plural_form or singular + "s")
    return f"{n:,} {word}"


def curated_table(
    sponsors: pd.DataFrame, names: pd.Series, set_members: list[str], family: str
) -> pd.DataFrame:
    """One row per member of a curated set, for `family` across all states.

    Sorted by certified LCAs (largest first); members with no LCAs in `family` come last
    (alphabetical), with 0 LCAs, no metrics and note 'No <family> filings'.
    """
    d = sponsors[(sponsors["family"] == family) & (sponsors["state"] == STATE_ALL)]
    d = d.set_index("parent_group")
    out = pd.DataFrame({"parent_group": list(dict.fromkeys(set_members))})
    out = out.join(d.drop(columns=["family", "state", "display_name"]), on="parent_group")
    out.insert(1, "display_name", out["parent_group"].map(names).fillna(out["parent_group"]))
    counts = ["cases"] + year_columns(d)
    out[counts] = out[counts].fillna(0).astype(int)
    out["note"] = out["cases"].eq(0).map({True: f"No {family} filings", False: ""})
    out["_has"] = out["cases"] > 0
    out = out.sort_values(["_has", "cases", "display_name"], ascending=[False, False, True])
    return out.drop(columns="_has").reset_index(drop=True)


def lookup_options(
    sponsors: pd.DataFrame, groups: pd.DataFrame, members: pd.DataFrame, family: str
) -> tuple[list[str], dict[str, str]]:
    """Options for the Employer lookup selectbox, and their labels.

    Options are the parent_groups with certified LCAs in `family` (largest first), then one
    alias per member name of a multi-name group ('alias:MERRILL LYNCH', labelled
    'MERRILL LYNCH → Bank of America'), so typing a member name finds its group.
    """
    d = sponsors[(sponsors["family"] == family) & (sponsors["state"] == STATE_ALL)]
    d = d.sort_values(["cases", "display_name"], ascending=[False, True])
    keys = d["parent_group"].tolist()
    names = groups.set_index("parent_group")["display_name"]
    labels = {k: names.get(k, k) for k in keys}
    m = members[members["parent_group"].isin(set(keys))]
    multi = m.groupby("parent_group")["employer_norm"].transform("size") > 1
    for row in m[multi].sort_values(["parent_group", "employer_norm"]).itertuples():
        shown = labels[row.parent_group]
        if _key(row.employer_norm) != _key(shown):
            option = ALIAS_PREFIX + row.employer_norm
            if option not in labels:
                keys.append(option)
                labels[option] = f"{row.employer_norm} → {shown}"
    return keys, labels


def resolve_option(option: str | None, members: pd.DataFrame) -> str | None:
    """Selectbox option -> parent_group (aliases map to their member's group)."""
    if option is None or not option.startswith(ALIAS_PREFIX):
        return option
    norm = option[len(ALIAS_PREFIX) :]
    hit = members.loc[members["employer_norm"] == norm, "parent_group"]
    return hit.iloc[0] if len(hit) else None


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).casefold())


def search_groups(members: pd.DataFrame, query: str, limit: int = 50) -> list[str]:
    """Groups whose label or any member name contains `query` (case-insensitive).

    Largest groups first, so 'MERRILL' finds BANK OF AMERICA through its member names.
    """
    q = query.strip().upper()
    if not q:
        return []
    hit = members["parent_group"].str.upper().str.contains(q, regex=False) | members[
        "employer_norm"
    ].str.contains(q, regex=False)
    sizes = members[hit].groupby("parent_group")["rows"].sum()
    top = sizes.reset_index().sort_values(["rows", "parent_group"], ascending=[False, True])
    return top["parent_group"].head(limit).tolist()


def readme_sections(headings: list[str], text: str | None = None) -> dict[str, str]:
    """{heading: markdown body} for '## heading' sections of the README.

    Raises KeyError if a heading is missing, so renaming one breaks a test, not the app.
    """
    text = README.read_text() if text is None else text
    parts = re.split(r"^## +(.+?)\s*$", text, flags=re.M)
    found = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    missing = [h for h in headings if h not in found]
    if missing:
        raise KeyError(f"README sections not found: {missing}")
    return {h: found[h] for h in headings}


def pct_change_table(trends: pd.DataFrame) -> pd.DataFrame:
    """Certified LCAs in the first and last loaded year per family, and the % change.

    Columns: family, first, last, pct_change (e.g. 0.351 for +35.1%); largest change first.
    """
    years = sorted(trends["fiscal_year"].unique())
    wide = trends.pivot_table(index="family", columns="fiscal_year", values="cases", aggfunc="sum")
    out = pd.DataFrame(
        {"first": wide[years[0]], "last": wide[years[-1]]}, index=wide.index
    ).reset_index()
    out["pct_change"] = (out["last"] - out["first"]) / out["first"].where(out["first"] > 0)
    return out.sort_values(["pct_change", "family"], ascending=[False, True]).reset_index(drop=True)


def plain(markdown: str) -> str:
    """README text without markdown code and bold markers, for plain-language boxes."""
    return markdown.replace("`", "").replace("**", "")


def readme_bullet(bold_start: str, text: str | None = None) -> str:
    """The README bullet that starts with '- **<bold_start>', joined into one paragraph."""
    text = README.read_text() if text is None else text
    pattern = rf"^- \*\*{re.escape(bold_start)}.*?(?=^- |^#|\Z)"
    m = re.search(pattern, text, flags=re.M | re.S)
    if not m:
        raise KeyError(f"README bullet not found: {bold_start}")
    return " ".join(m.group(0)[2:].split())
