"""Official JSON API gateway; never scrapes or bypasses CAPTCHA/OTP."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Literal
from urllib.parse import urljoin, urlparse

import requests
from pydantic import Field, model_validator

from ..governance.authoritative import AuthoritativePolicyGateway
from ..governance.models import AccessRequest, GovernmentAuthorization, UserContext
from ..governance.policy import PolicyGateway
from ..models import StrictModel, utc_now


class GovernmentConnectorConfig(StrictModel):
    provider: Literal["meebhoomi", "bhunaksha", "agristack", "authorized_custom"]
    base_url: str
    credential_env: str
    enabled: bool = False
    timeout_seconds: float = Field(default=20, gt=0, le=60)

    @model_validator(mode="after")
    def safe_base_url(self) -> "GovernmentConnectorConfig":
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("connector base_url must be HTTP(S)")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("non-local official connector must use HTTPS")
        return self


class GovernmentFetchInput(StrictModel):
    config: GovernmentConnectorConfig
    user: UserContext
    access: AccessRequest
    authorization: GovernmentAuthorization
    resource_path: str
    params: dict[str, str] = Field(default_factory=dict)


class GovernmentConnectorResult(StrictModel):
    provider: str
    status: Literal["allowed", "denied", "activation_required", "upstream_error"]
    reason_code: str
    fetched_at: datetime
    aggregate_only: bool
    authorization_id: str | None = None
    source_url: str | None = None
    record: dict | list | None = None
    warnings: list[str] = Field(default_factory=list)


class GovernmentRecordGateway:
    def __init__(
        self,
        config: GovernmentConnectorConfig,
        *,
        session: requests.Session | None = None,
        authoritative_policy: AuthoritativePolicyGateway | None = None,
        allow_unsigned_test_authorization: bool = False,
    ):
        self.config = config
        self.session = session or requests.Session()
        self.authoritative_policy = authoritative_policy
        self.allow_unsigned_test_authorization = allow_unsigned_test_authorization
        self.policy = PolicyGateway()

    def fetch(
        self,
        *,
        user: UserContext,
        access: AccessRequest,
        authorization: GovernmentAuthorization,
        resource_path: str,
        params: dict[str, str] | None = None,
        now: datetime | None = None,
    ) -> GovernmentConnectorResult:
        if self.authoritative_policy is not None:
            authoritative = self.authoritative_policy.store.get_authorization(
                authorization.authorization_id
            )
            if authoritative is None:
                decision = self.authoritative_policy.decide(
                    user, access,
                    authorization_id=authorization.authorization_id,
                    now=now,
                )
            else:
                authorization = authoritative
                decision = self.authoritative_policy.decide(
                    user, access,
                    authorization_id=authorization.authorization_id,
                    now=now,
                )
        elif self.allow_unsigned_test_authorization:
            decision = self.policy.decide(user, access, authorization, now)
        else:
            return GovernmentConnectorResult(
                provider=self.config.provider,
                status="denied",
                reason_code="AUTHORITATIVE_GOVERNANCE_STORE_REQUIRED",
                fetched_at=utc_now(),
                aggregate_only=True,
                authorization_id=authorization.authorization_id,
                warnings=["Unsigned caller-supplied authorization is never accepted."],
            )
        if not decision.allowed:
            return GovernmentConnectorResult(
                provider=self.config.provider, status="denied",
                reason_code=decision.reason_code, fetched_at=utc_now(),
                aggregate_only=decision.aggregate_only,
                authorization_id=authorization.authorization_id,
            )
        if not self.config.enabled:
            return GovernmentConnectorResult(
                provider=self.config.provider, status="activation_required",
                reason_code="CONNECTOR_DISABLED", fetched_at=utc_now(),
                aggregate_only=decision.aggregate_only,
                authorization_id=authorization.authorization_id,
                warnings=["Official connector is disabled until API/MoU activation."],
            )
        token = os.getenv(self.config.credential_env)
        if not token:
            return GovernmentConnectorResult(
                provider=self.config.provider, status="activation_required",
                reason_code="CREDENTIAL_MISSING", fetched_at=utc_now(),
                aggregate_only=decision.aggregate_only,
                authorization_id=authorization.authorization_id,
                warnings=[f"Credential environment variable {self.config.credential_env} is missing."],
            )
        if resource_path.startswith("/") or ".." in resource_path.split("/"):
            raise ValueError("resource_path must be a safe relative API path")
        url = urljoin(self.config.base_url.rstrip("/") + "/", resource_path)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "X-SATELLITE-X-Authorization": authorization.authorization_id,
            "X-SATELLITE-X-Purpose": access.purpose,
        }
        if access.case_id:
            headers["X-SATELLITE-X-Case-ID"] = access.case_id
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=self.config.timeout_seconds)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "json" not in content_type:
                raise ValueError("official connector returned non-JSON content")
            payload = response.json()
            if not isinstance(payload, (dict, list)):
                raise ValueError("official connector JSON must be an object or array")
            return GovernmentConnectorResult(
                provider=self.config.provider, status="allowed",
                reason_code="AUTHORIZED_OFFICIAL_API_RESPONSE", fetched_at=utc_now(),
                aggregate_only=decision.aggregate_only,
                authorization_id=authorization.authorization_id,
                source_url=url, record=payload,
            )
        except (requests.RequestException, ValueError) as exc:
            return GovernmentConnectorResult(
                provider=self.config.provider, status="upstream_error",
                reason_code="OFFICIAL_API_ERROR", fetched_at=utc_now(),
                aggregate_only=decision.aggregate_only,
                authorization_id=authorization.authorization_id,
                source_url=url,
                warnings=[str(exc)],
            )
