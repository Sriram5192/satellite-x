"""Minimal local identity store with hashed credentials and revocable sessions.

Production deployments can replace login with an authorized OIDC/OTP provider while retaining
field-link and session authorization semantics. Plaintext passwords and tokens are never stored.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..models import StrictModel


class AuthenticatedPrincipal(StrictModel):
    user_id: str
    role: Literal[
        "farmer", "government_officer", "investigator", "admin",
        "agronomist", "machinery_operator",
    ]
    expires_at: datetime
    owned_field_ids: list[str] = Field(default_factory=list)


class IdentityStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS identity_users (
                    user_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS identity_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES identity_users(user_id)
                );
                CREATE TABLE IF NOT EXISTS user_field_links (
                    user_id TEXT NOT NULL,
                    field_id TEXT NOT NULL,
                    confirmation_source TEXT NOT NULL,
                    confirmation_sha256 TEXT NOT NULL,
                    confirmed_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY(user_id, field_id),
                    FOREIGN KEY(user_id) REFERENCES identity_users(user_id)
                );
                CREATE TABLE IF NOT EXISTS external_identity_events (
                    verification_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    verified_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES identity_users(user_id)
                );
            """)
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(user_field_links)")
            }
            if "confirmation_sha256" not in columns:
                connection.execute(
                    "ALTER TABLE user_field_links ADD COLUMN confirmation_sha256 TEXT"
                )

    @staticmethod
    def _derive(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def register(self, user_id: str, password: str, role: str = "farmer", now: datetime | None = None) -> None:
        if len(password) < 12:
            raise ValueError("password must contain at least 12 characters")
        if role not in {
            "farmer", "government_officer", "investigator", "admin",
            "agronomist", "machinery_operator",
        }:
            raise ValueError("unsupported role")
        now = now or datetime.now(timezone.utc)
        salt = secrets.token_bytes(16)
        digest = self._derive(password, salt)
        try:
            with self.connect() as connection:
                connection.execute(
                    "INSERT INTO identity_users VALUES (?,?,?,?,1,?)",
                    (user_id, role, salt, digest, now.isoformat()),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("user_id already registered") from exc

    def login(self, user_id: str, password: str, *, ttl_hours: int = 12, now: datetime | None = None) -> str:
        now = now or datetime.now(timezone.utc)
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM identity_users WHERE user_id=?", (user_id,)).fetchone()
            if row is None or not row["active"] or not hmac.compare_digest(row["password_hash"], self._derive(password, row["password_salt"])):
                raise PermissionError("invalid credentials")
            token = secrets.token_urlsafe(32)
            connection.execute(
                "INSERT INTO identity_sessions VALUES (?,?,?,0,?)",
                (self._token_hash(token), user_id, (now + timedelta(hours=ttl_hours)).isoformat(), now.isoformat()),
            )
        return token

    def issue_verified_session(
        self,
        user_id: str,
        *,
        provider: str,
        verification_id: str,
        ttl_hours: int = 12,
        now: datetime | None = None,
    ) -> str:
        """Issue a session only after an external verifier supplies a unique proof id."""
        if provider not in {"sms_otp", "oidc", "official_sso"}:
            raise ValueError("unsupported external identity provider")
        now = now or datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        try:
            with self.connect() as connection:
                user = connection.execute(
                    "SELECT active FROM identity_users WHERE user_id=?", (user_id,)
                ).fetchone()
                if user is None or not user["active"]:
                    raise PermissionError("active user is required")
                connection.execute(
                    "INSERT INTO external_identity_events VALUES (?,?,?,?)",
                    (verification_id, user_id, provider, now.isoformat()),
                )
                connection.execute(
                    "INSERT INTO identity_sessions VALUES (?,?,?,0,?)",
                    (self._token_hash(token), user_id, (now + timedelta(hours=ttl_hours)).isoformat(), now.isoformat()),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("verification proof was already consumed") from exc
        return token

    def is_active_user(self, user_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT active FROM identity_users WHERE user_id=?", (user_id,)
            ).fetchone()
        return bool(row and row["active"])

    def link_confirmed_boundary(
        self, user_id: str, confirmation, *, now: datetime | None = None
    ) -> str:
        from ..polygon.models import BoundaryConfirmation
        confirmed = BoundaryConfirmation.model_validate(confirmation)
        source = (
            "ftw_user_confirmed"
            if confirmed.boundary_source.startswith("ftw_global_")
            else confirmed.boundary_source
        )
        payload = confirmed.model_dump(mode="json")
        confirmation_sha256 = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        now = now or datetime.now(timezone.utc)
        with self.connect() as connection:
            user = connection.execute("SELECT active FROM identity_users WHERE user_id=?", (user_id,)).fetchone()
            if user is None or not user["active"]:
                raise PermissionError("active user is required")
            connection.execute(
                """INSERT OR REPLACE INTO user_field_links
                (user_id,field_id,confirmation_source,confirmation_sha256,confirmed_at,active)
                VALUES (?,?,?,?,?,1)""",
                (user_id, confirmed.field_id, source, confirmation_sha256, now.isoformat()),
            )
        return confirmation_sha256

    def authenticate(self, token: str, *, now: datetime | None = None) -> AuthenticatedPrincipal:
        now = now or datetime.now(timezone.utc)
        with self.connect() as connection:
            row = connection.execute(
                """SELECT s.expires_at,u.user_id,u.role,u.active,s.revoked
                FROM identity_sessions s JOIN identity_users u ON u.user_id=s.user_id
                WHERE s.token_hash=?""",
                (self._token_hash(token),),
            ).fetchone()
            if row is None or row["revoked"] or not row["active"] or now >= datetime.fromisoformat(row["expires_at"]):
                raise PermissionError("session invalid or expired")
            fields = [item[0] for item in connection.execute(
                """SELECT field_id FROM user_field_links
                WHERE user_id=? AND active=1 AND confirmation_sha256 IS NOT NULL
                ORDER BY field_id""",
                (row["user_id"],),
            ).fetchall()]
        return AuthenticatedPrincipal(
            user_id=row["user_id"], role=row["role"],
            expires_at=datetime.fromisoformat(row["expires_at"]), owned_field_ids=fields,
        )

    def field_confirmation_sha256(self, user_id: str, field_id: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT confirmation_sha256 FROM user_field_links
                WHERE user_id=? AND field_id=? AND active=1""",
                (user_id, field_id),
            ).fetchone()
        return row[0] if row and row[0] else None

    def require_role(
        self, token: str, allowed_roles: set[str], *, now: datetime | None = None
    ) -> AuthenticatedPrincipal:
        principal = self.authenticate(token, now=now)
        if principal.role not in allowed_roles:
            raise PermissionError("authenticated role is not permitted")
        return principal

    def require_owned_field(self, token: str, field_id: str, *, now: datetime | None = None) -> AuthenticatedPrincipal:
        principal = self.require_role(token, {"farmer"}, now=now)
        if field_id not in principal.owned_field_ids:
            raise PermissionError("field is not linked to authenticated farmer")
        return principal

    def revoke(self, token: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE identity_sessions SET revoked=1 WHERE token_hash=?", (self._token_hash(token),))
