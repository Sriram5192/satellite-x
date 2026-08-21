from datetime import datetime, timezone

import pytest

from satellite_x.government.evidence_objects import EncryptedEvidenceObjectStore
from satellite_x.government.offline_sync import OfflineVerificationQueue
from satellite_x.government.server_sync import GroundVerificationServerStore
from satellite_x.government.verification import GroundVerification, hash_photo_bytes
from satellite_x.identity import IdentityStore
from satellite_x.security import ArtifactSigner


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


def test_secure_server_sync_is_authenticated_tamper_evident_and_idempotent(tmp_path):
    identity = IdentityStore(tmp_path / "identity.db")
    identity.initialize()
    identity.register("OFFICER-1", "correct horse field", role="government_officer", now=NOW)
    token = identity.login("OFFICER-1", "correct horse field", now=NOW)
    principal = identity.authenticate(token, now=NOW)

    photo = b"\x89PNG\r\n\x1a\nvalidation-photo"
    evidence = GroundVerification(
        task_id="T1", field_id="F1", officer_id="OFFICER-1", captured_at=NOW,
        latitude=16.2, longitude=80.3, observation="confirmed",
        photo_sha256=hash_photo_bytes(photo), notes="verified in field",
    )
    signer = ArtifactSigner.generate()
    queue = OfflineVerificationQueue(
        tmp_path / "mobile.db",
        trusted_receipt_keys={signer.key_id: signer.public_key_base64},
    )
    queue.initialize()
    envelope = queue.enqueue(event_id="EVENT-0001", device_id="PHONE-1", evidence=evidence, queued_at=NOW)
    objects = EncryptedEvidenceObjectStore(tmp_path / "objects", encryption_key=b"e" * 32)
    objects.initialize()
    objects.store(
        event_id=envelope.event_id, user_id=principal.user_id, content=photo,
        expected_sha256=evidence.photo_sha256, media_type="image/png",
    )
    server = GroundVerificationServerStore(
        tmp_path / "server.db", signer=signer, object_store=objects, clock=lambda: NOW
    )
    server.initialize()
    receipt = server.receive(envelope, principal)
    replay = server.receive(envelope, principal)
    assert receipt.server_receipt == replay.server_receipt
    assert replay.reason == "IDEMPOTENT_REPLAY"
    assert receipt.signed_artifact is not None
    payload = server.receipt_payload(receipt, principal.user_id, envelope.payload_sha256)
    assert ArtifactSigner.verify(
        receipt.signed_artifact, payload,
        trusted_public_keys={signer.key_id: signer.public_key_base64},
    )
    assert queue.acknowledge(receipt).sync_status == "synced"
    decrypted, media_type = objects.decrypt_for_authorized_audit(
        event_id=envelope.event_id, requesting_user_id=principal.user_id
    )
    assert decrypted == photo and media_type == "image/png"

    tampered = envelope.model_copy(update={"payload_sha256": "0" * 64})
    with pytest.raises(ValueError, match="hash mismatch"):
        server.receive(tampered, principal)
