"""Independent TLE/SGP4/ITU/link-budget/DES output comparison.

Imports no SATELLITE-X application modules.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import itur
from skyfield.api import EarthSatellite, load, wgs84

ROOT = Path(__file__).resolve().parents[1]
tle = json.loads((ROOT / "outputs/sentinel2a_tle_live.json").read_text())
passes = json.loads((ROOT / "outputs/sentinel2a_guntur_passes.json").read_text())
atmosphere = json.loads((ROOT / "outputs/atmospheric_loss_guntur_xband_validation.json").read_text())
link = json.loads((ROOT / "outputs/link_budget_xband_validation_only.json").read_text())
traffic = json.loads((ROOT / "outputs/traffic_120_station_validation_only.json").read_text())
provenance = json.loads((ROOT / "outputs/scene_orbit_provenance.json").read_text())


def checksum(line):
    return (sum(int(ch) for ch in line[:68] if ch.isdigit()) + line[:68].count("-")) % 10 == int(line[-1])

checks = {
    "tle_line1_checksum": checksum(tle["line1"]),
    "tle_line2_checksum": checksum(tle["line2"]),
    "tle_norad_id": int(tle["line1"][2:7]) == 40697,
    "historical_scene_rejected_latest_tle": provenance["status"] == "historical_tle_required" and not provenance["usable_for_pass_validation"],
}
first = passes["passes"][0]["samples"][0]
ts = load.timescale()
satellite = EarthSatellite(tle["line1"], tle["line2"], tle["name"], ts)
station = wgs84.latlon(16.3067, 80.4365, elevation_m=30)
difference = satellite - station
moment = datetime.fromisoformat(first["timestamp"].replace("Z", "+00:00"))
position = difference.at(ts.from_datetime(moment))
alt, az, distance = position.altaz()
before = difference.at(ts.from_datetime(moment - timedelta(seconds=0.5))).distance().km
after = difference.at(ts.from_datetime(moment + timedelta(seconds=0.5))).distance().km
range_rate = after - before
doppler = -8.2e9 * range_rate / 299_792.458
checks.update({
    "pass_elevation_equal": abs(first["elevation_deg"] - float(alt.degrees)) <= 1e-6,
    "pass_range_equal": abs(first["range_km"] - float(distance.km)) <= 1e-6,
    "pass_doppler_equal": abs(first["doppler_shift_hz"] - doppler) <= 0.01,
})
values = itur.atmospheric_attenuation_slant_path(
    16.3067, 80.4365, 8.2, 30, 0.01, 3.0, return_contributions=True
)
gas, cloud, rain, scint, total = [float(value.value) for value in values]
checks.update({
    "itu_gas_equal": abs(atmosphere["gaseous_db"] - gas) <= 1e-6,
    "itu_rain_equal": abs(atmosphere["rain_db"] - rain) <= 1e-6,
    "itu_total_equal": abs(atmosphere["modeled_total_db"] - total) <= 1e-6,
})
frequency = 8.2
range_km = 1000
wavelength = 299_792_458 / (frequency * 1e9)
fspl = 92.45 + 20 * math.log10(frequency) + 20 * math.log10(range_km)
gain = 10 * math.log10(0.6 * (math.pi * 3 / wavelength) ** 2)
received = 60 + gain - fspl - 8 - 2
n0 = 10 * math.log10(1.380649e-23 * 150)
cn0 = received - n0
ebn0 = cn0 - 10 * math.log10(560e6)
margin = ebn0 - 6
checks.update({
    "link_fspl_equal": abs(link["free_space_path_loss_db"] - fspl) <= 1e-6,
    "link_margin_equal": abs(link["link_margin_db"] - margin) <= 1e-6,
    "link_doppler_equal": abs(link["doppler_shift_hz"] - (-8.2e9 * 5 / 299_792.458)) <= 0.01,
    "traffic_request_conservation": traffic["completed_requests"] + traffic["dropped_requests"] == traffic["total_requests"] == 120,
    "traffic_data_conservation": abs(traffic["transmitted_megabits"] + traffic["dropped_megabits"] - traffic["requested_megabits"]) <= 1e-6,
    "traffic_fixture_labeled": traffic["scenario_purpose"] == "deterministic_validation_fixture",
})
checks = {key: bool(value) for key, value in checks.items()}
report = {
    "checks": checks,
    "passed": all(checks.values()),
    "check_count": len(checks),
    "important_scope": "TLE/SGP4 and ITU statistics are not live beacon telemetry; traffic is a labeled validation fixture.",
}
(ROOT / "outputs/orbit_communications_reality.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
