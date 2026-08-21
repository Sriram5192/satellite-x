from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from ..models import StrictModel


class FieldGovernmentRecord(StrictModel):
    field_id: str
    village_code: str
    mandal_code: str | None = None
    district_code: str | None = None
    crop_type: Literal["cotton", "chilli", "paddy", "other"]
    area_acres: float = Field(gt=0)
    verdict: str
    confidence_pct: float = Field(ge=0, le=100)
    ground_verification_required: bool


class AreaSummary(StrictModel):
    scope_level: Literal["village", "mandal", "district"]
    scope_code: str
    generated_at: datetime
    privacy_status: Literal["released", "suppressed_small_group"] = "released"
    minimum_group_size: int = Field(default=5, ge=5)
    suppression_reason: str | None = None
    field_count: int | None = Field(default=None, ge=0)
    total_agri_acres: float | None = Field(default=None, ge=0)
    crop_acres: dict[str, float] = Field(default_factory=dict)
    verdict_acres: dict[str, float] = Field(default_factory=dict)
    verification_required_fields: int | None = Field(default=None, ge=0)
    low_confidence_fields: int | None = Field(default=None, ge=0)
    contains_personal_data: Literal[False] = False


class VillageSummary(StrictModel):
    village_code: str
    generated_at: datetime
    privacy_status: Literal["released", "suppressed_small_group"] = "released"
    minimum_group_size: int = Field(default=5, ge=5)
    suppression_reason: str | None = None
    field_count: int | None = Field(default=None, ge=0)
    total_agri_acres: float | None = Field(default=None, ge=0)
    crop_acres: dict[str, float] = Field(default_factory=dict)
    verdict_acres: dict[str, float] = Field(default_factory=dict)
    verification_required_fields: int | None = Field(default=None, ge=0)
    low_confidence_fields: int | None = Field(default=None, ge=0)
    contains_personal_data: Literal[False] = False
