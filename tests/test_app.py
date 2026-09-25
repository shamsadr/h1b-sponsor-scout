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
    assert app.select_slider[0].value == 5
    assert status(app).startswith("Showing **")
    table = app.dataframe[0].value
    assert "parent_group" not in table.columns  # users never see the internal key
    app.checkbox[0].check().run()
    assert not app.exception
    assert "consistent only · min 5 LCAs/year" in status(app)


def test_find_sponsors_empty_state_and_reset(app):
    app.select_slider[0].set_value(50).run()
    app.checkbox[0].check().run()
    assert not app.exception
    assert status(app).startswith("Showing **0 employers**")
    assert "No employers match these filters" in app.info[0].value
    assert not app.dataframe
    [b for b in app.button if b.label == "Reset filters"][0].click().run()
    assert not app.exception
    assert app.select_slider[0].value == 5 and app.checkbox[0].value is False
    assert len(app.dataframe) == 1
    assert "Not legal or immigration advice." in footer(app)


def lookup(app):
    app.switch_page("views/employer_lookup.py").run()
    assert not app.exception
    return app


def employer_box(app):
    return next(sb for sb in app.selectbox if sb.label == "Employer")


def test_employer_lookup_starts_empty_with_quick_picks(app):
    lookup(app)
    assert "Pick a quick pick above" in app.info[0].value
    top = app.get("button_group")[0]
    assert len(top.options) == 5  # the 5 demo employers (top 8 when there are more)
    assert "Not legal or immigration advice." in footer(app)


def test_quick_pick_opens_a_summary_card(app):
    lookup(app)
    app.get("button_group")[0].set_value("ACME ANALYTICS").run()
    assert not app.exception
    assert app.subheader[0].value == "Acme Analytics"
    labels = [m.label for m in app.metric]
    assert labels == ["Certified LCAs", "Years active", "Median offered wage", "Level II+ share"]
    assert app.metric[2].value.startswith("$")
    assert app.query_params["employer"] == ["Acme Analytics"]
    app.switch_page("views/trends.py").run()
    assert "employer" not in app.query_params  # only Employer lookup keeps it


def test_selectbox_and_row_click_handoff_open_the_employer(app):
    lookup(app)
    employer_box(app).set_value("DESERT HEALTH SYSTEM").run()
    assert not app.exception and app.subheader[0].value == "Desert Health System"
    # Find sponsors' row click stores the group, then switches page (ui.open_employer).
    app.session_state["employer"] = "BLUE RIVER LOGISTICS"
    app.session_state["lookup_choice"] = "BLUE RIVER LOGISTICS"
    lookup(app)
    assert app.subheader[0].value == "Blue River Logistics"


def test_shared_employer_link_opens_the_employer(demo_app_data, monkeypatch):
    monkeypatch.setenv("H1B_APP_DATA", str(demo_app_data))
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["employer"] = "Quantfield Capital"
    at.switch_page("views/employer_lookup.py")  # a shared link opens this page directly
    at.run()
    assert not at.exception
    assert at.subheader[0].value == "Quantfield Capital"


def test_filters_come_from_the_url_and_go_back_to_it(demo_app_data, monkeypatch):
    monkeypatch.setenv("H1B_APP_DATA", str(demo_app_data))
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"role": "Operations Research", "state": "az", "min": "3"})
    at.query_params["consistent"] = "1"
    at.run()
    assert not at.exception
    assert at.selectbox[0].value == "Operations Research"
    assert at.selectbox[1].value == "AZ"
    assert (at.select_slider[0].value, at.checkbox[0].value) == (3, True)
    at.select_slider[0].set_value(10).run()
    assert at.query_params["min"] == ["10"]


def test_bad_url_values_fall_back_to_defaults(demo_app_data, monkeypatch):
    monkeypatch.setenv("H1B_APP_DATA", str(demo_app_data))
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"role": "Astronaut", "state": "ZZ", "min": "abc"})
    at.run()
    assert not at.exception
    assert at.selectbox[0].value == "Analytics (combined)"
    assert (at.selectbox[1].value, at.select_slider[0].value) == ("ALL", 5)
    assert at.query_params["role"] == ["Analytics (combined)"]


def test_filters_persist_across_pages(app):
    app.selectbox[0].set_value("Operations Research").run()
    app.select_slider[0].set_value(3).run()
    app.checkbox[0].check().run()
    app.switch_page("views/trends.py").run()
    assert app.query_params["role"] == ["Operations Research"]  # still in the URL
    app.switch_page("views/find_sponsors.py").run()
    assert app.selectbox[0].value == "Operations Research"
    assert (app.select_slider[0].value, app.checkbox[0].value) == (3, True)
