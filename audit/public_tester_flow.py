"""Headless top-to-end validation of the one-page public tester."""
from __future__ import annotations

import json
from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
app = AppTest.from_file(str(ROOT / "public_demo/app.py"), default_timeout=240).run()
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
bundle = app.session_state["result_bundle"]
checks = {
    "no_streamlit_exception": not app.exception,
    "boundary_confirmed": bundle["boundary_confirmation"]["user_confirmed"] is True,
    "set2_accepted": bundle["preprocessing"]["status"] == "accepted",
    "sar_accepted": bundle["sar"]["status"] == "accepted",
    "optical_primary_sar_ancillary": bundle["resilience"]["status"] == "OPTICAL_PRIMARY_SAR_ANCILLARY",
    "seven_indices": len(bundle["analytics"]["indices"]) == 7,
    "scene_weather_aligned": bundle["analytics"]["water_balance"]["reference_end_date"] == bundle["analytics"]["scene_date"],
    "diagnosis_present": bool(bundle["diagnosis"]["verdict"]),
    "download_available": bool(app.download_button),
    "ephemeral_no_persistence": bundle["persistent_storage"] is False,
}
report = {
    "scope": "public_one_page_original_services",
    "checks": checks,
    "passed": all(checks.values()),
    "verdict": bundle["diagnosis"]["verdict"],
    "scene_date": bundle["analytics"]["scene_date"],
    "water_balance_mm": bundle["analytics"]["water_balance"]["water_balance_15d_mm"],
}
(ROOT / "outputs/public_tester_flow.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
