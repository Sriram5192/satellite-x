"""Leakage-resistant candidate training from verified local yield labels.

This module creates a candidate only. A named human approval is still required before the
existing experimental estimator can consume it, and production authorization remains false.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

import numpy as np
from pydantic import Field, model_validator

from ..identity import IdentityStore
from ..models import StrictModel, utc_now
from ..security import ArtifactSigner, SignedArtifact
from .service import ApprovedYieldModel


class VerifiedYieldRecord(StrictModel):
    field_id: str
    crop_type: Literal["cotton", "chilli", "paddy"]
    district_code: str
    season: str
    yield_kg_per_acre: float = Field(gt=0)
    features: dict[str, float]
    verification_source: Literal["weighbridge", "crop_cutting_experiment", "audited_procurement"]
    evidence_reference: str = Field(min_length=3)
    evidence_signature: SignedArtifact | None = None

    def evidence_payload(self) -> dict:
        return self.model_dump(mode="json", exclude={"evidence_signature"})


class YieldTrainingInput(StrictModel):
    crop_type: Literal["cotton", "chilli", "paddy"]
    district_code: str
    dataset_purpose: Literal["production_verified", "deterministic_validation_fixture"]
    records: list[VerifiedYieldRecord] = Field(min_length=100)
    ridge_alpha: float = Field(default=1.0, ge=0)

    @model_validator(mode="after")
    def validate_dataset(self) -> "YieldTrainingInput":
        if any(row.crop_type != self.crop_type or row.district_code != self.district_code for row in self.records):
            raise ValueError("all yield records must match crop and district scope")
        feature_sets = {tuple(sorted(row.features)) for row in self.records}
        if len(feature_sets) != 1 or not next(iter(feature_sets)):
            raise ValueError("all yield records must contain the same non-empty feature set")
        if len({row.season for row in self.records}) < 2:
            raise ValueError("at least two independent seasons are required")
        identities = [(row.field_id, row.season) for row in self.records]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate field/season yield record")
        return self


class YieldModelCandidate(StrictModel):
    candidate_id: str
    crop_type: str
    district_code: str
    feature_names: list[str]
    coefficients: dict[str, float]
    intercept_kg_per_acre: float
    validation_method: Literal["leave_one_season_out"] = "leave_one_season_out"
    validation_r2: float
    validation_mae_kg_per_acre: float = Field(ge=0)
    validation_rmse_kg_per_acre: float = Field(ge=0)
    validation_abs_residual_q95_kg_per_acre: float = Field(gt=0)
    training_records: int
    independent_seasons: int
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_purpose: Literal["production_verified", "deterministic_validation_fixture"]
    generated_at: datetime
    status: Literal["candidate_requires_human_approval", "validation_fixture_only"]
    model_signature: SignedArtifact | None = None
    production_authorized: Literal[False] = False

    def signature_payload(self) -> dict:
        return self.model_dump(mode="json", exclude={"model_signature"})


class YieldModelHumanApproval(StrictModel):
    model_id: str
    approved_by: str = Field(min_length=3)
    approved_at: datetime
    validation_report_reference: str = Field(min_length=3)
    accepted_candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def candidate_digest(candidate: YieldModelCandidate) -> str:
    payload = candidate.model_dump(
        mode="json", exclude={"generated_at", "model_signature"}
    )
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class YieldTrainingService:
    def __init__(
        self,
        *,
        candidate_signer: ArtifactSigner,
        trusted_label_keys: dict[str, str] | None = None,
        trusted_candidate_keys: dict[str, str] | None = None,
    ):
        self.candidate_signer = candidate_signer
        self.trusted_label_keys = trusted_label_keys or {}
        self.trusted_candidate_keys = trusted_candidate_keys or {
            candidate_signer.key_id: candidate_signer.public_key_base64
        }

    @staticmethod
    def _fit(x: np.ndarray, y: np.ndarray, alpha: float) -> tuple[np.ndarray, float]:
        means = x.mean(axis=0)
        scales = x.std(axis=0)
        scales[scales < 1e-12] = 1.0
        z = (x - means) / scales
        beta = np.linalg.solve(z.T @ z + alpha * np.eye(z.shape[1]), z.T @ (y - y.mean()))
        coefficients = beta / scales
        intercept = float(y.mean() - means @ coefficients)
        return coefficients, intercept

    def train(self, request: YieldTrainingInput) -> YieldModelCandidate:
        if request.dataset_purpose == "production_verified":
            if not self.trusted_label_keys:
                raise ValueError("production yield training requires trusted label issuer keys")
            for row in request.records:
                signed = row.evidence_signature
                artifact_id = f"{row.field_id}:{row.season}"
                if (
                    signed is None
                    or signed.artifact_type != "verified_yield_label"
                    or signed.artifact_id != artifact_id
                    or not ArtifactSigner.verify(
                        signed,
                        row.evidence_payload(),
                        trusted_public_keys=self.trusted_label_keys,
                    )
                ):
                    raise ValueError(f"yield label signature is invalid for {artifact_id}")
        names = sorted(request.records[0].features)
        x = np.asarray([[row.features[name] for name in names] for row in request.records], dtype=float)
        y = np.asarray([row.yield_kg_per_acre for row in request.records], dtype=float)
        seasons = np.asarray([row.season for row in request.records])
        predictions = np.empty_like(y)
        for season in sorted(set(seasons)):
            train = seasons != season
            test = ~train
            coefficients, intercept = self._fit(x[train], y[train], request.ridge_alpha)
            predictions[test] = intercept + x[test] @ coefficients
        residuals = y - predictions
        denominator = float(np.sum((y - y.mean()) ** 2))
        r2 = 1.0 - float(np.sum(residuals**2)) / denominator if denominator > 0 else 0.0
        mae = float(np.mean(np.abs(residuals)))
        rmse = float(np.sqrt(np.mean(residuals**2)))
        q95 = float(np.quantile(np.abs(residuals), 0.95, method="higher"))
        coefficients, intercept = self._fit(x, y, request.ridge_alpha)
        canonical_records = [row.model_dump(mode="json") for row in sorted(request.records, key=lambda item: (item.season, item.field_id))]
        dataset_hash = hashlib.sha256(json.dumps(canonical_records, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        candidate_id = f"yield-{request.crop_type}-{request.district_code}-{dataset_hash[:12]}"
        candidate = YieldModelCandidate(
            candidate_id=candidate_id,
            crop_type=request.crop_type,
            district_code=request.district_code,
            feature_names=names,
            coefficients={name: round(float(value), 10) for name, value in zip(names, coefficients)},
            intercept_kg_per_acre=round(intercept, 10),
            validation_r2=round(r2, 6),
            validation_mae_kg_per_acre=round(mae, 6),
            validation_rmse_kg_per_acre=round(rmse, 6),
            validation_abs_residual_q95_kg_per_acre=round(max(q95, 1e-6), 6),
            training_records=len(request.records),
            independent_seasons=len(set(seasons)),
            dataset_sha256=dataset_hash,
            dataset_purpose=request.dataset_purpose,
            generated_at=utc_now(),
            status=(
                "candidate_requires_human_approval"
                if request.dataset_purpose == "production_verified"
                else "validation_fixture_only"
            ),
        )
        signed = self.candidate_signer.sign(
            artifact_type="yield_model_candidate",
            artifact_id=candidate.candidate_id,
            payload=candidate.signature_payload(),
            parent_sha256=[candidate.dataset_sha256],
            issued_at=candidate.generated_at,
        )
        return candidate.model_copy(update={"model_signature": signed})

    def approve(
        self,
        candidate: YieldModelCandidate,
        approval: YieldModelHumanApproval,
        identity: IdentityStore,
        session_token: str,
        *,
        minimum_r2: float = 0.5,
    ) -> ApprovedYieldModel:
        principal = identity.require_role(session_token, {"agronomist"})
        if principal.user_id != approval.approved_by:
            raise PermissionError("authenticated agronomist does not match approved_by")
        if (
            candidate.model_signature is None
            or candidate.model_signature.artifact_type != "yield_model_candidate"
            or candidate.model_signature.artifact_id != candidate.candidate_id
            or not ArtifactSigner.verify(
                candidate.model_signature,
                candidate.signature_payload(),
                trusted_public_keys=self.trusted_candidate_keys,
            )
        ):
            raise ValueError("yield candidate signature is invalid")
        if candidate.dataset_purpose != "production_verified":
            raise ValueError("validation fixture candidates cannot be approved")
        if candidate.validation_r2 < minimum_r2:
            raise ValueError(f"candidate validation_r2 is below {minimum_r2}")
        if approval.accepted_candidate_sha256 != candidate_digest(candidate):
            raise ValueError("approval candidate hash does not match")
        model = ApprovedYieldModel(
            model_id=approval.model_id,
            crop_type=candidate.crop_type,
            district_code=candidate.district_code,
            coefficients=candidate.coefficients,
            intercept_kg_per_acre=candidate.intercept_kg_per_acre,
            residual_mae_kg_per_acre=max(candidate.validation_mae_kg_per_acre, 1e-6),
            prediction_interval_half_width_kg_per_acre=(
                candidate.validation_abs_residual_q95_kg_per_acre
            ),
            validation_r2=candidate.validation_r2,
            training_records=candidate.training_records,
            independent_seasons=candidate.independent_seasons,
            approved_by=approval.approved_by,
            approved_at=approval.approved_at,
            validation_report_reference=approval.validation_report_reference,
        )
        signature = self.candidate_signer.sign(
            artifact_type="approved_yield_model",
            artifact_id=model.model_id,
            payload=model.signature_payload(),
            parent_sha256=[
                candidate.model_signature.payload_sha256,
                candidate.dataset_sha256,
            ],
            issued_at=approval.approved_at,
        )
        return model.model_copy(update={"approval_signature": signature})
