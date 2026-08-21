"""Contracts for the polygon recovery and confirmation engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ..models import StrictModel


class PolygonRecoveryInput(StrictModel):
    field_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    acres: float = Field(gt=0, le=1_000_000)
    location_consent: Literal[True]
    country_code: str = Field(default="IN", pattern=r"^[A-Z]{2}$")
    subdivision_code: str | None = Field(default=None, pattern=r"^[A-Z0-9]{1,3}$")
    search_radius_m: float = Field(default=300.0, ge=30, le=1000)
    gps_tolerance_m: float = Field(default=30.0, ge=5, le=100)

    @field_validator("country_code", "subdivision_code", mode="before")
    @classmethod
    def normalize_codes(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value


class LocationEvidence(StrictModel):
    source: Literal["nominatim_live", "cache"]
    category: str | None = None
    feature_type: str | None = None
    name: str | None = None
    display_name: str | None = None
    matched_latitude: float | None = Field(default=None, ge=-90, le=90)
    matched_longitude: float | None = Field(default=None, ge=-180, le=180)
    feature_distance_m: float | None = Field(default=None, ge=0)
    country_code: str | None = None
    subdivision_code: str | None = None
    blocking: bool
    reason_code: str
    raw_osm_type: str | None = None
    raw_osm_id: int | None = None


class BoundaryCandidate(StrictModel):
    candidate_id: str
    source: Literal["ftw_global_2024", "ftw_global_2025"]
    model_name: Literal["FTW_PRUE"] = "FTW_PRUE"
    year: Literal[2024, 2025]
    geometry_geojson: dict[str, Any]
    area_m2: float = Field(gt=0)
    area_acres: float = Field(gt=0)
    perimeter_m: float = Field(gt=0)
    source_confidence: float | None = Field(default=None, ge=0, le=100)
    contains_input_point: bool
    point_distance_m: float = Field(ge=0)
    area_difference_pct: float = Field(ge=0)
    score_pct: float = Field(ge=0, le=100)
    score_components: dict[str, float]
    quality: Literal["HIGH", "MEDIUM", "LOW"]
    legal_boundary: Literal[False] = False

    @field_validator("geometry_geojson")
    @classmethod
    def polygon_only(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("candidate geometry must be Polygon or MultiPolygon")
        return value


class PolygonRecoveryResult(StrictModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    request: PolygonRecoveryInput
    checked_at: datetime
    status: Literal[
        "rejected_location",
        "preflight_unavailable",
        "no_candidate",
        "candidates_found",
    ]
    location: LocationEvidence | None = None
    candidates: list[BoundaryCandidate] = Field(default_factory=list)
    selected_candidate_id: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def status_is_consistent(self) -> "PolygonRecoveryResult":
        if self.status == "candidates_found" and not self.candidates:
            raise ValueError("candidates_found status requires candidates")
        if self.status != "candidates_found" and self.selected_candidate_id is not None:
            raise ValueError("selected_candidate_id requires candidates_found status")
        return self


class GeometryValidation(StrictModel):
    valid: bool
    geometry_type: Literal["Polygon", "MultiPolygon"]
    area_m2: float = Field(gt=0)
    area_acres: float = Field(gt=0)
    perimeter_m: float = Field(gt=0)
    contains_input_point: bool
    point_distance_m: float = Field(ge=0)
    area_difference_pct: float = Field(ge=0)
    repaired: bool
    warnings: list[str] = Field(default_factory=list)


class BoundaryConfirmation(StrictModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    field_id: str
    confirmed_at: datetime
    boundary_source: Literal[
        "ftw_global_2024",
        "ftw_global_2025",
        "user_drawn",
        "official_fmb",
    ]
    source_candidate_id: str | None = None
    boundary_geojson: dict[str, Any]
    validation: GeometryValidation
    user_confirmed: Literal[True]
    legal_boundary: bool
    provenance: dict[str, Any]

    @field_validator("boundary_geojson")
    @classmethod
    def confirmed_polygon_only(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("confirmed boundary must be Polygon or MultiPolygon")
        return value
