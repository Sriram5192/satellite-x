"""Equipment-profiled transfer package; never an automatic machine command."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import Field

from ..identity import IdentityStore
from ..models import StrictModel, utc_now
from ..security import ArtifactSigner, SignedArtifact
from .prescription import ApprovedPrescription


class EquipmentProfile(StrictModel):
    equipment_id: str = Field(min_length=3)
    accepted_format: Literal["geojson_feature_collection"] = "geojson_feature_collection"
    minimum_rate: float = Field(ge=0)
    maximum_rate: float = Field(gt=0)
    rate_unit: Literal["kg_per_acre", "litre_per_acre"]
    profile_reference: str = Field(min_length=3)


class OperatorApproval(StrictModel):
    operator_id: str = Field(min_length=3)
    approved_at: datetime
    field_id: str
    prescription_approval_id: str
    equipment_id: str
    calibration_checked: Literal[True]
    boundary_reviewed: Literal[True]
    emergency_stop_checked: Literal[True]


class MachineryTransferResult(StrictModel):
    field_id: str
    equipment_id: str
    generated_at: datetime
    status: Literal["operator_transfer_package"] = "operator_transfer_package"
    format: Literal["geojson_feature_collection"] = "geojson_feature_collection"
    payload: dict
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operator_signature: SignedArtifact
    automatic_execution_authorized: Literal[False] = False
    warnings: list[str]


class MachineryTransferService:
    def build(
        self,
        prescription: ApprovedPrescription,
        equipment: EquipmentProfile,
        operator: OperatorApproval,
        identity: IdentityStore,
        session_token: str,
        signer: ArtifactSigner,
        trusted_approval_keys: dict[str, str],
    ) -> MachineryTransferResult:
        approval_signature = prescription.approval_signature
        approval_payload = {
            "field_id": prescription.field_id,
            "scene_id": prescription.scene_id,
            "generated_at": prescription.generated_at.isoformat().replace("+00:00", "Z"),
            "approval": prescription.approval.model_dump(mode="json"),
            "zones_sha256": approval_signature.parent_sha256[0]
            if approval_signature.parent_sha256 else "",
        }
        if not ArtifactSigner.verify(
            approval_signature,
            approval_payload,
            trusted_public_keys=trusted_approval_keys,
        ):
            raise ValueError("prescription approval signature is invalid or untrusted")
        principal = identity.require_role(session_token, {"machinery_operator"})
        if principal.user_id != operator.operator_id:
            raise PermissionError("authenticated operator does not match operator_id")
        if operator.field_id != prescription.field_id:
            raise ValueError("operator approval field does not match prescription")
        if operator.prescription_approval_id != prescription.approval.approval_id:
            raise ValueError("operator approval does not match prescription approval")
        if operator.equipment_id != equipment.equipment_id:
            raise ValueError("operator approval equipment does not match profile")
        if prescription.approval.rate_unit != equipment.rate_unit:
            raise ValueError("prescription and equipment rate units do not match")
        for feature in prescription.geojson_feature_collection.get("features", []):
            rate = float(feature["properties"]["approved_rate"])
            if not equipment.minimum_rate <= rate <= equipment.maximum_rate:
                raise ValueError("approved rate is outside equipment profile limits")
        payload = {
            **prescription.geojson_feature_collection,
            "satellite_x_transfer": {
                "field_id": prescription.field_id,
                "equipment_id": equipment.equipment_id,
                "profile_reference": equipment.profile_reference,
                "operator_id": operator.operator_id,
                "operator_approved_at": operator.approved_at.isoformat(),
                "automatic_execution": False,
            },
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        payload_sha256 = hashlib.sha256(canonical).hexdigest()
        generated_at = utc_now()
        operator_payload = {
            "field_id": prescription.field_id,
            "equipment_id": equipment.equipment_id,
            "payload_sha256": payload_sha256,
            "operator": operator.model_dump(mode="json"),
            "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        }
        operator_signature = signer.sign(
            artifact_type="machinery_operator_approval",
            artifact_id=f"{operator.operator_id}:{prescription.approval.approval_id}",
            payload=operator_payload,
            parent_sha256=[payload_sha256, approval_signature.payload_sha256],
            issued_at=operator.approved_at,
        )
        return MachineryTransferResult(
            field_id=prescription.field_id,
            equipment_id=equipment.equipment_id,
            generated_at=generated_at,
            payload=payload,
            payload_sha256=payload_sha256,
            operator_signature=operator_signature,
            warnings=[
                "This file is an operator transfer package, not an automatic machinery command.",
                "The operator remains responsible for equipment import review, calibration, boundary safety and field execution.",
            ],
        )
