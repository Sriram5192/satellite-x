"""Authenticity helpers for raw ESP32 HTTP/MQTT payload bytes."""

from __future__ import annotations

import hashlib
import hmac
import re

_SIGNATURE = re.compile(r"^[0-9a-fA-F]{64}$")


def sign_hmac_sha256(payload_bytes: bytes, secret: str) -> str:
    if not secret:
        raise ValueError("IoT HMAC secret cannot be empty")
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def verify_hmac_sha256(payload_bytes: bytes, signature: str, secret: str) -> bool:
    normalized = signature.removeprefix("sha256=").strip()
    if not _SIGNATURE.fullmatch(normalized):
        return False
    expected = sign_hmac_sha256(payload_bytes, secret)
    return hmac.compare_digest(expected, normalized.lower())
