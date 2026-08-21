"""Headless farmer UI integration: recovery -> SAR -> Set 2 -> Set 3/4."""
from __future__ import annotations

import json
import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
os.environ["SATELLITE_X_DEMO_MODE"] = "1"
os.environ.pop("SATELLITE_X_IDENTITY_DB", None)
at = AppTest.from_file(str(ROOT / "apps/polygon_app.py"), default_timeout=180).run()


def click(label: str) -> None:
    button = next(item for item in at.button if item.label == label)
    button.click().run()
    if at.exception:
        raise RuntimeError("; ".join(str(item.value) for item in at.exception))


next(item for item in at.text_input if item.label == "Field ID").set_value("AP_GNT_FTW_CROP_TEST")
next(item for item in at.number_input if item.label == "Latitude").set_value(16.064444813421694)
next(item for item in at.number_input if item.label == "Longitude").set_value(80.6059204280875)
next(item for item in at.number_input if item.label == "Reported acres").set_value(2.4791228671574923)
consent = next(item for item in at.checkbox if item.label.startswith("I consent"))
consent.set_value(True)
click("Recover Polygon")
click("Confirm selected candidate")
click("Run Sentinel-1 RTC cloud fallback")
click("Run Set 2 preprocessing")
click("Run Set 3 analytics + Set 4 diagnosis")

preprocessing = at.session_state["preprocessing"]
sar = at.session_state["sar_fallback"]
analytics = at.session_state["analytics"]
diagnosis = at.session_state["diagnosis"]
route_text = next(
    item.value for item in at.markdown if item.value.startswith("### Multimodal route:")
)
route = route_text.split("`")[1]
report = {
    "passed": not at.exception,
    "exceptions": [str(item.value) for item in at.exception],
    "field_id": analytics.field_id,
    "sar_status": sar.status,
    "sar_scene_id": sar.scene_id,
    "set2_status": preprocessing.status,
    "set2_scene_id": preprocessing.selected_scene.scene_id,
    "multimodal_route": route,
    "set3_ndvi_mean": analytics.indices["ndvi"].mean,
    "weather_reference_end": analytics.water_balance.reference_end_date.isoformat(),
    "water_balance_15d_mm": analytics.water_balance.water_balance_15d_mm,
    "set4_verdict": diagnosis.verdict,
    "set4_confidence_pct": diagnosis.confidence.final_confidence_pct,
}
(ROOT / "outputs/streamlit_flow.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
