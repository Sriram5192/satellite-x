import pytest
from pathlib import Path
from streamlit.testing.v1 import AppTest


APP = Path(__file__).parents[1] / "public_demo" / "app.py"


@pytest.mark.live
def test_public_tester_original_top_to_end_flow():
    app = AppTest.from_file(APP, default_timeout=240).run()
    app.text_input[0].set_value("PUBLIC-CROP-TEST")
    app.number_input[0].set_value(16.064444813421694)
    app.number_input[1].set_value(80.6059204280875)
    app.number_input[2].set_value(2.4791228671574923)
    app.checkbox[0].set_value(True)
    next(item for item in app.button if item.label == "Validate input").click().run()
    next(item for item in app.button if item.label.startswith("Run location check")).click().run()
    app.checkbox[1].set_value(True).run()
    next(item for item in app.button if item.label == "Confirm selected boundary").click().run()
    next(item for item in app.button if item.label.startswith("Run Set 1")).click().run()
    assert not app.exception
    bundle = app.session_state["result_bundle"]
    assert bundle["preprocessing"]["status"] == "accepted"
    assert bundle["sar"]["status"] == "accepted"
    assert bundle["analytics"]["water_balance"]["reference_end_date"] == bundle["analytics"]["scene_date"]
    assert bundle["diagnosis"]["verdict"] == "NORMAL_OR_UNRESOLVED"
    assert app.download_button
