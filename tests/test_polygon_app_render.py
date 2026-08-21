from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).parents[1] / "apps" / "polygon_app.py"


def test_polygon_app_initial_render_has_no_exception(monkeypatch):
    monkeypatch.setenv("SATELLITE_X_DEMO_MODE", "1")
    monkeypatch.delenv("SATELLITE_X_IDENTITY_DB", raising=False)
    app = AppTest.from_file(APP, default_timeout=60).run()
    assert not app.exception
    assert any("Polygon Recovery" in title.value for title in app.title)
    assert any("consent" in checkbox.label.lower() for checkbox in app.checkbox)
    assert [button.label for button in app.button][:2] == [
        "Load accepted crop integration test",
        "Recover Polygon",
    ]


def test_polygon_app_fails_closed_without_auth_or_explicit_demo(monkeypatch):
    monkeypatch.delenv("SATELLITE_X_DEMO_MODE", raising=False)
    monkeypatch.delenv("SATELLITE_X_IDENTITY_DB", raising=False)
    app = AppTest.from_file(APP, default_timeout=60).run()
    assert not app.exception
    assert any("Authentication is not configured" in item.value for item in app.error)
    assert not app.checkbox
