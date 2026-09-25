import pandas as pd
import pytest

from h1b.groups import (
    build_parent_groups,
    count_unrelated,
    load_overrides,
    name_key,
    primary_feins,
    risky_name_merges,
)


def lca(*specs: tuple[str, str | None, int]) -> pd.DataFrame:
    """LCA rows from (employer_norm, EMPLOYER_FEIN, n_rows) specs."""
    rows = [(name, fein) for name, fein, n in specs for _ in range(n)]
    return pd.DataFrame(rows, columns=["employer_norm", "EMPLOYER_FEIN"])


def group_of(groups: pd.DataFrame) -> dict[str, str]:
    return dict(zip(groups["employer_norm"], groups["parent_group"], strict=True))


def overrides(*rows: tuple[str, str, str | None]) -> pd.DataFrame:
    return pd.DataFrame(
        [(a, n, g, "") for a, n, g in rows],
        columns=["action", "employer_norm", "parent_group", "note"],
    )


@pytest.mark.parametrize(
    "norm, key",
    [
        ("GOLDMAN SACHS SERVICES", "GOLDMANSACHS"),
        ("GOLDMAN SACHS AND", "GOLDMANSACHS"),  # 'Goldman Sachs & Co.' after normalizing
        ("AMAZON DEVELOPMENT CENTER U S", "AMAZONDEVELOPMENTCENTER"),
        ("MCKINSEY AND UNITEDSTATES", "MCKINSEYANDUNITEDSTATES"),
        ("GLOBAL SERVICES", ""),  # one token left -> too generic
        ("MICROSOFT", ""),  # one token
        ("EVERESTCONSULTING GROUP", ""),  # one token once GROUP is dropped
        ("U S STEEL", ""),  # US is generic -> one token left
        ("AB CD", ""),  # under 6 characters
    ],
)
def test_name_key(norm, key):
    assert name_key(norm) == key


def test_generic_names_stay_separate():
    groups = build_parent_groups(
        lca(("GLOBAL SERVICES", "11-1111111", 5), ("GLOBAL GROUP", None, 5))
    )
    got = group_of(groups)
    assert got["GLOBAL SERVICES"] != got["GLOBAL GROUP"]


def test_name_edge_joins_spelling_variants_without_fein():
    df = lca(("MCKINSEY AND UNITED STATES", None, 3), ("MCKINSEY AND UNITEDSTATES", None, 1))
    assert len(set(group_of(build_parent_groups(df)).values())) == 1  # older years: no FEIN


def test_shared_primary_fein_merges_and_different_feins_do_not():
    df = lca(
        ("GAVS TECHNOLOGIES", "11-1111111", 10),
        ("NEUREALM", "11-1111111", 4),  # renamed, same FEIN
        ("OTHERCO ANALYTICS", "22-2222222", 5),
    )
    got = group_of(build_parent_groups(df))
    assert got["NEUREALM"] == got["GAVS TECHNOLOGIES"] == "GAVS TECHNOLOGIES"  # most rows
    assert got["OTHERCO ANALYTICS"] == "OTHERCO ANALYTICS"


@pytest.mark.parametrize("fein", ["12-3456789", "1231231231", "", None])
def test_placeholder_and_malformed_feins_never_link(fein):
    df = lca(("AMAZON COM SERVICES", fein, 5), ("ACME WIDGETS", fein, 5))
    got = group_of(build_parent_groups(df))
    assert got["AMAZON COM SERVICES"] != got["ACME WIDGETS"]


def test_fein_shared_by_many_unrelated_names_is_ignored_but_typos_still_merge():
    many = lca(
        ("UNIVERSITY OF X", "33-3333333", 5),
        ("STATE ENERGY COMMISSION", "33-3333333", 5),
        ("CITY SCHOOLS", "33-3333333", 5),  # 3 unrelated clusters > 2
    )
    assert build_parent_groups(many)["parent_group"].nunique() == 3

    typos = lca(
        ("PRICEWATERHOUSECOOPERS ADVISORY", "44-4444444", 50),
        ("PRICEWATEHOUSECOOPERS ADVISORY", "44-4444444", 2),  # first word differs, fuzzy match
        ("PWC PARTNERS", "44-4444444", 1),  # second cluster: 2 <= cap
    )
    assert build_parent_groups(typos)["parent_group"].nunique() == 1


def test_count_unrelated():
    assert count_unrelated(["ACME ANALYTICS", "ACME DATA", "ACMEE ANALYTICS"]) == 1
    assert count_unrelated(["ACME ANALYTICS", "ZETA LABS"]) == 2


def test_stray_fein_on_a_few_rows_does_not_bridge_companies():
    df = lca(
        ("TECH GIANT", "55-5555555", 50),
        ("KEYWEB TECHNOLOGIES", "66-6666666", 49),
        ("KEYWEB TECHNOLOGIES", "55-5555555", 1),  # a law firm's or typo'd FEIN on one filing
    )
    assert primary_feins(df)["KEYWEB TECHNOLOGIES"] == "66-6666666"
    got = group_of(build_parent_groups(df))
    assert got["KEYWEB TECHNOLOGIES"] != got["TECH GIANT"]


def test_override_merge_joins_unlinked_names_under_its_label():
    df = lca(("AMAZON COM SERVICES", "11-1111111", 9), ("AMAZON WEB SERVICES", "22-2222222", 3))
    ov = overrides(
        ("merge", "AMAZON COM SERVICES", "AMAZON"),
        ("merge", "AMAZON WEB SERVICES", "AMAZON"),
        ("merge", "NOT IN DATA", "AMAZON"),  # ignored
    )
    groups = build_parent_groups(df, ov)
    assert set(group_of(groups).values()) == {"AMAZON"}
    assert set(groups["link"]) == {"override"}
    assert risky_name_merges(groups).empty


def test_override_split_detaches_a_name_from_fein_and_name_edges():
    df = lca(
        ("UTAH SYSTEM OF HIGHER EDUCATION", "87-6000545", 4),
        ("UTAH DEPARTMENT OF COMMERCE", "87-6000545", 1),
        ("MY529", "87-6000545", 1),
    )
    assert build_parent_groups(df)["parent_group"].nunique() == 1  # linked by the FEIN
    got = group_of(build_parent_groups(df, overrides(("split", "MY529", None))))
    assert got["MY529"] == "MY529"
    assert got["UTAH DEPARTMENT OF COMMERCE"] == "UTAH SYSTEM OF HIGHER EDUCATION"


def test_conflicting_override_labels_in_one_group_raise():
    df = lca(("ACME ANALYTICS", "11-1111111", 2), ("ACME ANALYTICS US", "11-1111111", 2))
    ov = overrides(("merge", "ACME ANALYTICS", "A"), ("merge", "ACME ANALYTICS US", "B"))
    with pytest.raises(ValueError, match="split"):
        build_parent_groups(df, ov)


def test_load_overrides_missing_file_and_bad_action(tmp_path):
    assert load_overrides(tmp_path / "nope.csv").empty
    bad = tmp_path / "ov.csv"
    bad.write_text("action,employer_norm,parent_group,note\nmerj,ACME,ACME,\n")
    with pytest.raises(ValueError, match="merge"):
        load_overrides(bad)


def test_label_is_member_with_most_rows_then_alphabetical():
    df = lca(("BETA ANALYTICS", "11-1111111", 3), ("BETA ANALYTICS US", "11-1111111", 3))
    assert set(group_of(build_parent_groups(df)).values()) == {"BETA ANALYTICS"}


def test_grouping_is_order_independent():
    df = lca(
        ("GOLDMAN SACHS AND", "11-1111111", 7),
        ("GOLDMAN SACHS SERVICES", "22-2222222", 7),
        ("GOLDMAN SACHS TRUST NA", "11-1111111", 1),
        ("ACME ANALYTICS", "33-3333333", 4),
        ("ACME ANALYTICS US", None, 4),
        ("ZETA LABS", "33-3333333", 2),
        ("MY529", "44-4444444", 1),
    )
    ov = overrides(("split", "MY529", None))
    expected = build_parent_groups(df, ov)
    for seed in range(5):
        shuffled = df.sample(frac=1, random_state=seed).reset_index(drop=True)
        pd.testing.assert_frame_equal(build_parent_groups(shuffled, ov), expected)


def test_risky_name_merges_flags_name_only_joins_across_feins():
    df = lca(
        ("GOLDMAN SACHS AND", "11-1111111", 7),
        ("GOLDMAN SACHS SERVICES", "22-2222222", 5),  # name edge, different FEIN
        ("TESLA MOTORS", "33-3333333", 5),
        ("TESLA MOTORS US", "33-3333333", 1),  # name edge, same FEIN -> not risky
    )
    risky = risky_name_merges(build_parent_groups(df))
    assert set(risky["employer_norm"]) == {"GOLDMAN SACHS AND", "GOLDMAN SACHS SERVICES"}
