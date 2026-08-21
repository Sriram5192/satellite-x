"""Validated contracts for Set 2 preprocessing."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from ..models import SatelliteScene, StrictModel


class PreprocessingInput(StrictModel):
    field_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    boundary_geojson: dict[str, Any]
    analysis_date: date
    scan_range_days: int = Field(default=30, ge=1, le=180)
    expansion_days: int = Field(default=30, ge=1, le=180)
    location_blocking: bool = False
    location_reason: str | None = None

    @field_validator("boundary_geojson")
    @classmethod
    def polygon_only(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("boundary_geojson must be Polygon or MultiPolygon")
        if not value.get("coordinates"):
            raise ValueError("boundary_geojson coordinates are empty")
        return value


class SceneFieldQuality(StrictModel):
    scene_id: str
    acquired_at: datetime
    scene_cloud_pct: float = Field(ge=0, le=100)
    in_original_range: bool
    total_field_pixels: int = Field(ge=0)
    valid_field_pixels: int = Field(ge=0)
    field_valid_pct: float = Field(ge=0, le=100)
    scl_counts: dict[str, int]
    quality: Literal["HIGH", "MEDIUM", "LOW"]
    rejection_reasons: list[str] = Field(default_factory=list)


class UrbanGateResult(StrictModel):
    spectral_valid_pixels: int = Field(ge=0)
    spectral_valid_pct: float = Field(ge=0, le=100)
    mean_ndvi: float | None = None
    mean_ndbi: float | None = None
    built_pixel_pct: float | None = Field(default=None, ge=0, le=100)
    urban_rejected: bool
    condition: str


class SarFallbackInput(StrictModel):
    field_id: str
    boundary_geojson: dict[str, Any]
    analysis_date: date
    scan_range_days: int = Field(default=30, ge=1, le=180)


class SarFallbackResult(StrictModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    field_id: str
    processed_at: datetime
    status: Literal["accepted", "no_scene", "processing_error"]
    scene_id: str | None = None
    scene_date: date | None = None
    orbit_state: str | None = None
    valid_pixels: int = Field(default=0, ge=0)
    vv_db_mean: float | None = None
    vh_db_mean: float | None = None
    vv_minus_vh_db_mean: float | None = None
    warnings: list[str] = Field(default_factory=list)


class PreprocessingResult(StrictModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    request: PreprocessingInput
    processed_at: datetime
    status: Literal[
        "accepted",
        "rejected_location",
        "no_satellite_scene",
        "no_acceptable_scene",
        "urban_rejected",
        "processing_error",
    ]
    selected_scene: SatelliteScene | None = None
    selected_quality: SceneFieldQuality | None = None
    urban_gate: UrbanGateResult | None = None
    candidates: list[SceneFieldQuality] = Field(default_factory=list)
    expanded_search_used: bool = False
    valid_scl_classes: list[int] = Field(default_factory=lambda: [4, 5, 6, 7])
    warnings: list[str] = Field(default_factory=list)
