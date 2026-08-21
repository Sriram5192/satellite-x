"""Independent ordinary-least-squares oracle for the live multi-scene output."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = json.loads((ROOT / "examples/timeseries_live_request.json").read_text())
actual = json.loads((ROOT / "outputs/timeseries_live_result.json").read_text())
rows = sorted(source["observations"], key=lambda row: row["scene_date"])
from datetime import date
x = [(date.fromisoformat(row["scene_date"]) - date.fromisoformat(rows[0]["scene_date"])).days for row in rows]
checks = {}
expected = {}
for name in sorted(rows[0]["indices"]):
    y = [row["indices"][name]["mean"] for row in rows]
    x_mean = sum(x) / len(x)
    y_mean = sum(y) / len(y)
    slope = sum((a - x_mean) * (b - y_mean) for a, b in zip(x, y)) / sum((a - x_mean) ** 2 for a in x)
    expected[name] = {"slope_per_day": round(slope, 6), "total_change": round(y[-1] - y[0], 6)}
    checks[f"{name}_slope"] = abs(actual["index_trends"][name]["slope_per_day"] - expected[name]["slope_per_day"]) <= 1e-6
    checks[f"{name}_change"] = abs(actual["index_trends"][name]["total_change"] - expected[name]["total_change"]) <= 1e-6
checks["observation_count"] = actual["observation_count"] == 3
checks["max_gap_days"] = actual["max_gap_days"] == 33
report = {"oracle": "independent_ols_from_three_real_set3_outputs", "expected": expected, "checks": checks, "passed": all(checks.values())}
(ROOT / "outputs/timeseries_reality.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
