from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from ..models import StrictModel

Permission = Literal[
    "VIEW_OWN_FIELD",
    "VIEW_VILLAGE_SUMMARY",
    "VIEW_MANDAL_SUMMARY",
    "VIEW_DISTRICT_SUMMARY",
    "VIEW_DAMAGE_HEATMAP",
    "VIEW_CROP_STATISTICS",
    "VIEW_PARCEL_ANOMALIES",
    "VIEW_PARCEL_DETAILS",
    "CREATE_FIELD_VERIFICATION",
    "EXPORT_AGGREGATE_REPORT",
    "EXPORT_CASE_EVIDENCE",
]


class UserContext(StrictModel):
    user_id: str
    role: Literal[
        "farmer", "government_officer", "investigator", "admin",
        "agronomist", "machinery_operator",
    ]
    consent_active: bool
    owned_field_ids: list[str] = Field(default_factory=list)


class GovernmentAuthorization(StrictModel):
    authorization_id: str
    officer_id: str
    department: str
    designation: str
    permission_status: Literal["pending", "approved", "rejected", "revoked", "expired"]
    permissions: list[Permission]
    village_codes: list[str] = Field(default_factory=list)
    mandal_codes: list[str] = Field(default_factory=list)
    district_codes: list[str] = Field(default_factory=list)
    order_reference: str
    valid_from: datetime
    valid_until: datetime
    approved_by: str | None = None


class AccessRequest(StrictModel):
    action: Permission
    field_id: str | None = None
    village_code: str | None = None
    mandal_code: str | None = None
    district_code: str | None = None
    case_id: str | None = None
    purpose: str


class AccessDecision(StrictModel):
    allowed: bool
    reason_code: str
    audit_required: bool
    aggregate_only: bool
