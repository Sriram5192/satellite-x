"""Set 4 diagnosis contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from ..analytics.models import AnalyticsResult
from ..models import StrictModel


class DiagnosisInput(StrictModel):
    analytics: AnalyticsResult
    quality_tag: Literal["HIGH", "MEDIUM", "LOW"]
    sowing_date_quality: Literal["known", "approximate_month", "unknown"]


class EvidenceItem(StrictModel):
    code: str
    observed: Any
    rule: str
    vote: Literal["SUPPORTS", "OPPOSES", "NEUTRAL"]
    source: str


class ConfidenceBreakdown(StrictModel):
    quality_factor: float = Field(ge=0, le=1)
    completeness_factor: float = Field(ge=0, le=1)
    agreement_factor: float = Field(ge=0, le=1)
    sowing_penalty_pct: float = Field(ge=0, le=100)
    raw_confidence_pct: float
    final_confidence_pct: float = Field(ge=0, le=100)


class DiagnosisResult(StrictModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    field_id: str
    diagnosed_at: datetime
    verdict: Literal[
        "CONFIRMED_WATER_STRESS",
        "SUSPECTED_FUNGAL_RISK",
        "NITROGEN_DEFICIENCY_EVIDENCE",
        "NORMAL_MATURITY",
        "NORMAL_OR_UNRESOLVED",
    ]
    false_alarm_suppressed: bool
    evidence: list[EvidenceItem]
    confidence: ConfidenceBreakdown
    confidence_tag: Literal["HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "LOW_CONFIDENCE"]
    action_telugu: str
    action_english: str
    ground_verification_required: bool
    warnings: list[str] = Field(default_factory=list)
