"""Ed25519 signatures for immutable SATELLITE-X artifact chains."""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import Field

from ..models import StrictModel, utc_now


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class SignedArtifact(StrictModel):
    artifact_type: str
    artifact_id: str
    issued_at: datetime
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_sha256: list[str] = Field(default_factory=list)
    key_id: str
    public_key_base64: str
    signature_base64: str

    def signing_payload(self) -> dict[str, Any]:
        return self.model_dump(
            mode="json", exclude={"signature_base64", "public_key_base64"}
        )


class ArtifactSigner:
    def __init__(self, private_key: Ed25519PrivateKey):
        self.private_key = private_key
        self.public_key = private_key.public_key()
        public_raw = self.public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.public_key_base64 = base64.b64encode(public_raw).decode()
        self.key_id = hashlib.sha256(public_raw).hexdigest()[:16]

    @classmethod
    def generate(cls) -> "ArtifactSigner":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_private_key_base64(cls, value: str) -> "ArtifactSigner":
        try:
            raw = base64.b64decode(value, validate=True)
            return cls(Ed25519PrivateKey.from_private_bytes(raw))
        except Exception as exc:
            raise ValueError("invalid Ed25519 private key") from exc

    def private_key_base64(self) -> str:
        raw = self.private_key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        return base64.b64encode(raw).decode()

    def sign(
        self,
        *,
        artifact_type: str,
        artifact_id: str,
        payload: dict[str, Any] | list[Any],
        parent_sha256: list[str] | None = None,
        issued_at: datetime | None = None,
    ) -> SignedArtifact:
        digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        unsigned = SignedArtifact(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            issued_at=issued_at or utc_now(),
            payload_sha256=digest,
            parent_sha256=parent_sha256 or [],
            key_id=self.key_id,
            public_key_base64=self.public_key_base64,
            signature_base64=base64.b64encode(b"0" * 64).decode(),
        )
        signature = self.private_key.sign(canonical_json_bytes(unsigned.signing_payload()))
        return unsigned.model_copy(update={"signature_base64": base64.b64encode(signature).decode()})

    @staticmethod
    def verify(
        signed: SignedArtifact,
        payload: dict[str, Any] | list[Any],
        *,
        trusted_public_keys: dict[str, str] | None = None,
    ) -> bool:
        digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        if digest != signed.payload_sha256:
            return False
        if trusted_public_keys is not None:
            trusted = trusted_public_keys.get(signed.key_id)
            if trusted is None or trusted != signed.public_key_base64:
                return False
        try:
            public_raw = base64.b64decode(signed.public_key_base64, validate=True)
            signature = base64.b64decode(signed.signature_base64, validate=True)
            Ed25519PublicKey.from_public_bytes(public_raw).verify(
                signature, canonical_json_bytes(signed.signing_payload())
            )
            return True
        except (ValueError, InvalidSignature):
            return False
