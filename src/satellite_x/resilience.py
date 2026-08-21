"""Safe optical/SAR availability routing without cross-sensor fabrication."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import model_validator

from .models import StrictModel, utc_now
from .preprocessing.models import PreprocessingResult, SarFallbackResult


class ResilienceInput(StrictModel):
    field_id: str
    optical: PreprocessingResult
    sar: SarFallbackResult | None = None

    @model_validator(mode="after")
    def field_ids_match(self) -> "ResilienceInput":
        if self.optical.request.field_id != self.field_id:
            raise ValueError("optical field_id does not match")
        if self.sar is not None and self.sar.field_id != self.field_id:
            raise ValueError("SAR field_id does not match")
        return self


class ResilienceDecision(StrictModel):
    field_id: str
    decided_at: datetime
    status: Literal[
        "OPTICAL_PRIMARY",
        "OPTICAL_PRIMARY_SAR_ANCILLARY",
        "SAR_ONLY_UNRESOLVED",
        "NO_USABLE_REMOTE_SENSING_EVIDENCE",
        "LOCATION_OR_URBAN_REJECTED",
    ]
    optical_analytics_allowed: bool
    optical_indices_available: bool
    sar_evidence_available: bool
    diagnosis_allowed: bool
    warnings: list[str]


class ResilienceService:
    def run(self, request: ResilienceInput) -> ResilienceDecision:
        optical = request.optical
        sar_ok = request.sar is not None and request.sar.status == "accepted"
        if optical.status == "accepted":
            return ResilienceDecision(
                field_id=request.field_id,
                decided_at=utc_now(),
                status="OPTICAL_PRIMARY_SAR_ANCILLARY" if sar_ok else "OPTICAL_PRIMARY",
                optical_analytics_allowed=True,
                optical_indices_available=True,
                sar_evidence_available=sar_ok,
                diagnosis_allowed=True,
                warnings=(
                    ["SAR is ancillary context only; optical Set 3 indices remain the diagnosis input."]
                    if sar_ok else []
                ),
            )
        if optical.status in {"rejected_location", "urban_rejected"}:
            return ResilienceDecision(
                field_id=request.field_id,
                decided_at=utc_now(),
                status="LOCATION_OR_URBAN_REJECTED",
                optical_analytics_allowed=False,
                optical_indices_available=False,
                sar_evidence_available=sar_ok,
                diagnosis_allowed=False,
                warnings=["SAR cannot override a location or calibrated urban rejection."],
            )
        if sar_ok:
            return ResilienceDecision(
                field_id=request.field_id,
                decided_at=utc_now(),
                status="SAR_ONLY_UNRESOLVED",
                optical_analytics_allowed=False,
                optical_indices_available=False,
                sar_evidence_available=True,
                diagnosis_allowed=False,
                warnings=[
                    "Only SAR backscatter evidence is available. No optical indices, crop-stress verdict, or agronomic diagnosis is generated."
                ],
            )
        return ResilienceDecision(
            field_id=request.field_id,
            decided_at=utc_now(),
            status="NO_USABLE_REMOTE_SENSING_EVIDENCE",
            optical_analytics_allowed=False,
            optical_indices_available=False,
            sar_evidence_available=False,
            diagnosis_allowed=False,
            warnings=["Neither accepted optical data nor accepted SAR evidence is available."],
        )
