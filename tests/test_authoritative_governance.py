from datetime import datetime, timedelta, timezone

from satellite_x.governance import (
    AccessRequest, AuthoritativeGovernanceStore, AuthoritativePolicyGateway,
    CaseRecord, GovernmentAuthorization, UserContext,
)
from satellite_x.security import ArtifactSigner


NOW = datetime(2026, 8, 18, tzinfo=timezone.utc)


def test_signed_authorization_and_case_are_required_for_identifiable_access(tmp_path):
    signer = ArtifactSigner.generate()
    store = AuthoritativeGovernanceStore(
        tmp_path / "governance.db",
        trusted_public_keys={signer.key_id: signer.public_key_base64},
    )
    store.initialize()
    authorization = GovernmentAuthorization(
        authorization_id="AUTH-1", officer_id="INV-1", department="Agriculture",
        designation="Investigator", permission_status="approved",
        permissions=["VIEW_PARCEL_DETAILS", "EXPORT_CASE_EVIDENCE"], village_codes=["V1"],
        order_reference="ORDER-1", valid_from=NOW-timedelta(days=1),
        valid_until=NOW+timedelta(days=10), approved_by="AUTHORITY-1",
    )
    auth_signature = signer.sign(
        artifact_type="government_authorization", artifact_id="AUTH-1",
        payload=authorization.model_dump(mode="json"), issued_at=NOW,
    )
    store.save_authorization(authorization, auth_signature)
    case = CaseRecord(
        case_id="CASE-1", investigator_id="INV-1", authorization_id="AUTH-1",
        purpose="verified damage investigation", field_ids=["F1"], status="active",
        valid_from=NOW-timedelta(hours=1), valid_until=NOW+timedelta(days=2),
        created_by="AUTHORITY-1",
    )
    case_signature = signer.sign(
        artifact_type="investigation_case", artifact_id="CASE-1",
        payload=case.model_dump(mode="json"), parent_sha256=[auth_signature.payload_sha256],
        issued_at=NOW,
    )
    store.save_case(case, case_signature)
    gateway = AuthoritativePolicyGateway(store)
    user = UserContext(user_id="INV-1", role="investigator", consent_active=True)
    allowed = gateway.decide(
        user,
        AccessRequest(action="VIEW_PARCEL_DETAILS", village_code="V1", field_id="F1", case_id="CASE-1", purpose="verified damage investigation"),
        authorization_id="AUTH-1", now=NOW,
    )
    assert allowed.allowed and not allowed.aggregate_only
    wrong_purpose = gateway.decide(
        user,
        AccessRequest(action="VIEW_PARCEL_DETAILS", village_code="V1", field_id="F1", case_id="CASE-1", purpose="different purpose"),
        authorization_id="AUTH-1", now=NOW,
    )
    assert not wrong_purpose.allowed
    assert wrong_purpose.reason_code == "AUTHORITATIVE_CASE_DENIED"


def test_untrusted_issuer_signature_is_rejected(tmp_path):
    trusted = ArtifactSigner.generate(); attacker = ArtifactSigner.generate()
    store = AuthoritativeGovernanceStore(tmp_path / "governance.db", trusted_public_keys={trusted.key_id: trusted.public_key_base64})
    store.initialize()
    authorization = GovernmentAuthorization(
        authorization_id="AUTH-X", officer_id="O1", department="X", designation="X",
        permission_status="approved", permissions=["VIEW_VILLAGE_SUMMARY"], village_codes=["V1"],
        order_reference="X", valid_from=NOW, valid_until=NOW+timedelta(days=1), approved_by="X",
    )
    signed = attacker.sign(artifact_type="government_authorization", artifact_id="AUTH-X", payload=authorization.model_dump(mode="json"), issued_at=NOW)
    import pytest
    with pytest.raises(ValueError, match="signature"):
        store.save_authorization(authorization, signed)
