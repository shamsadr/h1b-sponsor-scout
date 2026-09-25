"""The shared formatting helpers in app/ui.py."""

import pandas as pd
import pytest

import ui


@pytest.mark.parametrize(
    "value, expected",
    [
        (137900.4, "$137,900"),
        (137900.5, "$137,901"),  # nearest dollar, halves round up
        (88000, "$88,000"),
        (0, "$0"),
        (None, "—"),
        (float("nan"), "—"),
        (pd.NA, "—"),
    ],
)
def test_fmt_money(value, expected):
    assert ui.fmt_money(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (0.844, "84%"),
        (0.845, "85%"),
        (1.0, "100%"),
        (0.0, "0%"),  # a true zero is a value, not missing
        (None, "—"),
        (float("nan"), "—"),
    ],
)
def test_fmt_pct(value, expected):
    assert ui.fmt_pct(value) == expected


@pytest.mark.parametrize("value, expected", [(1423, "1,423"), (7, "7"), (0, "0"), (None, "—")])
def test_fmt_count(value, expected):
    assert ui.fmt_count(value) == expected


def test_column_configs_use_the_shared_formats():
    assert ui.money_col("Wage")["type_config"]["format"] == "$%,.0f"
    assert ui.pct_col("Share")["type_config"]["format"] == "%.0f%%"
    assert ui.count_col("Cases")["type_config"]["format"] == "localized"
