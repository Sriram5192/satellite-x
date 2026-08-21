from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).parents[1] / "apps" / "power_engine_demo.py"


def test_power_engine_demo_all_pages_render_without_exception():
    app = AppTest.from_file(APP, default_timeout=120).run()
    assert not app.exception
    pages = [
        "Agriculture intelligence", "Orbit & Doppler", "Atmosphere & link",
        "Dynamic traffic", "Security & governance", "Verification & activation",
    ]
    for page in pages:
        app.radio[0].set_value(page).run()
        assert not app.exception, page
    assert any("Operational external activation" in item.value for item in app.error)
