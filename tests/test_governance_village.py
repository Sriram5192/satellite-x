from datetime import datetime, timedelta, timezone

from satellite_x.governance.models import (
    AccessRequest, GovernmentAuthorization, UserContext,
)
from satellite_x.governance.policy import PolicyGateway
from satellite_x.government.area import AreaAggregator
from satellite_x.government.models import FieldGovernmentRecord
from satellite_x.government.village import VillageAggregator


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


def authorization():
    return GovernmentAuthorization(
        authorization_id="A1", officer_id="O1", department="Agriculture",
        designation="MAO", permission_status="approved",
        permissions=["VIEW_VILLAGE_SUMMARY", "VIEW_MANDAL_SUMMARY", "VIEW_DISTRICT_SUMMARY", "VIEW_PARCEL_DETAILS"],
        village_codes=["V1"], mandal_codes=["M1"], district_codes=["D1"], order_reference="ORDER-1",
        valid_from=NOW-timedelta(days=1), valid_until=NOW+timedelta(days=30),
        approved_by="D1",
    )


def test_farmer_can_only_view_owned_field():
    gateway = PolicyGateway()
    user = UserContext(user_id="U1", role="farmer", consent_active=True, owned_field_ids=["F1"])
    assert gateway.decide(user, AccessRequest(action="VIEW_OWN_FIELD", field_id="F1", purpose="advisory"), now=NOW).allowed
    assert not gateway.decide(user, AccessRequest(action="VIEW_OWN_FIELD", field_id="F2", purpose="advisory"), now=NOW).allowed


def test_admin_role_does_not_bypass_field_data_policy():
    decision = PolicyGateway().decide(
        UserContext(user_id="ADMIN-1", role="admin", consent_active=True),
        AccessRequest(action="VIEW_PARCEL_DETAILS", village_code="V1", field_id="F1", purpose="support"),
        now=NOW,
    )
    assert not decision.allowed
    assert decision.reason_code == "NON_DATA_ROLE_ACCESS_DENIED"


def test_government_scope_and_case_gate():
    gateway = PolicyGateway()
    user = UserContext(user_id="O1", role="government_officer", consent_active=True)
    aggregate = gateway.decide(
        user, AccessRequest(action="VIEW_VILLAGE_SUMMARY", village_code="V1", purpose="damage"), authorization(), NOW
    )
    assert aggregate.allowed and aggregate.aggregate_only
    denied = gateway.decide(
        user, AccessRequest(action="VIEW_PARCEL_DETAILS", village_code="V1", field_id="F1", purpose="investigation"), authorization(), NOW
    )
    assert not denied.allowed and denied.reason_code == "CASE_ID_REQUIRED"
    allowed = gateway.decide(
        user, AccessRequest(action="VIEW_PARCEL_DETAILS", village_code="V1", field_id="F1", case_id="C1", purpose="investigation"), authorization(), NOW
    )
    assert allowed.allowed and not allowed.aggregate_only


def test_village_summary_contains_no_personal_data():
    fields = [
        FieldGovernmentRecord(field_id="F1", village_code="V1", crop_type="chilli", area_acres=2, verdict="NORMAL_OR_UNRESOLVED", confidence_pct=70, ground_verification_required=False),
        FieldGovernmentRecord(field_id="F2", village_code="V1", crop_type="paddy", area_acres=3, verdict="CONFIRMED_WATER_STRESS", confidence_pct=45, ground_verification_required=True),
        FieldGovernmentRecord(field_id="F3", village_code="V2", crop_type="cotton", area_acres=4, verdict="NORMAL", confidence_pct=80, ground_verification_required=False),
    ]
    summary = VillageAggregator(clock=lambda: NOW).aggregate("V1", fields)
    assert summary.privacy_status == "suppressed_small_group"
    assert summary.field_count is None
    assert summary.total_agri_acres is None
    assert summary.crop_acres == {}
    assert summary.contains_personal_data is False

    released_fields = fields[:2] + [
        FieldGovernmentRecord(field_id=f"V1-EXTRA-{i}", village_code="V1", crop_type="chilli", area_acres=1, verdict="NORMAL", confidence_pct=70, ground_verification_required=False)
        for i in range(3)
    ]
    released = VillageAggregator(clock=lambda: NOW).aggregate("V1", released_fields)
    assert released.privacy_status == "released"
    assert released.field_count == 5
    assert released.total_agri_acres == 8
    assert released.crop_acres == {"chilli": 5.0, "paddy": 3.0}
    assert released.verification_required_fields == 1
    assert released.low_confidence_fields == 1


def test_mandal_and_district_aggregation_are_separately_authorized_and_anonymous():
    fields = [
        FieldGovernmentRecord(field_id="F1", village_code="V1", mandal_code="M1", district_code="D1", crop_type="chilli", area_acres=2, verdict="NORMAL", confidence_pct=70, ground_verification_required=False),
        FieldGovernmentRecord(field_id="F2", village_code="V2", mandal_code="M1", district_code="D1", crop_type="paddy", area_acres=3, verdict="STRESS", confidence_pct=40, ground_verification_required=True),
        FieldGovernmentRecord(field_id="F3", village_code="V3", mandal_code="M2", district_code="D1", crop_type="cotton", area_acres=4, verdict="NORMAL", confidence_pct=80, ground_verification_required=False),
        FieldGovernmentRecord(field_id="F4", village_code="V4", mandal_code="M1", district_code="D1", crop_type="chilli", area_acres=1, verdict="NORMAL", confidence_pct=75, ground_verification_required=False),
        FieldGovernmentRecord(field_id="F5", village_code="V5", mandal_code="M1", district_code="D1", crop_type="paddy", area_acres=1, verdict="NORMAL", confidence_pct=75, ground_verification_required=False),
        FieldGovernmentRecord(field_id="F6", village_code="V6", mandal_code="M1", district_code="D1", crop_type="other", area_acres=1, verdict="NORMAL", confidence_pct=75, ground_verification_required=False),
    ]
    aggregator = AreaAggregator(clock=lambda: NOW)
    mandal = aggregator.aggregate("mandal", "M1", fields)
    district = aggregator.aggregate("district", "D1", fields)
    assert mandal.total_agri_acres == 8 and mandal.field_count == 5
    assert district.total_agri_acres == 12 and district.field_count == 6
    assert not mandal.contains_personal_data and not district.contains_personal_data

    gateway = PolicyGateway()
    user = UserContext(user_id="O1", role="government_officer", consent_active=True)
    assert gateway.decide(user, AccessRequest(action="VIEW_MANDAL_SUMMARY", mandal_code="M1", purpose="crop monitoring"), authorization(), NOW).allowed
    assert gateway.decide(user, AccessRequest(action="VIEW_DISTRICT_SUMMARY", district_code="D1", purpose="crop monitoring"), authorization(), NOW).allowed
    assert not gateway.decide(user, AccessRequest(action="VIEW_MANDAL_SUMMARY", mandal_code="M2", purpose="crop monitoring"), authorization(), NOW).allowed
