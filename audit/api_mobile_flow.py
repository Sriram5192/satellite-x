"""Executed in-process HTTP flow: PWA -> OTP -> authenticated idempotent sync."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from satellite_x.api import create_app
from satellite_x.government.evidence_objects import EncryptedEvidenceObjectStore
from satellite_x.government.offline_sync import OfflineVerificationQueue
from satellite_x.government.server_sync import GroundVerificationServerStore
from satellite_x.government.verification import GroundVerification, hash_photo_bytes
from satellite_x.identity import IdentityStore
from satellite_x.integrations.otp import OtpService
from satellite_x.security import ArtifactSigner

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc)


class AuditSmsTransport:
    def send(self, phone, message):
        return "AUDIT-SMS-1"


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    identity = IdentityStore(root / "identity.db"); identity.initialize()
    identity.register("AUDIT-OFFICER", "audit password only", role="government_officer", now=NOW)
    signer = ArtifactSigner.generate()
    objects = EncryptedEvidenceObjectStore(root / "objects", encryption_key=b"e" * 32); objects.initialize()
    server = GroundVerificationServerStore(root / "server.db", signer=signer, object_store=objects, clock=lambda: NOW); server.initialize()
    otp = OtpService(root / "otp.db", transport=AuditSmsTransport(), secret=b"o" * 32, code_generator=lambda: "246810", clock=lambda: NOW); otp.initialize()
    client = TestClient(create_app(identity, server, otp=otp, mobile_directory=ROOT / "mobile"))
    challenge = client.post("/api/v1/auth/otp/request", json={"user_id": "AUDIT-OFFICER", "phone_e164": "+919876543210"})
    verified = client.post("/api/v1/auth/otp/verify", json={"challenge_id": challenge.json()["challenge_id"], "code": "246810"})
    token = verified.json()["token"]
    photo = b"\x89PNG\r\n\x1a\ndeterministic-audit-photo"
    evidence = GroundVerification(
        task_id="AUDIT-T1", field_id="AUDIT-F1", officer_id="AUDIT-OFFICER",
        captured_at=NOW, latitude=16.0644, longitude=80.6059,
        observation="confirmed", photo_sha256=hash_photo_bytes(photo), notes="deterministic API audit",
    )
    queue = OfflineVerificationQueue(
        root / "mobile.db",
        trusted_receipt_keys={signer.key_id: signer.public_key_base64},
    ); queue.initialize()
    envelope = queue.enqueue(event_id="AUDIT-EVENT-1", device_id="AUDIT-PHONE", evidence=evidence, queued_at=NOW)
    payload = {"envelopes": [envelope.model_dump(mode="json")]}
    headers = {"Authorization": f"Bearer {token}"}
    unauth = client.post("/api/v1/verification/sync", json=payload)
    missing_photo = client.post("/api/v1/verification/sync", json=payload, headers=headers)
    uploaded = client.put(
        f"/api/v1/verification/photo/{envelope.event_id}",
        data={"expected_sha256": evidence.photo_sha256},
        files={"photo": ("photo.png", photo, "image/png")},
        headers=headers,
    )
    first = client.post("/api/v1/verification/sync", json=payload, headers=headers)
    replay = client.post("/api/v1/verification/sync", json=payload, headers=headers)
    health = client.get("/api/health")
    checks = {
        "health_200": health.status_code == 200,
        "api_no_store": health.headers.get("cache-control") == "no-store",
        "frame_denied": health.headers.get("x-frame-options") == "DENY",
        "csp_present": "default-src 'self'" in health.headers.get("content-security-policy", ""),
        "pwa_200": client.get("/").status_code == 200,
        "service_worker_200": client.get("/service-worker.js").status_code == 200,
        "otp_request_200": challenge.status_code == 200,
        "otp_verify_200": verified.status_code == 200,
        "unauthenticated_sync_401": unauth.status_code == 401,
        "missing_photo_rejected": missing_photo.status_code == 409,
        "encrypted_photo_upload_200": uploaded.status_code == 200,
        "authenticated_sync_200": first.status_code == 200,
        "idempotent_same_receipt": first.json()["receipts"][0]["server_receipt"] == replay.json()["receipts"][0]["server_receipt"],
        "replay_labeled": replay.json()["receipts"][0]["reason"] == "IDEMPOTENT_REPLAY",
        "ed25519_receipt_key": first.json()["receipts"][0]["signed_artifact"]["key_id"] == signer.key_id,
    }
report = {"mode": "deterministic_test_sms_adapter_no_real_message", "checks": checks, "passed": all(checks.values())}
(ROOT / "outputs/api_mobile_flow.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
