"""Authenticated farmer flow: login -> confirm/link own field -> SAR -> Set 2 -> Set 3/4."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

from satellite_x.identity import IdentityStore

ROOT = Path(__file__).resolve().parents[1]


def click(at, label: str):
    next(item for item in at.button if item.label == label).click().run()
    if at.exception:
        raise RuntimeError("; ".join(str(item.value) for item in at.exception))


with tempfile.TemporaryDirectory() as directory:
    db = Path(directory) / "identity.db"
    identity = IdentityStore(db); identity.initialize()
    identity.register("AUDIT-FARMER", "authenticated audit password", role="farmer")
    os.environ["SATELLITE_X_IDENTITY_DB"] = str(db)
    os.environ.pop("SATELLITE_X_DEMO_MODE", None)
    at = AppTest.from_file(str(ROOT / "apps/polygon_app.py"), default_timeout=180).run()
    next(item for item in at.text_input if item.label == "Account ID").set_value("AUDIT-FARMER")
    next(item for item in at.text_input if item.label == "Password").set_value("authenticated audit password")
    click(at, "Sign in")
    next(item for item in at.text_input if item.label == "Field ID").set_value("AP_GNT_FTW_CROP_TEST")
    next(item for item in at.number_input if item.label == "Latitude").set_value(16.064444813421694)
    next(item for item in at.number_input if item.label == "Longitude").set_value(80.6059204280875)
    next(item for item in at.number_input if item.label == "Reported acres").set_value(2.4791228671574923)
    next(item for item in at.checkbox if item.label.startswith("I consent")).set_value(True)
    click(at, "Recover Polygon")
    click(at, "Confirm selected candidate")
    click(at, "Link confirmed field to my account")
    principal = identity.authenticate(at.session_state["identity_token"])
    click(at, "Run Sentinel-1 RTC cloud fallback")
    click(at, "Run Set 2 preprocessing")
    click(at, "Run Set 3 analytics + Set 4 diagnosis")
    analytics = at.session_state["analytics"]
    diagnosis = at.session_state["diagnosis"]
    report = {
        "passed": not at.exception,
        "exceptions": [str(item.value) for item in at.exception],
        "authenticated_user": principal.user_id,
        "role": principal.role,
        "owned_field_ids": principal.owned_field_ids,
        "analyzed_field": analytics.field_id,
        "weather_reference_end": analytics.water_balance.reference_end_date.isoformat(),
        "scene_date": analytics.scene_date.isoformat(),
        "set4_verdict": diagnosis.verdict,
    }
(ROOT / "outputs/streamlit_authenticated_flow.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] and report["analyzed_field"] in report["owned_field_ids"] and report["weather_reference_end"] == report["scene_date"] else 1)
