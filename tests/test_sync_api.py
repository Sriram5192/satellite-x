from datetime import datetime, timezone

from fastapi.testclient import TestClient

from satellite_x.api import create_app
from satellite_x.api.rate_limit import SqliteRateLimiter
from satellite_x.government.evidence_objects import EncryptedEvidenceObjectStore
from satellite_x.government.offline_sync import OfflineVerificationQueue
from satellite_x.government.server_sync import GroundVerificationServerStore
from satellite_x.government.verification import GroundVerification, hash_photo_bytes
from satellite_x.identity import IdentityStore
from satellite_x.integrations.otp import OtpService
from satellite_x.security import ArtifactSigner


class Sms:
    def send(self, phone, message):
        return "SMS-1"


def test_authenticated_sync_api_and_idempotent_receipt(tmp_path):
    now = datetime.now(timezone.utc)
    identity = IdentityStore(tmp_path / "identity.db")
    identity.initialize()
    identity.register("OFFICER-1", "correct horse field", role="government_officer", now=now)
    token = identity.login("OFFICER-1", "correct horse field", now=now)
    signer = ArtifactSigner.generate()
    objects = EncryptedEvidenceObjectStore(tmp_path / "objects", encryption_key=b"e" * 32)
    objects.initialize()
    server = GroundVerificationServerStore(
        tmp_path / "server.db", signer=signer, object_store=objects, clock=lambda: now
    )
    server.initialize()
    otp = OtpService(tmp_path / "otp.db", transport=Sms(), secret=b"o" * 32, code_generator=lambda: "123456", clock=lambda: now)
    otp.initialize()
    limiter = SqliteRateLimiter(tmp_path / "limits.db", secret=b"l" * 32, clock=lambda: now.timestamp())
    limiter.initialize()
    client = TestClient(create_app(
        identity, server, otp=otp, rate_limiter=limiter,
        mobile_directory="mobile", max_json_bytes=100_000,
    ))

    queue = OfflineVerificationQueue(
        tmp_path / "mobile.db",
        trusted_receipt_keys={signer.key_id: signer.public_key_base64},
    )
    queue.initialize()
    photo = b"\x89PNG\r\n\x1a\napi-validation-photo"
    evidence = GroundVerification(
        task_id="T1", field_id="F1", officer_id="OFFICER-1", captured_at=now,
        latitude=16.2, longitude=80.3, observation="confirmed",
        photo_sha256=hash_photo_bytes(photo), notes="field checked",
    )
    envelope = queue.enqueue(event_id="EVENT-0001", device_id="PHONE-1", evidence=evidence, queued_at=now)
    payload = {"envelopes": [envelope.model_dump(mode="json")]}
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.headers["cache-control"] == "no-store"
    assert health.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in health.headers["content-security-policy"]
    key_response = client.get("/api/v1/security/receipt-key")
    assert key_response.status_code == 200
    assert key_response.json()["key_id"] == signer.key_id
    assert "SATELLITE-X Field Verification" in client.get("/").text
    service_worker = client.get("/service-worker.js")
    assert service_worker.status_code == 200
    assert 'url.pathname.startsWith("/api/")' in service_worker.text
    challenge = client.post("/api/v1/auth/otp/request", json={"user_id": "OFFICER-1", "phone_e164": "+919876543210"})
    assert challenge.status_code == 200
    verified = client.post("/api/v1/auth/otp/verify", json={"challenge_id": challenge.json()["challenge_id"], "code": "123456"})
    assert verified.status_code == 200
    token = verified.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/v1/verification/sync", json=payload).status_code == 401
    assert client.post("/api/v1/verification/sync", json=payload, headers=headers).status_code == 409
    uploaded = client.put(
        f"/api/v1/verification/photo/{envelope.event_id}",
        data={"expected_sha256": evidence.photo_sha256},
        files={"photo": ("photo.png", photo, "image/png")},
        headers=headers,
    )
    assert uploaded.status_code == 200
    first = client.post("/api/v1/verification/sync", json=payload, headers=headers)
    replay = client.post("/api/v1/verification/sync", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert first.status_code == 200 and replay.status_code == 200
    assert first.json()["receipts"][0]["server_receipt"] == replay.json()["receipts"][0]["server_receipt"]
    assert replay.json()["receipts"][0]["reason"] == "IDEMPOTENT_REPLAY"
    assert first.json()["receipts"][0]["signed_artifact"]["key_id"] == signer.key_id
    oversized = client.post(
        "/api/v1/auth/otp/request",
        content=b"x" * 100_001,
        headers={"content-type": "application/json"},
    )
    assert oversized.status_code == 413


def test_sqlite_rate_limiter_is_shared_and_atomic(tmp_path):
    limiter = SqliteRateLimiter(tmp_path / "limits.db", secret=b"l" * 32, clock=lambda: 1000)
    limiter.initialize()
    assert limiter.consume("bucket", "user", limit=2, window_seconds=60)
    assert limiter.consume("bucket", "user", limit=2, window_seconds=60)
    assert not limiter.consume("bucket", "user", limit=2, window_seconds=60)
    second_worker = SqliteRateLimiter(tmp_path / "limits.db", secret=b"l" * 32, clock=lambda: 1000)
    assert not second_worker.consume("bucket", "user", limit=2, window_seconds=60)
