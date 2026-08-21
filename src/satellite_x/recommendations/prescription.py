"""Human-approved, transport-neutral prescription export.

SATELLITE-X never derives application rates from NDVI. Rates enter only through a named
agronomist approval and the output remains experimental until equipment validation.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal

from pydantic import Field

from ..identity import IdentityStore
from ..models import StrictModel, utc_now
from ..security import ArtifactSigner, SignedArtifact, canonical_json_bytes
from .management_zones import ManagementZoneResult


class PrescriptionApproval(StrictModel):
    approval_id: str = Field(min_length=4)
    approved_by: str = Field(min_length=3)
    approved_at: datetime
    input_name: str = Field(min_length=2)
    rate_unit: Literal["kg_per_acre", "litre_per_acre"]
    zone_rates: dict[Literal["low_relative_ndvi", "medium_relative_ndvi", "high_relative_ndvi"], float]
    trial_reference: str = Field(min_length=3)


class ApprovedPrescription(StrictModel):
    field_id: str
    scene_id: str
    generated_at: datetime
    status: Literal["human_approved_experimental"] = "human_approved_experimental"
    approval: PrescriptionApproval
    approval_signature: SignedArtifact
    geojson_feature_collection: dict
    machinery_execution_authorized: Literal[False] = False
    warnings: list[str]


class PrescriptionService:
    def approve(
        self,
        zones: ManagementZoneResult,
        approval: PrescriptionApproval,
        identity: IdentityStore,
        session_token: str,
        signer: ArtifactSigner,
    ) -> ApprovedPrescription:
        principal = identity.require_role(session_token, {"agronomist"})
        if principal.user_id != approval.approved_by:
            raise PermissionError("authenticated agronomist does not match approved_by")
        if zones.human_approval_required is not True:
            raise ValueError("management zones must carry the human-approval gate")
        present = {item.zone for item in zones.zones}
        missing = present - set(approval.zone_rates)
        if missing:
            raise ValueError(f"approved rates missing for zones: {sorted(missing)}")
        features = []
        for item in zones.zones:
            rate = approval.zone_rates[item.zone]
            if rate < 0:
                raise ValueError("application rates cannot be negative")
            features.append({
                "type": "Feature",
                "geometry": item.geometry_geojson,
                "properties": {
                    "zone": item.zone,
                    "relative_ndvi_mean": item.ndvi_mean,
                    "input_name": approval.input_name,
                    "approved_rate": rate,
                    "rate_unit": approval.rate_unit,
                    "approval_id": approval.approval_id,
                },
            })
        generated_at = utc_now()
        approval_payload = {
            "field_id": zones.field_id,
            "scene_id": zones.scene_id,
            "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
            "approval": approval.model_dump(mode="json"),
            "zones_sha256": hashlib.sha256(
                canonical_json_bytes(zones.model_dump(mode="json"))
            ).hexdigest(),
        }
        signed = signer.sign(
            artifact_type="prescription_approval",
            artifact_id=approval.approval_id,
            payload=approval_payload,
            parent_sha256=[approval_payload["zones_sha256"]],
            issued_at=approval.approved_at,
        )
        return ApprovedPrescription(
            field_id=zones.field_id,
            scene_id=zones.scene_id,
            generated_at=generated_at,
            approval=approval,
            approval_signature=signed,
            geojson_feature_collection={"type": "FeatureCollection", "features": features},
            warnings=[
                "GeoJSON is transport-neutral and is not an equipment command.",
                "Machinery execution remains disabled until equipment-specific validation and operator approval.",
            ],
        )
