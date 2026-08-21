from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).parents[1] / "public_demo" / "app.py"


def test_public_tester_initial_page_is_simple_and_fail_closed():
    app = AppTest.from_file(APP, default_timeout=120).run()
    assert not app.exception
    assert any("Test Your Field" in item.value for item in app.markdown)
    labels = [item.label for item in app.text_input]
    assert "Field ID" in labels
    assert any("consent" in item.label.lower() for item in app.checkbox)
    assert not app.download_button
    assert any("GitHub URL placeholder" in item.value for item in app.code)
