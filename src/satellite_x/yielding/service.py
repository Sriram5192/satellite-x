"""Yield interface that is unavailable until a locally validated model is supplied."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from ..models import StrictModel, utc_now
from ..security import ArtifactSigner, SignedArtifact


class YieldEstimateRequest(StrictModel):
    field_id: str
    crop_type: Literal["cotton", "chilli", "paddy"]
    district_code: str
    season: str
    features: dict[str, float]


class ApprovedYieldModel(StrictModel):
    model_id: str
    crop_type: Literal["cotton", "chilli", "paddy"]
    district_code: str
    coefficients: dict[str, float]
    intercept_kg_per_acre: float
    residual_mae_kg_per_acre: float = Field(gt=0)
    prediction_interval_half_width_kg_per_acre: float = Field(gt=0)
    validation_r2: float = Field(ge=-1, le=1)
    training_records: int = Field(ge=100)
    independent_seasons: int = Field(ge=2)
    approved_by: str = Field(min_length=3)
    approved_at: datetime
    validation_report_reference: str = Field(min_length=3)
    approval_signature: SignedArtifact | None = None

    def signature_payload(self) -> dict:
        return self.model_dump(mode="json", exclude={"approval_signature"})


class YieldEstimateResult(StrictModel):
    field_id: str
    status: Literal["unavailable_unvalidated_model", "experimental_human_review_required"]
    model_id: str | None = None
    estimate_kg_per_acre: float | None = None
    lower_bound_kg_per_acre: float | None = None
    upper_bound_kg_per_acre: float | None = None
    generated_at: datetime
    production_authorized: Literal[False] = False
    warnings: list[str]


class YieldService:
    def __init__(self, *, trusted_model_keys: dict[str, str] | None = None):
        self.trusted_model_keys = trusted_model_keys or {}

    def estimate(
        self, request: YieldEstimateRequest, model: ApprovedYieldModel | None = None
    ) -> YieldEstimateResult:
        if model is None:
            return YieldEstimateResult(
                field_id=request.field_id,
                status="unavailable_unvalidated_model",
                generated_at=utc_now(),
                warnings=[
                    "Yield is unavailable until multi-season verified local yield labels and an approved validation report exist."
                ],
            )
        if (
            model.approval_signature is None
            or not self.trusted_model_keys
            or model.approval_signature.artifact_type != "approved_yield_model"
            or model.approval_signature.artifact_id != model.model_id
            or not ArtifactSigner.verify(
                model.approval_signature,
                model.signature_payload(),
                trusted_public_keys=self.trusted_model_keys,
            )
        ):
            raise ValueError("yield model approval signature is invalid or untrusted")
        if model.crop_type != request.crop_type or model.district_code != request.district_code:
            raise ValueError("yield model crop/district scope does not match request")
        if model.validation_r2 < 0.5:
            raise ValueError("approved yield model must have validation_r2 >= 0.5")
        missing = set(model.coefficients) - set(request.features)
        if missing:
            raise ValueError(f"yield features missing: {sorted(missing)}")
        estimate = model.intercept_kg_per_acre + sum(
            coefficient * request.features[name]
            for name, coefficient in model.coefficients.items()
        )
        estimate = max(0.0, estimate)
        margin = model.prediction_interval_half_width_kg_per_acre
        return YieldEstimateResult(
            field_id=request.field_id,
            status="experimental_human_review_required",
            model_id=model.model_id,
            estimate_kg_per_acre=round(estimate, 3),
            lower_bound_kg_per_acre=round(max(0.0, estimate - margin), 3),
            upper_bound_kg_per_acre=round(estimate + margin, 3),
            generated_at=utc_now(),
            warnings=[
                "This is an experimental estimate with a held-out residual interval; coverage still requires external local validation and it is not authorized for insurance, credit, or compensation decisions."
            ],
        )
