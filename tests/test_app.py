"""Smoke test: every app page runs on a demo publish without an exception."""

import pytest
from streamlit.testing.v1 import AppTest

from h1b.config import DEMO_DIR, ROOT
from h1b.pipeline import process_files, publish

APP = str(ROOT / "app" / "streamlit_app.py")
PAGES = ["views/employer_lookup.py", "views/trends.py", "views/methodology.py"]


@pytest.fixture(scope="module")
def demo_app_data(tmp_path_factory):
    processed = tmp_path_factory.mktemp("processed")
    for fy in (2024, 2025):
        process_files(
            [DEMO_DIR / f"lca_demo_FY{fy}.csv"], fy, out_dir=processed, interim_dir=processed / "i"
        )
    out = tmp_path_factory.mktemp("app")
    publish(processed_dir=processed, out_dir=out)
    return out


@pytest.fixture
def app(demo_app_data, monkeypatch):
    monkeypatch.setenv("H1B_APP_DATA", str(demo_app_data))
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    return at


def footer(at) -> str:
    return at.caption[-1].value


def status(at) -> str:
    """The 'Showing N employers · ...' line on Find sponsors."""
    return next(m.value for m in at.markdown if m.value.startswith("Showing"))


def test_every_page_runs_and_shows_the_footer(app):
    assert app.title[0].value == "Find sponsors"
    assert footer(app).startswith("Source: U.S. DOL OFLC LCA disclosure data, FY2024–FY2025.")
    for page in PAGES:
        app.switch_page(page).run()
        assert not app.exception, page
        assert "Not legal or immigration advice." in footer(app), page


def test_find_sponsors_defaults_status_line_and_columns(app):
    assert app.selectbox[0].value == "Analytics (combined)"
    assert app.slider[0].value == 5
    assert status(app).startswith("Showing **")
    table = app.dataframe[0].value
    assert "parent_group" not in table.columns  # users never see the internal key
    app.checkbox[0].check().run()
    assert not app.exception
    assert "consistent only · min 5 cases/year" in status(app)


def test_find_sponsors_empty_state_and_reset(app):
    app.slider[0].set_value(100).run()
    app.checkbox[0].check().run()
    assert not app.exception
    assert status(app).startswith("Showing **0 employers**")
    assert "No employers match these filters" in app.info[0].value
    assert not app.dataframe
    [b for b in app.button if b.label == "Reset filters"][0].click().run()
    assert not app.exception
    assert app.slider[0].value == 5 and app.checkbox[0].value is False
    assert len(app.dataframe) == 1
    assert "Not legal or immigration advice." in footer(app)


def test_employer_lookup_search(app):
    app.switch_page("views/employer_lookup.py").run()
    app.text_input[0].input("acme").run()
    assert not app.exception
    assert app.selectbox[0].value == "ACME ANALYTICS"
    assert int(app.metric[0].value.replace(",", "")) > 0
    app.text_input[0].input("no such employer").run()
    assert app.warning and "Not legal" in footer(app)
