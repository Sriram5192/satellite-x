"""Idempotent offline queue for ground-verification evidence.

The queue is transport-neutral: a deployed mobile client can export pending envelopes and
apply signed backend receipts without silently claiming that network delivery occurred.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..models import StrictModel, utc_now
from ..security import ArtifactSigner, SignedArtifact
from .verification import GroundVerification


class OfflineEvidenceEnvelope(StrictModel):
    event_id: str = Field(min_length=8)
    device_id: str = Field(min_length=3)
    queued_at: datetime
    evidence: GroundVerification
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sync_status: Literal["pending", "synced", "rejected"] = "pending"
    server_receipt: str | None = None


class SyncReceipt(StrictModel):
    event_id: str
    accepted: bool
    server_receipt: str
    received_at: datetime
    signed_artifact: SignedArtifact | None = None
    reason: str | None = None


def canonical_evidence_payload(evidence: GroundVerification) -> dict[str, str]:
    """Cross-language canonical form used by Python and the offline PWA."""
    captured = evidence.captured_at.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return {
        "captured_at": captured,
        "field_id": evidence.field_id,
        "latitude": f"{evidence.latitude:.7f}",
        "longitude": f"{evidence.longitude:.7f}",
        "notes": evidence.notes,
        "observation": evidence.observation,
        "officer_id": evidence.officer_id,
        "photo_sha256": evidence.photo_sha256,
        "task_id": evidence.task_id,
    }


def evidence_digest(evidence: GroundVerification) -> str:
    canonical = json.dumps(
        canonical_evidence_payload(evidence), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class OfflineVerificationQueue:
    def __init__(
        self, path: str | Path, *, trusted_receipt_keys: dict[str, str]
    ):
        if not trusted_receipt_keys:
            raise ValueError("trusted receipt verification keys are required")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.trusted_receipt_keys = trusted_receipt_keys

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS offline_verification_queue (
                    event_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    queued_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    sync_status TEXT NOT NULL CHECK(sync_status IN ('pending','synced','rejected')),
                    server_receipt TEXT,
                    synced_at TEXT
                )
            """)

    def enqueue(
        self,
        *,
        event_id: str,
        device_id: str,
        evidence: GroundVerification,
        queued_at: datetime | None = None,
    ) -> OfflineEvidenceEnvelope:
        envelope = OfflineEvidenceEnvelope(
            event_id=event_id,
            device_id=device_id,
            queued_at=queued_at or utc_now(),
            evidence=evidence,
            payload_sha256=evidence_digest(evidence),
        )
        payload = evidence.model_dump_json()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT payload_sha256 FROM offline_verification_queue WHERE event_id=?",
                (event_id,),
            ).fetchone()
            if existing:
                if existing["payload_sha256"] != envelope.payload_sha256:
                    raise ValueError("event_id already exists with different evidence")
                return self.get(event_id)
            connection.execute(
                """INSERT INTO offline_verification_queue
                (event_id,device_id,queued_at,payload_json,payload_sha256,sync_status)
                VALUES (?,?,?,?,?,'pending')""",
                (event_id, device_id, envelope.queued_at.isoformat(), payload, envelope.payload_sha256),
            )
        return envelope

    def get(self, event_id: str) -> OfflineEvidenceEnvelope:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM offline_verification_queue WHERE event_id=?", (event_id,)
            ).fetchone()
        if row is None:
            raise KeyError(event_id)
        return OfflineEvidenceEnvelope(
            event_id=row["event_id"], device_id=row["device_id"],
            queued_at=datetime.fromisoformat(row["queued_at"]),
            evidence=GroundVerification.model_validate_json(row["payload_json"]),
            payload_sha256=row["payload_sha256"], sync_status=row["sync_status"],
            server_receipt=row["server_receipt"],
        )

    def pending(self, limit: int = 100) -> list[OfflineEvidenceEnvelope]:
        with self.connect() as connection:
            ids = [row[0] for row in connection.execute(
                "SELECT event_id FROM offline_verification_queue WHERE sync_status='pending' ORDER BY queued_at LIMIT ?",
                (limit,),
            ).fetchall()]
        return [self.get(event_id) for event_id in ids]

    def acknowledge(self, receipt: SyncReceipt) -> OfflineEvidenceEnvelope:
        envelope = self.get(receipt.event_id)
        signed = receipt.signed_artifact
        payload = {
            "event_id": receipt.event_id,
            "payload_sha256": envelope.payload_sha256,
            "user_id": envelope.evidence.officer_id,
            "received_at": receipt.received_at.isoformat().replace("+00:00", "Z"),
            "accepted": receipt.accepted,
        }
        if (
            signed is None
            or signed.artifact_type != "ground_verification_receipt"
            or signed.artifact_id != receipt.event_id
            or not ArtifactSigner.verify(
                signed, payload, trusted_public_keys=self.trusted_receipt_keys
            )
        ):
            raise ValueError("receipt signature is invalid or untrusted")
        status = "synced" if receipt.accepted else "rejected"
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE offline_verification_queue
                SET sync_status=?, server_receipt=?, synced_at=?
                WHERE event_id=? AND sync_status='pending'""",
                (status, receipt.server_receipt, receipt.received_at.isoformat(), receipt.event_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("receipt must match one pending event")
        return self.get(receipt.event_id)
