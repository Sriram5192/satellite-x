"""Headless validation of every public demo page."""
from __future__ import annotations

import json
from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
pages = [
    "Executive overview", "Agriculture intelligence", "Orbit & Doppler",
    "Atmosphere & link", "Dynamic traffic", "Security & governance",
    "Verification & activation",
]
app = AppTest.from_file(str(ROOT / "apps/power_engine_demo.py"), default_timeout=120).run()
checks = {}
for page in pages:
    if page != "Executive overview":
        app.radio[0].set_value(page).run()
    checks[page] = not app.exception
report = {
    "pages": checks,
    "passed": all(checks.values()),
    "explicit_external_activation_warning": any(
        "Operational external activation" in item.value for item in app.error
    ),
    "scope": "read_only_release_artifact_demo",
}
report["passed"] = report["passed"] and report["explicit_external_activation_warning"]
(ROOT / "outputs/power_engine_demo_flow.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
