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
    NAME_SIMILARITY,
    PLACEHOLDER_FEINS,
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


def primary_feins(df: pd.DataFrame) -> pd.Series:
    """employer_norm -> its most common usable FEIN (ties: smallest FEIN)."""
    if "EMPLOYER_FEIN" not in df.columns:
        return pd.Series(dtype="object")
    fein = df["EMPLOYER_FEIN"].astype("string").str.strip()
    usable = fein.str.match(FEIN_PATTERN).fillna(False) & ~fein.isin(PLACEHOLDER_FEINS)
    d = pd.DataFrame({"employer_norm": df["employer_norm"], "fein": fein})[usable]
    counts = d.groupby(["employer_norm", "fein"]).size().rename("n").reset_index()
    counts = counts.sort_values(["employer_norm", "n", "fein"], ascending=[True, False, True])
    return counts.drop_duplicates("employer_norm").set_index("employer_norm")["fein"].astype(str)


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

    Columns: parent_group, employer_norm, primary_fein, rows, link, group_rows, n_entities.
    link lists the edge types that touch the name ('name', 'fein', 'override'), or 'none'.
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
    # Default label: the member with the most rows (ties: alphabetical).
    best = (
        out.sort_values(["rows", "employer_norm"], ascending=[False, True])
        .drop_duplicates("root")
        .set_index("root")["employer_norm"]
    )
    out["parent_group"] = [label_of_root.get(r, best[r]) for r in out["root"]]
    out["link"] = ["+".join(sorted(links[n])) or "none" for n in out["employer_norm"]]
    g = out.groupby("parent_group")
    out["group_rows"] = g["rows"].transform("sum")
    out["n_entities"] = g["employer_norm"].transform("size")
    out = out.sort_values(
        ["group_rows", "parent_group", "rows", "employer_norm"],
        ascending=[False, True, False, True],
    )
    cols = ["parent_group", "employer_norm", "primary_fein", "rows", "link"]
    return out[cols + ["group_rows", "n_entities"]].reset_index(drop=True)


def add_parent_group(df: pd.DataFrame, groups: pd.DataFrame) -> pd.DataFrame:
    """Add a parent_group column to LCA rows using build_parent_groups output."""
    mapping = groups.set_index("employer_norm")["parent_group"]
    return df.assign(parent_group=df["employer_norm"].map(mapping))


def risky_name_merges(groups: pd.DataFrame) -> pd.DataFrame:
    """Members of groups whose names have 2+ different primary FEINs and no override.

    FEIN edges only join names with the same primary FEIN, so such groups are held
    together by name edges alone, which is worth a look by eye.
    """
    g = groups.groupby("parent_group")
    has_override = g["link"].transform(lambda s: s.str.contains("override").any())
    n_feins = g["primary_fein"].transform("nunique")
    return groups[~has_override & (n_feins >= 2)].reset_index(drop=True)
