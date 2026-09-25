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


def test_every_page_runs_and_shows_the_footer(app):
    assert app.title[0].value == "Find sponsors"
    assert footer(app).startswith("Source: U.S. DOL OFLC LCA disclosure data, FY2024–FY2025.")
    for page in PAGES:
        app.switch_page(page).run()
        assert not app.exception, page
        assert "Not legal or immigration advice." in footer(app), page


def test_find_sponsors_table_and_consistent_checkbox(app):
    table = app.dataframe[0].value
    assert table.columns[:2].tolist() == ["display_name", "cases"]
    app.checkbox[0].check().run()
    assert not app.exception
    assert len(app.dataframe[0].value) <= len(table)


def test_employer_lookup_search(app):
    app.switch_page("views/employer_lookup.py").run()
    app.text_input[0].input("acme").run()
    assert not app.exception
    assert app.selectbox[0].value == "ACME ANALYTICS"
    assert int(app.metric[0].value.replace(",", "")) > 0
    app.text_input[0].input("no such employer").run()
    assert app.warning and "Not legal" in footer(app)
