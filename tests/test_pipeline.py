import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from satellite_x.acquisition.pipeline import AcquisitionPipeline
from satellite_x.config import Settings
from satellite_x.models import FarmInput, IoTReading
from conftest import RouteHttp


GOLDEN = Path(__file__).parent / "golden" / "set1_expected.json"


def test_full_pipeline_matches_golden_output(load_fixture, tmp_path):
    field = FarmInput.model_validate({
        "field_id": "AP_F001", "latitude": 16.3067, "longitude": 80.4365,
        "crop_type": "cotton", "sowing_date": "2024-01-01",
        "analysis_date": "2024-01-30", "scan_range_days": 30, "acres": 5,
    })
    iot = IoTReading.model_validate({
        "field_id": "AP_F001", "device_id": "ESP32_GOLDEN",
        "timestamp": "2024-01-30T10:30:00Z", "soil_moisture_pct": 34.5,
        "soil_temp_c": 27.1, "soil_ph": 6.8, "n_mg_kg": 28.0,
        "p_mg_kg": 19.5, "k_mg_kg": 35.2, "battery_v": 3.8,
        "source": "live_hardware",
    })
    http = RouteHttp(
        stac=load_fixture("aws_stac.json"),
        weather=load_fixture("weather_30d.json"),
        soil=load_fixture("soilgrids.json"),
    )
    settings = Settings(cache_dir=tmp_path)
    pipeline = AcquisitionPipeline(
        settings, http=http, clock=lambda: datetime(2024, 1, 30, 12, 0, tzinfo=timezone.utc)
    )
    actual = pipeline.run(field, iot).model_dump(mode="json")
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["iot_verified"] is False
    assert actual["iot_fresh"] is True
    assert actual["streams"][3]["state"] == "unverified"
    assert any("HMAC-SHA256" in warning for warning in actual["warnings"])

    verified = pipeline.run(field, iot, iot_verified=True)
    assert verified.iot_verified is True
    assert verified.iot_fresh is True
    assert verified.streams[3].state == "live"
    assert verified.status == "complete"


def test_iot_field_mismatch_stops_before_external_calls(tmp_path):
    field = FarmInput.model_validate({
        "field_id": "A", "latitude": 16, "longitude": 80, "crop_type": "paddy",
        "sowing_date": "2024-01-01", "analysis_date": "2024-01-30", "acres": 1,
    })
    iot = IoTReading.model_validate({
        "field_id": "B", "device_id": "node", "timestamp": "2024-01-30T00:00:00Z",
        "soil_moisture_pct": 20, "soil_temp_c": 20, "soil_ph": 7,
        "n_mg_kg": 1, "p_mg_kg": 1, "k_mg_kg": 1, "battery_v": 3.7,
        "source": "live_hardware",
    })
    http = RouteHttp()
    pipeline = AcquisitionPipeline(Settings(cache_dir=tmp_path), http=http)
    with pytest.raises(ValueError, match="does not match"):
        pipeline.run(field, iot)
    assert http.calls == []
