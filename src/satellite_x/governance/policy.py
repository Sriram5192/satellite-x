from __future__ import annotations

from datetime import datetime, timezone

from .models import AccessDecision, AccessRequest, GovernmentAuthorization, UserContext


class PolicyGateway:
    def decide(
        self,
        user: UserContext,
        request: AccessRequest,
        authorization: GovernmentAuthorization | None = None,
        now: datetime | None = None,
    ) -> AccessDecision:
        now = now or datetime.now(timezone.utc)
        if not user.consent_active:
            return AccessDecision(allowed=False, reason_code="CONSENT_INACTIVE", audit_required=True, aggregate_only=True)
        if user.role == "farmer":
            allowed = request.action == "VIEW_OWN_FIELD" and request.field_id in user.owned_field_ids
            return AccessDecision(
                allowed=allowed,
                reason_code="OWN_FIELD_ALLOWED" if allowed else "FARMER_SCOPE_DENIED",
                audit_required=True,
                aggregate_only=False,
            )
        if user.role in {"admin", "agronomist", "machinery_operator"}:
            return AccessDecision(
                allowed=False,
                reason_code="NON_DATA_ROLE_ACCESS_DENIED",
                audit_required=True,
                aggregate_only=True,
            )
        if authorization is None or authorization.officer_id != user.user_id:
            return AccessDecision(allowed=False, reason_code="AUTHORIZATION_MISSING", audit_required=True, aggregate_only=True)
        if authorization.permission_status != "approved":
            return AccessDecision(allowed=False, reason_code="AUTHORIZATION_NOT_APPROVED", audit_required=True, aggregate_only=True)
        if now < authorization.valid_from or now > authorization.valid_until:
            return AccessDecision(allowed=False, reason_code="AUTHORIZATION_OUTSIDE_VALIDITY", audit_required=True, aggregate_only=True)
        if request.action not in authorization.permissions:
            return AccessDecision(allowed=False, reason_code="PERMISSION_DENIED", audit_required=True, aggregate_only=True)
        if request.action == "VIEW_MANDAL_SUMMARY":
            in_scope = request.mandal_code in authorization.mandal_codes
        elif request.action == "VIEW_DISTRICT_SUMMARY":
            in_scope = request.district_code in authorization.district_codes
        elif request.district_code is not None:
            in_scope = request.district_code in authorization.district_codes
        elif request.mandal_code is not None:
            in_scope = request.mandal_code in authorization.mandal_codes
        else:
            in_scope = request.village_code in authorization.village_codes
        if not in_scope:
            return AccessDecision(allowed=False, reason_code="JURISDICTION_DENIED", audit_required=True, aggregate_only=True)
        parcel_detail = request.action in {"VIEW_PARCEL_DETAILS", "EXPORT_CASE_EVIDENCE"}
        if parcel_detail and not request.case_id:
            return AccessDecision(allowed=False, reason_code="CASE_ID_REQUIRED", audit_required=True, aggregate_only=True)
        return AccessDecision(
            allowed=True,
            reason_code="GOVERNMENT_SCOPE_ALLOWED",
            audit_required=True,
            aggregate_only=not parcel_detail,
        )
