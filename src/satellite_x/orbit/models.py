from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from ..models import StrictModel


class TleRecord(StrictModel):
    name: str
    norad_id: int = Field(gt=0)
    line1: str
    line2: str
    epoch: datetime
    fetched_at: datetime
    source_url: str
    age_hours_at_fetch: float
    freshness: Literal["fresh", "stale"]
    maximum_age_hours: float


class GroundStation(StrictModel):
    station_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    elevation_m: float = Field(default=0, ge=-500, le=9000)


class PassPredictionInput(StrictModel):
    tle: TleRecord
    station: GroundStation
    start_time: datetime
    end_time: datetime
    minimum_elevation_deg: float = Field(default=10, ge=0, le=90)
    downlink_frequency_hz: float = Field(default=8.2e9, gt=0)
    sample_interval_seconds: int = Field(default=10, ge=1, le=300)
    maximum_tle_epoch_gap_hours: float = Field(default=168, gt=0)

    @model_validator(mode="after")
    def validate_window(self) -> "PassPredictionInput":
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("pass prediction times must include timezone")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class PassSample(StrictModel):
    timestamp: datetime
    elevation_deg: float
    azimuth_deg: float
    range_km: float
    range_rate_km_s: float
    doppler_shift_hz: float


class PassWindow(StrictModel):
    aos: datetime
    tca: datetime
    los: datetime
    duration_seconds: float = Field(gt=0)
    max_elevation_deg: float
    max_absolute_doppler_hz: float
    samples: list[PassSample]


class PassPredictionResult(StrictModel):
    norad_id: int
    satellite_name: str
    station_id: str
    tle_epoch: datetime
    prediction_start: datetime
    prediction_end: datetime
    tle_epoch_gap_hours: float
    status: Literal["accepted", "tle_epoch_out_of_policy", "no_pass"]
    passes: list[PassWindow]
    warnings: list[str] = Field(default_factory=list)
