"""Secure idempotent receiver with publicly verifiable Ed25519 receipts."""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..identity import AuthenticatedPrincipal
from ..security import ArtifactSigner, SignedArtifact
from .evidence_objects import EncryptedEvidenceObjectStore
from .offline_sync import OfflineEvidenceEnvelope, SyncReceipt, evidence_digest


class GroundVerificationServerStore:
    def __init__(
        self,
        path: str | Path,
        *,
        signer: ArtifactSigner,
        object_store: EncryptedEvidenceObjectStore,
        clock=None,
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.signer = signer
        self.object_store = object_store
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS ground_verification_events (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    server_receipt TEXT NOT NULL,
                    signed_receipt_json TEXT
                )
            """)
            columns = {
                row[1] for row in connection.execute(
                    "PRAGMA table_info(ground_verification_events)"
                )
            }
            if "signed_receipt_json" not in columns:
                connection.execute(
                    "ALTER TABLE ground_verification_events ADD COLUMN signed_receipt_json TEXT"
                )

    def _signed_receipt(
        self,
        *,
        event_id: str,
        payload_sha256: str,
        user_id: str,
        received_at: datetime,
    ) -> tuple[str, SignedArtifact]:
        payload = {
            "event_id": event_id,
            "payload_sha256": payload_sha256,
            "user_id": user_id,
            "received_at": received_at.isoformat().replace("+00:00", "Z"),
            "accepted": True,
        }
        signed = self.signer.sign(
            artifact_type="ground_verification_receipt",
            artifact_id=event_id,
            payload=payload,
            parent_sha256=[payload_sha256],
            issued_at=received_at,
        )
        receipt_id = "ed25519:" + signed.key_id + ":" + hashlib.sha256(
            signed.signature_base64.encode()
        ).hexdigest()[:32]
        return receipt_id, signed

    @staticmethod
    def receipt_payload(receipt: SyncReceipt, user_id: str, payload_sha256: str) -> dict:
        return {
            "event_id": receipt.event_id,
            "payload_sha256": payload_sha256,
            "user_id": user_id,
            "received_at": receipt.received_at.isoformat().replace("+00:00", "Z"),
            "accepted": receipt.accepted,
        }

    def receive(
        self,
        envelope: OfflineEvidenceEnvelope,
        principal: AuthenticatedPrincipal,
    ) -> SyncReceipt:
        now = self.clock()
        if principal.role not in {"government_officer", "investigator"}:
            raise PermissionError("ground-verification sync requires an authorized officer")
        if envelope.evidence.officer_id != principal.user_id:
            raise PermissionError("evidence officer_id does not match authenticated user")
        if not self.object_store.has(
            event_id=envelope.event_id,
            user_id=principal.user_id,
            photo_sha256=envelope.evidence.photo_sha256,
        ):
            raise ValueError("encrypted evidence photo must be uploaded before synchronization")
        if envelope.sync_status != "pending" or envelope.server_receipt is not None:
            raise ValueError("server accepts pending unsynchronized envelopes only")
        calculated = evidence_digest(envelope.evidence)
        if not hmac.compare_digest(calculated, envelope.payload_sha256):
            raise ValueError("ground-verification payload hash mismatch")
        with self.connect() as connection:
            row = connection.execute(
                """SELECT payload_sha256,server_receipt,received_at,signed_receipt_json
                FROM ground_verification_events WHERE event_id=?""",
                (envelope.event_id,),
            ).fetchone()
            if row:
                if not hmac.compare_digest(row["payload_sha256"], envelope.payload_sha256):
                    raise ValueError("event_id collision with different evidence")
                if not row["signed_receipt_json"]:
                    raise ValueError("legacy unsigned receipt cannot be replayed as verified")
                return SyncReceipt(
                    event_id=envelope.event_id,
                    accepted=True,
                    server_receipt=row["server_receipt"],
                    received_at=datetime.fromisoformat(row["received_at"]),
                    signed_artifact=SignedArtifact.model_validate_json(
                        row["signed_receipt_json"]
                    ),
                    reason="IDEMPOTENT_REPLAY",
                )
            receipt, signed = self._signed_receipt(
                event_id=envelope.event_id,
                payload_sha256=envelope.payload_sha256,
                user_id=principal.user_id,
                received_at=now,
            )
            connection.execute(
                """INSERT INTO ground_verification_events
                (event_id,user_id,device_id,payload_sha256,evidence_json,received_at,
                 server_receipt,signed_receipt_json)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    envelope.event_id, principal.user_id, envelope.device_id,
                    envelope.payload_sha256, envelope.evidence.model_dump_json(),
                    now.isoformat(), receipt, signed.model_dump_json(),
                ),
            )
        return SyncReceipt(
            event_id=envelope.event_id,
            accepted=True,
            server_receipt=receipt,
            received_at=now,
            signed_artifact=signed,
        )
