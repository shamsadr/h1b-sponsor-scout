"""Parent-company grouping: link employer_norm values that share a FEIN or a name key.

Nodes are employer_norm values. Two nodes are linked when
  - they have the same name key (employer_norm without generic words and spaces), or
  - they share a primary FEIN (the FEIN a name uses most), unless that FEIN is a
    placeholder, malformed, or shared by too many unrelated names.
Groups are the connected components. employer_overrides.csv then adds manual merges
and splits. Every tie is broken alphabetically, so row order never changes the result.
"""

import re
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from h1b.config import (
    FEIN_PATTERN,
    GENERIC_NAME_TOKENS,
    MAX_UNRELATED_PER_FEIN,
    MIN_NAME_KEY_CHARS,
    MIN_NAME_KEY_TOKENS,
    NAME_SIM_WARN,
    NAME_SIMILARITY,
    PERSON_SUFFIXES,
    PLACEHOLDER_FEINS,
    TITLE_WORDS,
)

OVERRIDE_COLS = ["action", "employer_norm", "parent_group", "note"]


class _UnionFind:
    """Minimal union-find; each root is the alphabetically smallest member."""

    def __init__(self, items: list[str]):
        self.parent = {x: x for x in items}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        lo, hi = sorted((self.find(a), self.find(b)))
        self.parent[hi] = lo


def name_key(norm: str) -> str:
    """'GOLDMAN SACHS SERVICES' -> 'GOLDMANSACHS'; '' if too generic to link on.

    Drops GENERIC_NAME_TOKENS and a trailing AND (from '& Co.'), then removes spaces
    so 'EVEREST CONSULTING' and 'EVERESTCONSULTING' match. Keys with fewer than
    MIN_NAME_KEY_TOKENS words or MIN_NAME_KEY_CHARS letters return '' (so a one-word
    spelling like 'EVERESTCONSULTING' can only join its group through a FEIN).
    """
    s = re.sub(r"\bU S(?: A)?\b", "US", norm)
    s = re.sub(r"\bN A\b", "NA", s)
    tokens = [t for t in s.split() if t not in GENERIC_NAME_TOKENS]
    while tokens and tokens[-1] == "AND":
        tokens.pop()
    key = "".join(tokens)
    if len(tokens) < MIN_NAME_KEY_TOKENS or len(key) < MIN_NAME_KEY_CHARS:
        return ""
    return key


def _mode_per_name(names: pd.Series, values: pd.Series) -> pd.Series:
    """employer_norm -> its most common non-null value (ties: smallest value)."""
    d = pd.DataFrame({"employer_norm": names, "v": values}).dropna()
    counts = d.groupby(["employer_norm", "v"]).size().rename("n").reset_index()
    counts = counts.sort_values(["employer_norm", "n", "v"], ascending=[True, False, True])
    return counts.drop_duplicates("employer_norm").set_index("employer_norm")["v"].astype(str)


def primary_feins(df: pd.DataFrame) -> pd.Series:
    """employer_norm -> its most common usable FEIN (ties: smallest FEIN)."""
    if "EMPLOYER_FEIN" not in df.columns:
        return pd.Series(dtype="object")
    fein = df["EMPLOYER_FEIN"].astype("string").str.strip()
    usable = fein.str.match(FEIN_PATTERN).fillna(False) & ~fein.isin(PLACEHOLDER_FEINS)
    return _mode_per_name(df["employer_norm"], fein.where(usable))


def primary_states(df: pd.DataFrame) -> pd.Series:
    """employer_norm -> its most common EMPLOYER_STATE (ties: alphabetical)."""
    if "EMPLOYER_STATE" not in df.columns:
        return pd.Series(dtype="object")
    state = df["EMPLOYER_STATE"].astype("string").str.strip().str.upper().replace("", pd.NA)
    return _mode_per_name(df["employer_norm"], state)


def _related(a: str, b: str) -> bool:
    """Same first word, or similar spelling (catches typos like PRICEWATEHOUSECOOPERS)."""
    return a.split()[0] == b.split()[0] or SequenceMatcher(None, a, b).ratio() >= NAME_SIMILARITY


def count_unrelated(names: list[str]) -> int:
    """Number of clusters of related names (1 = all variants of one name)."""
    names = sorted(names)
    uf = _UnionFind(names)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if _related(a, b):
                uf.union(a, b)
    return len({uf.find(n) for n in names})


def load_overrides(path: Path | None) -> pd.DataFrame:
    """Read employer_overrides.csv (empty if missing). action is 'merge' or 'split'.

    merge: join employer_norm to every other row with the same parent_group label.
    split: give employer_norm no automatic edges (it stands alone, or joins parent_group).
    """
    if path is None or not Path(path).exists():
        return pd.DataFrame(columns=OVERRIDE_COLS)
    ov = pd.read_csv(path, dtype=str).reindex(columns=OVERRIDE_COLS)
    for c in ["action", "employer_norm", "parent_group"]:
        ov[c] = ov[c].str.strip()
    bad = ov[~ov["action"].isin({"merge", "split"})]
    if len(bad):
        raise ValueError(f"{path}: action must be 'merge' or 'split', got {bad['action'].tolist()}")
    no_label = ov[(ov["action"] == "merge") & ov["parent_group"].isna()]
    if len(no_label):
        raise ValueError(
            f"{path}: merge rows need a parent_group: {no_label['employer_norm'].tolist()}"
        )
    return ov


def build_parent_groups(df: pd.DataFrame, overrides: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per employer_norm with its parent_group and how it was linked.

    Columns: parent_group, employer_norm, primary_fein, primary_state, rows, link,
    group_rows, n_entities. link lists the edge types that touch the name ('name', 'fein',
    'override'), or 'none'. A group without overrides is labelled by its largest name; if
    that name equals an override label, its FEIN is appended ('CITI (56-1928771)').
    """
    ov = overrides if overrides is not None else pd.DataFrame(columns=OVERRIDE_COLS)
    rows = df["employer_norm"].value_counts()
    nodes = sorted(rows.index)
    uf = _UnionFind(nodes)
    links: dict[str, set[str]] = {n: set() for n in nodes}
    split = set(ov.loc[ov["action"] == "split", "employer_norm"])
    auto = [n for n in nodes if n and n not in split]  # never link blank names

    def link_all(members: list[str], kind: str) -> None:
        for m in members[1:]:
            uf.union(members[0], m)
        for m in members:
            links[m].add(kind)

    # 1) Name edges.
    keys = pd.Series({n: name_key(n) for n in auto}, dtype="object")
    for _, members in keys[keys != ""].groupby(keys[keys != ""]):
        if len(members) > 1:
            link_all(sorted(members.index), "name")

    # 2) FEIN edges: primary FEIN only, and not when it covers many unrelated names.
    primary = primary_feins(df)
    p = primary[primary.index.isin(auto)]
    for _, members in p.groupby(p):
        names = sorted(members.index)
        if len(names) > 1 and count_unrelated(names) <= MAX_UNRELATED_PER_FEIN:
            link_all(names, "fein")

    # 3) Manual merges (and splits that name a parent_group).
    labelled = ov.dropna(subset=["parent_group"])
    labelled = labelled[labelled["employer_norm"].isin(rows.index)]
    for _, grp in labelled.groupby("parent_group"):
        link_all(sorted(grp["employer_norm"]), "override")
    label_of_root: dict[str, str] = {}
    for r in labelled.itertuples():
        root = uf.find(r.employer_norm)
        if label_of_root.setdefault(root, r.parent_group) != r.parent_group:
            raise ValueError(
                f"Overrides '{label_of_root[root]}' and '{r.parent_group}' ended up in one group; "
                "add a split row for the name that joins them."
            )

    out = pd.DataFrame({"employer_norm": nodes, "rows": rows.reindex(nodes).to_numpy()})
    out["root"] = out["employer_norm"].map(uf.find)
    out["primary_fein"] = out["employer_norm"].map(primary)
    out["primary_state"] = out["employer_norm"].map(primary_states(df))
    # Default label: the member with the most rows (ties: alphabetical).
    best = (
        out.sort_values(["rows", "employer_norm"], ascending=[False, True])
        .drop_duplicates("root")
        .set_index("root")["employer_norm"]
    )
    taken = set(label_of_root.values())

    def label(root: str) -> str:
        if root in label_of_root:
            return label_of_root[root]
        name = best[root]
        return f"{name} ({primary.get(name) or 'no FEIN'})" if name in taken else name

    out["parent_group"] = [label(r) for r in out["root"]]
    out["link"] = ["+".join(sorted(links[n])) or "none" for n in out["employer_norm"]]
    g = out.groupby("parent_group")
    out["group_rows"] = g["rows"].transform("sum")
    out["n_entities"] = g["employer_norm"].transform("size")
    out = out.sort_values(
        ["group_rows", "parent_group", "rows", "employer_norm"],
        ascending=[False, True, False, True],
    )
    cols = ["parent_group", "employer_norm", "primary_fein", "primary_state", "rows", "link"]
    return out[cols + ["group_rows", "n_entities"]].reset_index(drop=True)


def add_parent_group(df: pd.DataFrame, groups: pd.DataFrame) -> pd.DataFrame:
    """Add a parent_group column to LCA rows using build_parent_groups output."""
    mapping = groups.set_index("employer_norm")["parent_group"]
    return df.assign(parent_group=df["employer_norm"].map(mapping))


def looks_like_person_or_title(norm: str) -> bool:
    """'SYSTEMS ANALYST' or 'JOHN SMITH MD': a job title or a person typed as the employer."""
    tokens = norm.split()
    if not tokens:
        return False
    return tokens[-1] in PERSON_SUFFIXES or (len(tokens) <= 3 and tokens[-1] in TITLE_WORDS)


def _group_mode(m: pd.DataFrame, col: str) -> pd.Series:
    """Per row of m: the value of `col` that covers the most rows in its parent_group."""
    w = m.dropna(subset=[col]).groupby(["parent_group", col])["rows"].sum().reset_index()
    w = w.sort_values(["parent_group", "rows", col], ascending=[True, False, True])
    top = w.drop_duplicates("parent_group").set_index("parent_group")[col]
    return m["parent_group"].map(top)


def merge_review(groups: pd.DataFrame) -> pd.DataFrame:
    """One row per member of a multi-member group, with warning signals to review by eye.

    risk_flags counts: name_sim < NAME_SIM_WARN (difflib ratio to the group label);
    linked by name only while its primary FEIN differs from the group's main FEIN;
    primary state differs from the group's main state; name looks like a person or title.
    Members placed by employer_overrides.csv are reviewed=True with risk_flags=0; their
    signal columns are still filled in.
    """
    m = groups[groups["n_entities"] > 1].copy()
    main_fein, main_state = _group_mode(m, "primary_fein"), _group_mode(m, "primary_state")
    m["row_share"] = m["rows"] / m["group_rows"]
    m["name_sim"] = [
        round(SequenceMatcher(None, n, g).ratio(), 3)
        for n, g in zip(m["employer_norm"], m["parent_group"], strict=True)
    ]
    m["state_mismatch"] = (
        m["primary_state"].notna() & main_state.notna() & (m["primary_state"] != main_state)
    )
    m["looks_like_person_or_title"] = m["employer_norm"].map(looks_like_person_or_title)
    name_only = (
        m["link"].eq("name")
        & m["primary_fein"].notna()
        & main_fein.notna()
        & (m["primary_fein"] != main_fein)
    )
    m["reviewed"] = m["link"].str.contains("override")
    flags = (
        (m["name_sim"] < NAME_SIM_WARN).astype(int)
        + name_only.astype(int)
        + m["state_mismatch"].astype(int)
        + m["looks_like_person_or_title"].astype(int)
    )
    m["risk_flags"] = flags.where(~m["reviewed"], 0)
    m = m.sort_values(
        ["risk_flags", "rows", "parent_group", "employer_norm"],
        ascending=[False, False, True, True],
    )
    cols = [
        "parent_group",
        "employer_norm",
        "rows",
        "row_share",
        "primary_fein",
        "primary_state",
        "link",
        "name_sim",
        "state_mismatch",
        "looks_like_person_or_title",
        "reviewed",
        "risk_flags",
        "n_entities",
    ]
    return m[cols].reset_index(drop=True)
