"""Provider-backed OTP with hashed challenges, expiry, replay protection and rate limits."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import requests
from pydantic import Field

from ..identity import IdentityStore
from ..models import StrictModel

E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")


class SmsTransport(Protocol):
    def send(self, phone_e164: str, message: str) -> str: ...


class HttpSmsTransport:
    """Generic authorized JSON SMS API transport; provider credentials come only from env."""

    def __init__(self, endpoint: str, credential_env: str, sender_id: str, timeout: float = 15):
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("SMS endpoint must be HTTP(S)")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("non-local SMS endpoint must use HTTPS")
        self.endpoint = endpoint
        self.credential_env = credential_env
        self.sender_id = sender_id
        self.timeout = timeout

    def send(self, phone_e164: str, message: str) -> str:
        token = os.getenv(self.credential_env)
        if not token:
            raise RuntimeError(f"SMS credential {self.credential_env} is missing")
        response = requests.post(
            self.endpoint,
            json={"to": phone_e164, "message": message, "sender_id": self.sender_id},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message_id = payload.get("message_id") if isinstance(payload, dict) else None
        if not message_id:
            raise RuntimeError("SMS provider response has no message_id")
        return str(message_id)


class OtpChallengeReceipt(StrictModel):
    challenge_id: str
    masked_phone: str
    expires_at: datetime
    provider_message_id: str


class OtpVerification(StrictModel):
    verification_id: str
    challenge_id: str
    user_id: str
    verified_at: datetime


class OtpService:
    def __init__(
        self,
        path: str | Path,
        *,
        transport: SmsTransport,
        secret: bytes,
        code_generator=None,
        clock=None,
        ttl_minutes: int = 5,
        max_attempts: int = 5,
        hourly_requests: int = 5,
    ):
        if len(secret) < 32:
            raise ValueError("OTP secret must contain at least 32 bytes")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.transport = transport
        self.secret = secret
        self.code_generator = code_generator or (lambda: f"{secrets.randbelow(1_000_000):06d}")
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.ttl_minutes = ttl_minutes
        self.max_attempts = max_attempts
        self.hourly_requests = hourly_requests

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS otp_challenges (
                    challenge_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    phone_hash TEXT NOT NULL,
                    masked_phone TEXT NOT NULL,
                    otp_hash TEXT NOT NULL,
                    provider_message_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    consumed INTEGER NOT NULL DEFAULT 0
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS otp_user_created ON otp_challenges(user_id, created_at)")

    def _digest(self, *parts: str) -> str:
        return hmac.new(self.secret, ":".join(parts).encode(), hashlib.sha256).hexdigest()

    def request(self, user_id: str, phone_e164: str) -> OtpChallengeReceipt:
        if not E164.fullmatch(phone_e164):
            raise ValueError("phone must use E.164 format")
        now = self.clock()
        cutoff = (now - timedelta(hours=1)).isoformat()
        with self.connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM otp_challenges WHERE user_id=? AND created_at>=?",
                (user_id, cutoff),
            ).fetchone()[0]
        if count >= self.hourly_requests:
            raise PermissionError("OTP hourly request limit exceeded")
        challenge_id = secrets.token_urlsafe(18)
        code = self.code_generator()
        if not re.fullmatch(r"[0-9]{6}", code):
            raise ValueError("OTP generator must produce six digits")
        expires = now + timedelta(minutes=self.ttl_minutes)
        message_id = self.transport.send(phone_e164, f"Your SATELLITE-X verification code is {code}. It expires in {self.ttl_minutes} minutes.")
        masked = f"+{'*' * max(0, len(phone_e164) - 5)}{phone_e164[-4:]}"
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO otp_challenges
                (challenge_id,user_id,phone_hash,masked_phone,otp_hash,provider_message_id,created_at,expires_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    challenge_id, user_id, self._digest("phone", phone_e164), masked,
                    self._digest("otp", challenge_id, code), message_id,
                    now.isoformat(), expires.isoformat(),
                ),
            )
        return OtpChallengeReceipt(
            challenge_id=challenge_id, masked_phone=masked,
            expires_at=expires, provider_message_id=message_id,
        )

    def _claim(self, challenge_id: str, code: str) -> OtpVerification:
        now = self.clock()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM otp_challenges WHERE challenge_id=?", (challenge_id,)
            ).fetchone()
            if row is None:
                raise PermissionError("OTP challenge not found")
            if row["consumed"]:
                raise PermissionError("OTP challenge already consumed or in progress")
            if now >= datetime.fromisoformat(row["expires_at"]):
                raise PermissionError("OTP challenge expired")
            if row["attempts"] >= self.max_attempts:
                raise PermissionError("OTP attempt limit exceeded")
            expected = self._digest("otp", challenge_id, code)
            if not hmac.compare_digest(row["otp_hash"], expected):
                connection.execute(
                    "UPDATE otp_challenges SET attempts=attempts+1 WHERE challenge_id=?",
                    (challenge_id,),
                )
                raise PermissionError("invalid OTP")
            updated = connection.execute(
                "UPDATE otp_challenges SET consumed=2 WHERE challenge_id=? AND consumed=0",
                (challenge_id,),
            )
            if updated.rowcount != 1:
                raise PermissionError("OTP challenge already consumed or in progress")
        verification_id = "otp-" + hashlib.sha256(challenge_id.encode()).hexdigest()[:32]
        return OtpVerification(
            verification_id=verification_id,
            challenge_id=challenge_id,
            user_id=row["user_id"],
            verified_at=now,
        )

    def _finish_claim(self, challenge_id: str, *, consumed: bool) -> None:
        with self.connect() as connection:
            updated = connection.execute(
                "UPDATE otp_challenges SET consumed=? WHERE challenge_id=? AND consumed=2",
                (1 if consumed else 0, challenge_id),
            )
            if updated.rowcount != 1:
                raise RuntimeError("OTP claim state was lost")

    def verify(self, challenge_id: str, code: str) -> OtpVerification:
        verification = self._claim(challenge_id, code)
        self._finish_claim(challenge_id, consumed=True)
        return verification

    def verify_and_issue_session(
        self,
        challenge_id: str,
        code: str,
        identity: IdentityStore,
        *,
        ttl_hours: int = 12,
    ) -> str:
        verification = self._claim(challenge_id, code)
        try:
            token = identity.issue_verified_session(
                verification.user_id,
                provider="sms_otp",
                verification_id=verification.verification_id,
                ttl_hours=ttl_hours,
                now=verification.verified_at,
            )
        except Exception:
            self._finish_claim(challenge_id, consumed=False)
            raise
        self._finish_claim(challenge_id, consumed=True)
        return token
