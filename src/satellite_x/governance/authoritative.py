"""Authoritative signed authorization/case registry and fail-closed policy gateway."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from ..models import StrictModel
from ..security import ArtifactSigner, SignedArtifact
from .models import AccessDecision, AccessRequest, GovernmentAuthorization, UserContext
from .policy import PolicyGateway


class CaseRecord(StrictModel):
    case_id: str = Field(min_length=3, max_length=128)
    investigator_id: str
    authorization_id: str
    purpose: str = Field(min_length=5, max_length=500)
    field_ids: list[str] = Field(min_length=1)
    status: Literal["active", "closed", "revoked", "expired"]
    valid_from: datetime
    valid_until: datetime
    created_by: str

    @model_validator(mode="after")
    def valid_period(self) -> "CaseRecord":
        if self.valid_until <= self.valid_from:
            raise ValueError("case valid_until must be after valid_from")
        return self


class AuthoritativeGovernanceStore:
    def __init__(self, path: str | Path, *, trusted_public_keys: dict[str, str]):
        if not trusted_public_keys:
            raise ValueError("at least one trusted issuer key is required")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.trusted_public_keys = trusted_public_keys

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS signed_authorizations (
                    authorization_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    signed_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    stored_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS signed_cases (
                    case_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    signed_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    stored_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def _verify(self, signed: SignedArtifact, payload: dict, expected_type: str, expected_id: str) -> None:
        if signed.artifact_type != expected_type or signed.artifact_id != expected_id:
            raise ValueError("signed artifact type/id mismatch")
        if not ArtifactSigner.verify(
            signed, payload, trusted_public_keys=self.trusted_public_keys
        ):
            raise ValueError("artifact signature or payload digest is invalid")

    def save_authorization(
        self, authorization: GovernmentAuthorization, signed: SignedArtifact
    ) -> None:
        payload = authorization.model_dump(mode="json")
        self._verify(signed, payload, "government_authorization", authorization.authorization_id)
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO signed_authorizations
                (authorization_id,payload_json,signed_json,payload_sha256)
                VALUES (?,?,?,?)""",
                (authorization.authorization_id, json.dumps(payload), signed.model_dump_json(), signed.payload_sha256),
            )

    def save_case(self, case: CaseRecord, signed: SignedArtifact) -> None:
        payload = case.model_dump(mode="json")
        self._verify(signed, payload, "investigation_case", case.case_id)
        if self.get_authorization(case.authorization_id) is None:
            raise ValueError("case references no authoritative authorization")
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO signed_cases
                (case_id,payload_json,signed_json,payload_sha256) VALUES (?,?,?,?)""",
                (case.case_id, json.dumps(payload), signed.model_dump_json(), signed.payload_sha256),
            )

    def get_authorization(self, authorization_id: str) -> GovernmentAuthorization | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json,signed_json FROM signed_authorizations WHERE authorization_id=?",
                (authorization_id,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        signed = SignedArtifact.model_validate_json(row["signed_json"])
        self._verify(signed, payload, "government_authorization", authorization_id)
        return GovernmentAuthorization.model_validate(payload)

    def get_case(self, case_id: str) -> CaseRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json,signed_json FROM signed_cases WHERE case_id=?", (case_id,)
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        signed = SignedArtifact.model_validate_json(row["signed_json"])
        self._verify(signed, payload, "investigation_case", case_id)
        return CaseRecord.model_validate(payload)


class AuthoritativePolicyGateway:
    def __init__(self, store: AuthoritativeGovernanceStore):
        self.store = store
        self.base = PolicyGateway()

    def decide(
        self,
        user: UserContext,
        request: AccessRequest,
        *,
        authorization_id: str,
        now: datetime | None = None,
    ) -> AccessDecision:
        now = now or datetime.now(timezone.utc)
        authorization = self.store.get_authorization(authorization_id)
        if authorization is None:
            return AccessDecision(
                allowed=False, reason_code="AUTHORITATIVE_AUTHORIZATION_NOT_FOUND",
                audit_required=True, aggregate_only=True,
            )
        decision = self.base.decide(user, request, authorization, now)
        if not decision.allowed:
            return decision
        if request.action in {"VIEW_PARCEL_DETAILS", "EXPORT_CASE_EVIDENCE"}:
            case = self.store.get_case(request.case_id or "")
            valid = (
                case is not None
                and case.status == "active"
                and case.investigator_id == user.user_id
                and case.authorization_id == authorization_id
                and request.field_id in case.field_ids
                and case.valid_from <= now <= case.valid_until
                and request.purpose == case.purpose
            )
            if not valid:
                return AccessDecision(
                    allowed=False, reason_code="AUTHORITATIVE_CASE_DENIED",
                    audit_required=True, aggregate_only=True,
                )
        return decision
