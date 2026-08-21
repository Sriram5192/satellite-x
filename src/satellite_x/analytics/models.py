"""Set 3 input/output contracts."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import Field, model_validator

from ..models import SoilProperties, StrictModel, WeatherAcquisition
from ..preprocessing.models import PreprocessingResult


class AnalyticsInput(StrictModel):
    field_id: str
    crop_type: Literal["cotton", "chilli", "paddy"]
    sowing_date: date
    sowing_date_quality: Literal["known", "approximate_month", "unknown"] = "known"
    preprocessing: PreprocessingResult
    weather: WeatherAcquisition
    soil: SoilProperties

    @model_validator(mode="after")
    def field_and_status_match(self) -> "AnalyticsInput":
        if self.preprocessing.request.field_id != self.field_id:
            raise ValueError("preprocessing field_id does not match analytics field_id")
        if self.preprocessing.status != "accepted":
            raise ValueError("analytics requires an accepted preprocessing result")
        scene = self.preprocessing.selected_scene
        if scene is None:
            raise ValueError("accepted preprocessing requires selected_scene")
        dates = sorted(item.observation_date for item in self.weather.history)
        scene_date = scene.acquired_at.date()
        if not dates or dates[-1] != scene_date:
            latest = dates[-1].isoformat() if dates else "none"
            raise ValueError(
                f"weather history must end on selected scene date {scene_date}; latest is {latest}"
            )
        expected = [scene_date - timedelta(days=offset) for offset in range(14, -1, -1)]
        if dates[-15:] != expected:
            raise ValueError("weather history must contain 15 contiguous days ending on the scene date")
        from ..acquisition.weather import WeatherClient
        if WeatherClient.summarize(self.weather.history) != self.weather.summary:
            raise ValueError("weather summary does not match the supplied daily history")
        return self


class IndexStatistics(StrictModel):
    mean: float
    median: float
    p10: float
    p90: float
    minimum: float
    maximum: float
    valid_pixels: int = Field(gt=0)


class PhenologyState(StrictModel):
    crop_type: str
    das: int
    stage_name: str
    stage_start_das: int
    stage_end_das: int
    expected_ndvi_low: float
    expected_ndvi_high: float
    criticality: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    ndvi_position: Literal["BELOW_EXPECTED", "WITHIN_EXPECTED", "ABOVE_EXPECTED"]


class WaterBalanceState(StrictModel):
    reference_start_date: date
    reference_end_date: date
    scene_alignment_days: Literal[0] = 0
    rain_15d_mm: float
    et0_15d_mm: float
    water_balance_15d_mm: float
    humidity_mean_5d_pct: float | None = Field(default=None, ge=0, le=100)
    deficit_flag: bool
    threshold_mm: float = -30.0


class AnalyticsResult(StrictModel):
    schema_version: Literal["1.1.0"] = "1.1.0"
    field_id: str
    computed_at: datetime
    scene_id: str
    scene_date: date
    spectral_valid_pixels: int = Field(gt=0)
    spectral_valid_pct: float = Field(gt=0, le=100)
    indices: dict[str, IndexStatistics]
    phenology: PhenologyState
    water_balance: WaterBalanceState
    soil: SoilProperties
    data_warnings: list[str] = Field(default_factory=list)
