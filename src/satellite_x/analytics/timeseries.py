"""Crop-aware multi-scene trend summaries for executed Set 3 observations."""
from __future__ import annotations

from datetime import date
from typing import Literal

import numpy as np
from pydantic import Field, model_validator

from ..models import StrictModel
from .models import AnalyticsResult


class TimeSeriesInput(StrictModel):
    field_id: str
    observations: list[AnalyticsResult] = Field(min_length=2)

    @model_validator(mode="after")
    def observations_match(self) -> "TimeSeriesInput":
        if any(item.field_id != self.field_id for item in self.observations):
            raise ValueError("all observations must match field_id")
        crops = {item.phenology.crop_type for item in self.observations}
        if len(crops) != 1:
            raise ValueError("all observations must use the same crop")
        if len({item.scene_date for item in self.observations}) != len(self.observations):
            raise ValueError("scene dates must be unique")
        return self


class IndexTrend(StrictModel):
    first_mean: float
    latest_mean: float
    total_change: float
    slope_per_day: float
    direction: Literal["increasing", "stable", "decreasing"]


class TimeSeriesResult(StrictModel):
    field_id: str
    crop_type: str
    start_date: date
    end_date: date
    observation_count: int = Field(ge=2)
    max_gap_days: int = Field(ge=1)
    quality: Literal["limited", "usable"]
    index_trends: dict[str, IndexTrend]
    below_expected_ndvi_observations: int = Field(ge=0)
    persistent_water_deficit_observations: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class TimeSeriesService:
    def run(self, request: TimeSeriesInput) -> TimeSeriesResult:
        rows = sorted(request.observations, key=lambda item: item.scene_date)
        index_names = set(rows[0].indices)
        if any(set(item.indices) != index_names for item in rows):
            raise ValueError("all observations must contain identical indices")
        origin = rows[0].scene_date
        x = np.array([(item.scene_date - origin).days for item in rows], dtype=float)
        gaps = np.diff(x).astype(int)
        trends = {}
        for name in sorted(index_names):
            y = np.array([item.indices[name].mean for item in rows], dtype=float)
            slope = float(np.polyfit(x, y, 1)[0])
            if slope > 0.001:
                direction = "increasing"
            elif slope < -0.001:
                direction = "decreasing"
            else:
                direction = "stable"
            trends[name] = IndexTrend(
                first_mean=round(float(y[0]), 6), latest_mean=round(float(y[-1]), 6),
                total_change=round(float(y[-1] - y[0]), 6),
                slope_per_day=round(slope, 6), direction=direction,
            )
        warnings = []
        max_gap = int(gaps.max())
        if len(rows) < 3:
            warnings.append("Two scenes establish change, but at least three are required for a usable temporal trend.")
        if max_gap > 30:
            warnings.append("A scene gap exceeds 30 days; interpret temporal slopes cautiously.")
        return TimeSeriesResult(
            field_id=request.field_id,
            crop_type=rows[0].phenology.crop_type,
            start_date=rows[0].scene_date,
            end_date=rows[-1].scene_date,
            observation_count=len(rows),
            max_gap_days=max_gap,
            quality="usable" if len(rows) >= 3 and max_gap <= 30 else "limited",
            index_trends=trends,
            below_expected_ndvi_observations=sum(item.phenology.ndvi_position == "BELOW_EXPECTED" for item in rows),
            persistent_water_deficit_observations=sum(item.water_balance.deficit_flag for item in rows),
            warnings=warnings,
        )
