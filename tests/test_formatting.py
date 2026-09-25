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


BACKGROUNDS = {"light": "#ffffff", "dark": "#0e1117"}  # Streamlit's default themes


def contrast(a: str, b: str) -> float:
    """WCAG 2 contrast ratio between two hex colors."""

    def lum(h: str) -> float:
        c = [int(h[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    hi, lo = sorted([lum(a), lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_colors_clear_wcag_contrast_in_both_themes():
    for mode, bg in BACKGROUNDS.items():
        for color in ui.YEAR_RAMPS[mode]:
            assert contrast(color, bg) >= 3, (mode, color)  # graphics: 3:1
        for color in [ui.SERIES_BLUE, ui.REFERENCE_GRAY, *ui.LEVEL_COLORS.values()]:
            assert contrast(color, bg) >= 3, (mode, color)
        assert contrast(ui.MUTED_TEXT[mode], bg) >= 4.5, mode  # text: 4.5:1


def test_year_ramp_uses_the_theme_ramp_endpoints():
    light = ui.YEAR_RAMPS["light"]
    assert ui.year_ramp([2024, 2025]) == [light[0], light[-1]]  # no theme in tests -> light
    assert ui.year_ramp([2025]) == [ui.SERIES_BLUE]
