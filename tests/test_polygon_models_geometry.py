import pytest
from pydantic import ValidationError

from satellite_x.polygon.geometry import normalize_and_validate
from satellite_x.polygon.models import PolygonRecoveryInput


def request(**updates):
    raw = {
        "field_id": "AP_FIELD", "latitude": 16.2, "longitude": 80.3,
        "acres": 1.0, "location_consent": True, "country_code": "IN",
        "subdivision_code": "AP", "search_radius_m": 300, "gps_tolerance_m": 30,
    }
    raw.update(updates)
    return PolygonRecoveryInput.model_validate(raw)


def test_location_consent_is_mandatory():
    with pytest.raises(ValidationError):
        request(location_consent=False)


def test_polygon_is_measured_and_contains_gps():
    geometry = {
        "type": "Polygon",
        "coordinates": [[[80.299, 16.199], [80.301, 16.199], [80.301, 16.201],
                         [80.299, 16.201], [80.299, 16.199]]],
    }
    normalized, validation = normalize_and_validate(geometry, request())
    assert normalized["type"] == "Polygon"
    assert validation.valid is True
    assert validation.contains_input_point is True
    assert validation.point_distance_m == 0
    assert validation.area_m2 > 0


def test_self_intersection_is_repaired():
    bowtie = {
        "type": "Polygon",
        "coordinates": [[[80.299, 16.199], [80.301, 16.201], [80.299, 16.201],
                         [80.301, 16.199], [80.299, 16.199]]],
    }
    _, validation = normalize_and_validate(bowtie, request())
    assert validation.repaired is True
    assert validation.geometry_type == "MultiPolygon"
    assert validation.area_m2 > 0
