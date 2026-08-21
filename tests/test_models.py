from datetime import datetime

import pytest
from pydantic import ValidationError

from satellite_x.models import FarmInput, IoTReading


BASE_FIELD = {
    "field_id": "AP_F001",
    "latitude": 16.3067,
    "longitude": 80.4365,
    "crop_type": "Cotton",
    "sowing_date": "2024-01-01",
    "analysis_date": "2024-01-30",
    "scan_range_days": 30,
    "acres": 5,
}


def test_farm_input_normalizes_crop_and_dates():
    field = FarmInput.model_validate(BASE_FIELD)
    assert field.crop_type == "cotton"
    assert field.analysis_date.isoformat() == "2024-01-30"


def test_sowing_date_after_analysis_is_rejected():
    data = {**BASE_FIELD, "sowing_date": "2024-02-01"}
    with pytest.raises(ValidationError, match="sowing_date cannot be after"):
        FarmInput.model_validate(data)


def test_non_polygon_boundary_is_rejected():
    data = {**BASE_FIELD, "boundary_geojson": {"type": "Point", "coordinates": [1, 2]}}
    with pytest.raises(ValidationError, match="Polygon or MultiPolygon"):
        FarmInput.model_validate(data)


def iot_payload():
    return {
        "field_id": "AP_F001",
        "device_id": "ESP32_01",
        "timestamp": "2026-08-15T10:30:00Z",
        "soil_moisture_pct": 34.5,
        "soil_temp_c": 27.1,
        "soil_ph": 6.8,
        "n_mg_kg": 28,
        "p_mg_kg": 19.5,
        "k_mg_kg": 35.2,
        "battery_v": 3.8,
        "source": "live_hardware",
    }


def test_iot_contract_accepts_blueprint_payload():
    reading = IoTReading.model_validate(iot_payload())
    assert reading.timestamp.utcoffset().total_seconds() == 0
    assert reading.source == "live_hardware"


@pytest.mark.parametrize(
    ("field", "value"),
    [("soil_moisture_pct", 101), ("soil_ph", 14.1), ("battery_v", 6.1), ("n_mg_kg", -1)],
)
def test_iot_physical_ranges_are_enforced(field, value):
    payload = iot_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        IoTReading.model_validate(payload)


def test_iot_naive_timestamp_and_extra_fields_are_rejected():
    payload = iot_payload()
    payload["timestamp"] = datetime(2026, 8, 15, 10, 30).isoformat()
    payload["fabricated"] = True
    with pytest.raises(ValidationError) as error:
        IoTReading.model_validate(payload)
    assert "timestamp must include a UTC offset" in str(error.value)
    assert "Extra inputs are not permitted" in str(error.value)
