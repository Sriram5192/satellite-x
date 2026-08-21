"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True, slots=True)
class Settings:
    aws_stac_url: str = "https://earth-search.aws.element84.com/v1"
    cdse_stac_url: str = "https://stac.dataspace.copernicus.eu/v1"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    soilgrids_url: str = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    nominatim_url: str = "https://nominatim.openstreetmap.org/reverse"
    ftw_vectors_base_url: str = (
        "https://data.source.coop/ftw/global-data/predictions/vectors/alpha/"
        "results-by-admin-conf"
    )
    planetary_computer_stac_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    planetary_computer_s1_token_url: str = (
        "https://planetarycomputer.microsoft.com/api/sas/v1/token/"
        "sentinel1euwestrtc/sentinel1-grd-rtc"
    )
    connect_timeout_s: float = 5.0
    read_timeout_s: float = 30.0
    retries: int = 2
    backoff_factor: float = 0.5
    user_agent: str = "Satellite-X/0.1"
    max_cloud_pct: float = 40.0
    expand_days: int = 30
    forecast_days: int = 7
    iot_max_age_hours: float = 24.0
    road_reject_distance_m: float = 20.0
    structure_reject_distance_m: float = 15.0
    water_reject_distance_m: float = 15.0
    ftw_min_area_ratio: float = 0.2
    ftw_max_area_ratio: float = 5.0
    ftw_query_limit: int = 250
    max_candidate_area_difference_pct: float = 50.0
    polygon_high_score_pct: float = 85.0
    polygon_medium_score_pct: float = 65.0
    polygon_max_candidates: int = 5
    spectral_min_valid_pct: float = 60.0
    spectral_min_valid_pixels: int = 9
    cache_dir: Path = Path("runtime/cache")
    soil_baseline_ph: float = 6.8
    soil_baseline_n_g_kg: float = 0.25

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            connect_timeout_s=_env_float("SATELLITE_X_CONNECT_TIMEOUT_S", 5.0),
            read_timeout_s=_env_float("SATELLITE_X_READ_TIMEOUT_S", 30.0),
            retries=_env_int("SATELLITE_X_RETRIES", 2),
            backoff_factor=_env_float("SATELLITE_X_BACKOFF_FACTOR", 0.5),
            user_agent=os.getenv("SATELLITE_X_USER_AGENT", "Satellite-X/0.1"),
            max_cloud_pct=_env_float("SATELLITE_X_MAX_CLOUD_PCT", 40.0),
            expand_days=_env_int("SATELLITE_X_EXPAND_DAYS", 30),
            forecast_days=_env_int("SATELLITE_X_FORECAST_DAYS", 7),
            iot_max_age_hours=_env_float("SATELLITE_X_IOT_MAX_AGE_HOURS", 24.0),
            road_reject_distance_m=_env_float(
                "SATELLITE_X_ROAD_REJECT_DISTANCE_M", 20.0
            ),
            structure_reject_distance_m=_env_float(
                "SATELLITE_X_STRUCTURE_REJECT_DISTANCE_M", 15.0
            ),
            water_reject_distance_m=_env_float(
                "SATELLITE_X_WATER_REJECT_DISTANCE_M", 15.0
            ),
            ftw_min_area_ratio=_env_float("SATELLITE_X_FTW_MIN_AREA_RATIO", 0.2),
            ftw_max_area_ratio=_env_float("SATELLITE_X_FTW_MAX_AREA_RATIO", 5.0),
            ftw_query_limit=_env_int("SATELLITE_X_FTW_QUERY_LIMIT", 250),
            max_candidate_area_difference_pct=_env_float(
                "SATELLITE_X_MAX_CANDIDATE_AREA_DIFF_PCT", 50.0
            ),
            polygon_high_score_pct=_env_float(
                "SATELLITE_X_POLYGON_HIGH_SCORE_PCT", 85.0
            ),
            polygon_medium_score_pct=_env_float(
                "SATELLITE_X_POLYGON_MEDIUM_SCORE_PCT", 65.0
            ),
            polygon_max_candidates=_env_int(
                "SATELLITE_X_POLYGON_MAX_CANDIDATES", 5
            ),
            spectral_min_valid_pct=_env_float(
                "SATELLITE_X_SPECTRAL_MIN_VALID_PCT", 60.0
            ),
            spectral_min_valid_pixels=_env_int(
                "SATELLITE_X_SPECTRAL_MIN_VALID_PIXELS", 9
            ),
            cache_dir=Path(os.getenv("SATELLITE_X_CACHE_DIR", "runtime/cache")),
            soil_baseline_ph=_env_float("SATELLITE_X_SOIL_BASELINE_PH", 6.8),
            soil_baseline_n_g_kg=_env_float("SATELLITE_X_SOIL_BASELINE_N_G_KG", 0.25),
        )
