"""The shared formatting helpers in app/ui.py."""

import tomllib

import pandas as pd
import pytest

import ui
from h1b.config import ROOT


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
    # Colors cannot depend on the theme (st.context.theme lags a theme switch by one rerun),
    # so every color must work on both backgrounds.
    for mode, bg in BACKGROUNDS.items():
        bars = [*ui.YEAR_RAMP, ui.SERIES_BLUE, ui.REFERENCE_GRAY, *ui.LEVEL_COLORS.values()]
        for color in bars:
            assert contrast(color, bg) >= 3, (mode, color)  # graphics: 3:1
        # MUTED_GRAY is only used for large text (bold, >= 18.7 px): WCAG threshold 3:1.
        assert contrast(ui.MUTED_GRAY, bg) >= 3, mode


def test_year_ramp_uses_the_ramp_endpoints():
    assert ui.year_ramp([2024, 2025]) == [ui.YEAR_RAMP[0], ui.YEAR_RAMP[-1]]
    assert ui.year_ramp([2025]) == [ui.SERIES_BLUE]


def test_primary_color_is_per_theme_so_the_theme_chooser_stays():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
    theme = config.get("theme", {})
    # A primaryColor directly under [theme] hides the Light / Dark / System chooser.
    assert "primaryColor" not in theme
    for mode, bg in BACKGROUNDS.items():
        primary = theme[mode]["primaryColor"]
        assert contrast(primary, bg) >= 3, mode  # widgets (slider, checkbox) vs background
        assert contrast(primary, "#ffffff") >= 4.5, mode  # white text on primary buttons


def text_marks(spec) -> list[dict]:
    """Every mark definition of type 'text' in an Altair/Vega-Lite spec (any nesting)."""
    found = []
    if isinstance(spec, dict):
        mark = spec.get("mark")
        if isinstance(mark, dict) and mark.get("type") == "text":
            found.append(mark)
        for value in spec.values():
            found += text_marks(value)
    elif isinstance(spec, list):
        for value in spec:
            found += text_marks(value)
    return found


def test_pct_change_labels_are_wcag_large_text():
    d = pd.DataFrame(
        {
            "family": ["A", "B", "Ref"],
            "first": [100, 200, 300],
            "last": [135, 180, 350],
            "pct_change": [0.35, -0.10, 0.17],
        }
    )
    marks = text_marks(ui.pct_change_chart(d, "Ref", 2024, 2025).to_dict())
    assert len(marks) == 2  # positive and negative labels
    for mark in marks:
        # Large text = at least 14 pt (18.7 px) and bold; its contrast threshold is 3:1.
        assert mark["fontSize"] >= 18.7 and mark["fontWeight"] == "bold"
        assert mark["color"] == ui.MUTED_GRAY
        for bg in BACKGROUNDS.values():
            assert contrast(mark["color"], bg) >= 3


def test_fiscal_years_read_clearly_apart():
    # The two year colors differ by at least 2:1 luminance contrast (1.48:1 before).
    assert contrast(ui.YEAR_RAMP[0], ui.YEAR_RAMP[-1]) >= 2
