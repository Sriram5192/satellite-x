import pytest

from satellite_x.acquisition.weather import WeatherClient
from satellite_x.cache import JsonCache
from satellite_x.config import Settings
from satellite_x.errors import ExternalServiceError
from satellite_x.models import FarmInput
from conftest import RouteHttp


def field():
    return FarmInput.model_validate({
        "field_id": "AP_F001", "latitude": 16.3067, "longitude": 80.4365,
        "crop_type": "cotton", "sowing_date": "2024-01-01",
        "analysis_date": "2024-01-30", "scan_range_days": 30, "acres": 5,
    })


def test_golden_15_and_30_day_aggregates(load_fixture, tmp_path):
    client = WeatherClient(
        RouteHttp(weather=load_fixture("weather_30d.json")),
        JsonCache(tmp_path), Settings(cache_dir=tmp_path),
    )
    result, warnings = client.acquire(field())
    assert warnings == []
    assert result.source == "open_meteo_archive"
    assert result.summary.model_dump() == {
        "days_available_15d": 15,
        "rain_15d_mm": 345.0,
        "et0_15d_mm": 60.0,
        "days_available_30d": 30,
        "rain_30d_mm": 465.0,
        "et0_30d_mm": 120.0,
        "humidity_mean_5d_pct": 88.0,
        "complete_15d": True,
        "complete_30d": True,
    }


def test_live_failure_reuses_exact_cached_response(load_fixture, tmp_path):
    cache = JsonCache(tmp_path)
    success = WeatherClient(
        RouteHttp(weather=load_fixture("weather_30d.json")), cache, Settings(cache_dir=tmp_path)
    )
    success.acquire(field())
    failed = WeatherClient(
        RouteHttp(failure=ExternalServiceError("open_meteo", "offline")),
        cache, Settings(cache_dir=tmp_path),
    )
    result, warnings = failed.acquire(field())
    assert result.source == "cache"
    assert result.fallback_used is True
    assert result.summary.rain_15d_mm == 345.0
    assert "cached response used" in warnings[0]


def test_live_failure_without_cache_is_not_fabricated(tmp_path):
    client = WeatherClient(
        RouteHttp(failure=ExternalServiceError("open_meteo", "offline")),
        JsonCache(tmp_path), Settings(cache_dir=tmp_path),
    )
    with pytest.raises(ExternalServiceError, match="cache unavailable"):
        client.acquire(field())
