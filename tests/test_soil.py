from satellite_x.acquisition.soil import SoilGridsClient
from satellite_x.cache import JsonCache
from satellite_x.config import Settings
from satellite_x.errors import ExternalServiceError
from satellite_x.models import FarmInput
from conftest import RouteHttp


def field():
    return FarmInput.model_validate({
        "field_id": "AP_F001", "latitude": 16.3067, "longitude": 80.4365,
        "crop_type": "paddy", "sowing_date": "2024-01-01",
        "analysis_date": "2024-01-30", "scan_range_days": 30, "acres": 5,
    })


def test_soilgrids_units_are_converted(load_fixture, tmp_path):
    client = SoilGridsClient(
        RouteHttp(soil=load_fixture("soilgrids.json")),
        JsonCache(tmp_path), Settings(cache_dir=tmp_path),
    )
    soil, warnings = client.acquire(field())
    assert warnings == []
    assert soil.ph_h2o == 6.8
    assert soil.nitrogen_g_kg == 0.25
    assert soil.source == "soilgrids_live"


def test_soil_uses_cache_then_explicit_baseline(load_fixture, tmp_path):
    cache = JsonCache(tmp_path)
    SoilGridsClient(
        RouteHttp(soil=load_fixture("soilgrids.json")), cache, Settings(cache_dir=tmp_path)
    ).acquire(field())
    cached, _ = SoilGridsClient(
        RouteHttp(failure=ExternalServiceError("soilgrids", "offline")),
        cache, Settings(cache_dir=tmp_path),
    ).acquire(field())
    assert cached.source == "cache"

    empty_cache = JsonCache(tmp_path / "empty")
    baseline, warnings = SoilGridsClient(
        RouteHttp(failure=ExternalServiceError("soilgrids", "offline")),
        empty_cache, Settings(cache_dir=tmp_path / "empty"),
    ).acquire(field())
    assert baseline.source == "regional_ag_zone_baseline"
    assert baseline.model_dump()["fallback_used"] is True
    assert (baseline.ph_h2o, baseline.nitrogen_g_kg) == (6.8, 0.25)
    assert "baseline used" in warnings[0]
