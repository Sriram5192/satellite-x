from datetime import datetime, timezone

from satellite_x.identity import IdentityStore
from satellite_x.recommendations.management_zones import ManagementZoneFeature, ManagementZoneResult
from satellite_x.recommendations.machinery import EquipmentProfile, MachineryTransferService, OperatorApproval
from satellite_x.recommendations.prescription import PrescriptionApproval, PrescriptionService
from satellite_x.security import ArtifactSigner


NOW = datetime.now(timezone.utc)


def test_prescription_requires_named_human_rates_and_never_authorizes_machinery(tmp_path):
    zones = ManagementZoneResult(
        field_id="F1", scene_id="S1", generated_at=NOW,
        thresholds={"lower_tertile": 0.3, "upper_tertile": 0.5},
        zones=[ManagementZoneFeature(
            zone="low_relative_ndvi", pixel_count=3, approximate_acres=0.1,
            ndvi_mean=0.2,
            geometry_geojson={"type": "Polygon", "coordinates": [[[80,16],[81,16],[81,17],[80,16]]]},
        )], warnings=["experimental"],
    )
    approval = PrescriptionApproval(
        approval_id="APP-1", approved_by="AGRONOMIST-1", approved_at=NOW,
        input_name="approved input", rate_unit="kg_per_acre",
        zone_rates={"low_relative_ndvi": 12}, trial_reference="TRIAL-1",
    )
    identity = IdentityStore(tmp_path / "identity.db"); identity.initialize()
    identity.register("AGRONOMIST-1", "agronomist password", role="agronomist", now=NOW)
    agronomist_token = identity.login("AGRONOMIST-1", "agronomist password", now=NOW)
    signer = ArtifactSigner.generate()
    result = PrescriptionService().approve(
        zones, approval, identity, agronomist_token, signer
    )
    assert ArtifactSigner.verify(
        result.approval_signature,
        {
            "field_id": result.field_id,
            "scene_id": result.scene_id,
            "generated_at": result.generated_at.isoformat().replace("+00:00", "Z"),
            "approval": result.approval.model_dump(mode="json"),
            "zones_sha256": result.approval_signature.parent_sha256[0],
        },
        trusted_public_keys={signer.key_id: signer.public_key_base64},
    )
    assert result.status == "human_approved_experimental"
    assert result.machinery_execution_authorized is False
    assert result.geojson_feature_collection["features"][0]["properties"]["approved_rate"] == 12

    equipment = EquipmentProfile(
        equipment_id="SPREADER-1", minimum_rate=0, maximum_rate=30,
        rate_unit="kg_per_acre", profile_reference="OEM-PROFILE-1",
    )
    operator = OperatorApproval(
        operator_id="OPERATOR-1", approved_at=NOW, field_id="F1",
        prescription_approval_id="APP-1", equipment_id="SPREADER-1",
        calibration_checked=True, boundary_reviewed=True, emergency_stop_checked=True,
    )
    identity.register("OPERATOR-1", "operator password", role="machinery_operator", now=NOW)
    operator_token = identity.login("OPERATOR-1", "operator password", now=NOW)
    transfer = MachineryTransferService().build(
        result, equipment, operator, identity, operator_token, signer,
        {signer.key_id: signer.public_key_base64},
    )
    assert transfer.status == "operator_transfer_package"
    assert transfer.automatic_execution_authorized is False
    assert transfer.payload["satellite_x_transfer"]["automatic_execution"] is False
