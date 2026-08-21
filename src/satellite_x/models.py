"""Validated input/output contracts for SATELLITE-X Set 1."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, use_enum_values=True)


class CropType(str, Enum):
    cotton = "cotton"
    chilli = "chilli"
    paddy = "paddy"


class FarmInput(StrictModel):
    field_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    crop_type: CropType
    sowing_date: date
    analysis_date: date = Field(default_factory=date.today)
    scan_range_days: int = Field(default=30, ge=1, le=180)
    acres: float = Field(gt=0, le=1_000_000)
    boundary_geojson: dict[str, Any] | None = None

    @field_validator("crop_type", mode="before")
    @classmethod
    def normalize_crop(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("boundary_geojson")
    @classmethod
    def validate_boundary(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        if value.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("boundary_geojson.type must be Polygon or MultiPolygon")
        coordinates = value.get("coordinates")
        if not isinstance(coordinates, (list, tuple)) or not coordinates:
            raise ValueError("boundary_geojson.coordinates must be a non-empty list")
        return value

    @model_validator(mode="after")
    def dates_are_consistent(self) -> "FarmInput":
        if self.sowing_date > self.analysis_date:
            raise ValueError("sowing_date cannot be after analysis_date")
        return self


class IoTReading(StrictModel):
    field_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    device_id: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    soil_moisture_pct: float = Field(ge=0, le=100)
    soil_temp_c: float = Field(ge=-20, le=80)
    soil_ph: float = Field(ge=0, le=14)
    n_mg_kg: float = Field(ge=0)
    p_mg_kg: float = Field(ge=0)
    k_mg_kg: float = Field(ge=0)
    battery_v: float = Field(ge=0, le=6)
    source: Literal["live_hardware"] = "live_hardware"

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        return value


class AcquisitionAttempt(StrictModel):
    source: str
    date_start: date | None = None
    date_end: date | None = None
    outcome: Literal["success", "empty", "error"]
    detail: str


class BandAsset(StrictModel):
    band_code: Literal["B02", "B03", "B04", "B05", "B08", "B11", "SCL"]
    source_key: str
    href: str = Field(min_length=1)
    resolution_m: int = Field(gt=0)
    media_type: str | None = None
    scale: float | None = None
    offset: float | None = None
    nodata: float | None = None
    requires_authentication: bool = False


class SatelliteScene(StrictModel):
    scene_id: str
    provider: Literal["aws_earth_search", "copernicus_cdse"]
    collection: str
    acquired_at: datetime
    cloud_cover_pct: float = Field(ge=0, le=100)
    bbox: list[float] = Field(min_length=4, max_length=4)
    assets: dict[str, BandAsset]

    @model_validator(mode="after")
    def all_required_bands_exist(self) -> "SatelliteScene":
        required = {"B02", "B03", "B04", "B05", "B08", "B11", "SCL"}
        if set(self.assets) != required:
            missing = sorted(required - set(self.assets))
            extra = sorted(set(self.assets) - required)
            raise ValueError(f"invalid asset set; missing={missing}, extra={extra}")
        return self


class SatelliteAcquisition(StrictModel):
    scene: SatelliteScene
    attempts: list[AcquisitionAttempt]
    expanded_date_range: bool
    fallback_used: bool


class DailyWeather(StrictModel):
    observation_date: date
    precipitation_mm: float = Field(ge=0)
    et0_mm: float = Field(ge=0)
    temperature_max_c: float
    temperature_min_c: float
    relative_humidity_mean_pct: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def temperatures_are_consistent(self) -> "DailyWeather":
        if self.temperature_min_c > self.temperature_max_c:
            raise ValueError("temperature_min_c cannot exceed temperature_max_c")
        return self


class WeatherSummary(StrictModel):
    days_available_15d: int = Field(ge=0, le=15)
    rain_15d_mm: float = Field(ge=0)
    et0_15d_mm: float = Field(ge=0)
    days_available_30d: int = Field(ge=0, le=30)
    rain_30d_mm: float = Field(ge=0)
    et0_30d_mm: float = Field(ge=0)
    humidity_mean_5d_pct: float | None = Field(default=None, ge=0, le=100)
    complete_15d: bool
    complete_30d: bool


class WeatherAcquisition(StrictModel):
    source: Literal["open_meteo_archive", "open_meteo_forecast", "cache"]
    history: list[DailyWeather]
    forecast: list[DailyWeather]
    summary: WeatherSummary
    cache_key: str
    fallback_used: bool = False


class SoilProperties(StrictModel):
    ph_h2o: float = Field(ge=0, le=14)
    nitrogen_g_kg: float = Field(ge=0)
    depth: Literal["0-5cm"] = "0-5cm"
    statistic: Literal["mean"] = "mean"
    source: Literal["soilgrids_live", "cache", "regional_ag_zone_baseline"]
    fallback_used: bool = False
    cache_key: str | None = None


class StreamState(StrictModel):
    stream: Literal["satellite", "weather", "soil", "iot"]
    state: Literal[
        "live", "cache", "baseline", "unverified", "stale", "not_supplied"
    ]
    detail: str


class RawDataContainer(StrictModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    field: FarmInput
    acquired_at: datetime
    status: Literal["complete", "degraded"]
    satellite: SatelliteAcquisition
    weather: WeatherAcquisition
    soil: SoilProperties
    iot: IoTReading | None = None
    iot_verified: bool = False
    iot_fresh: bool | None = None
    streams: list[StreamState]
    warnings: list[str] = Field(default_factory=list)

    @field_validator("acquired_at")
    @classmethod
    def acquired_at_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("acquired_at must include a UTC offset")
        return value

    @model_validator(mode="after")
    def iot_provenance_is_consistent(self) -> "RawDataContainer":
        if self.iot is None and (self.iot_verified or self.iot_fresh is not None):
            raise ValueError("IoT provenance flags require an IoT reading")
        if self.iot is not None and self.iot_fresh is None:
            raise ValueError("iot_fresh must be set when an IoT reading is supplied")
        return self


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
