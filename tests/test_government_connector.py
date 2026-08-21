from datetime import datetime, timedelta, timezone

from satellite_x.governance.models import AccessRequest, GovernmentAuthorization, UserContext
from satellite_x.integrations.government import GovernmentConnectorConfig, GovernmentRecordGateway


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


class Response:
    headers = {"content-type": "application/json"}
    def raise_for_status(self): pass
    def json(self): return {"record_id": "OFFICIAL-1"}


class Session:
    def __init__(self): self.call = None
    def get(self, url, **kwargs): self.call = (url, kwargs); return Response()


def authorization():
    return GovernmentAuthorization(
        authorization_id="AUTH-1", officer_id="O1", department="Agriculture", designation="MAO",
        permission_status="approved", permissions=["VIEW_VILLAGE_SUMMARY"], village_codes=["V1"],
        order_reference="ORDER-1", valid_from=NOW-timedelta(days=1), valid_until=NOW+timedelta(days=1), approved_by="D1",
    )


def test_official_connector_rejects_unsigned_caller_authorization():
    user = UserContext(user_id="O1", role="government_officer", consent_active=True)
    access = AccessRequest(action="VIEW_VILLAGE_SUMMARY", village_code="V1", purpose="authorized crop summary")
    config = GovernmentConnectorConfig(provider="agristack", base_url="https://official.example/api/", credential_env="OFFICIAL_TOKEN", enabled=False)
    result = GovernmentRecordGateway(config).fetch(
        user=user, access=access, authorization=authorization(),
        resource_path="records", now=NOW,
    )
    assert result.status == "denied"
    assert result.reason_code == "AUTHORITATIVE_GOVERNANCE_STORE_REQUIRED"


def test_official_connector_requires_policy_enablement_and_external_credential(monkeypatch):
    user = UserContext(user_id="O1", role="government_officer", consent_active=True)
    access = AccessRequest(action="VIEW_VILLAGE_SUMMARY", village_code="V1", purpose="authorized crop summary")
    config = GovernmentConnectorConfig(provider="agristack", base_url="https://official.example/api/", credential_env="OFFICIAL_TOKEN", enabled=False)
    result = GovernmentRecordGateway(config, allow_unsigned_test_authorization=True).fetch(user=user, access=access, authorization=authorization(), resource_path="records", now=NOW)
    assert result.status == "activation_required"
    assert result.reason_code == "CONNECTOR_DISABLED"

    session = Session()
    enabled = config.model_copy(update={"enabled": True})
    monkeypatch.setenv("OFFICIAL_TOKEN", "secret-token")
    result = GovernmentRecordGateway(enabled, session=session, allow_unsigned_test_authorization=True).fetch(user=user, access=access, authorization=authorization(), resource_path="records", now=NOW)
    assert result.status == "allowed" and result.aggregate_only
    assert session.call[1]["headers"]["Authorization"] == "Bearer secret-token"
    assert session.call[1]["headers"]["X-SATELLITE-X-Authorization"] == "AUTH-1"


def test_official_connector_denies_out_of_jurisdiction_before_network(monkeypatch):
    session = Session()
    monkeypatch.setenv("OFFICIAL_TOKEN", "secret-token")
    config = GovernmentConnectorConfig(provider="agristack", base_url="https://official.example/api/", credential_env="OFFICIAL_TOKEN", enabled=True)
    result = GovernmentRecordGateway(config, session=session, allow_unsigned_test_authorization=True).fetch(
        user=UserContext(user_id="O1", role="government_officer", consent_active=True),
        access=AccessRequest(action="VIEW_VILLAGE_SUMMARY", village_code="V2", purpose="out of scope"),
        authorization=authorization(), resource_path="records", now=NOW,
    )
    assert result.status == "denied" and result.reason_code == "JURISDICTION_DENIED"
    assert session.call is None
