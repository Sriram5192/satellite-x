from datetime import datetime, timezone

import pytest

from satellite_x.government.offline_sync import OfflineVerificationQueue, SyncReceipt
from satellite_x.government.verification import GroundVerification, hash_photo_bytes
from satellite_x.security import ArtifactSigner


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


def evidence(note="checked"):
    return GroundVerification(
        task_id="T1", field_id="F1", officer_id="O1", captured_at=NOW,
        latitude=16.2, longitude=80.3, observation="confirmed",
        photo_sha256=hash_photo_bytes(b"real-photo-bytes"), notes=note,
    )


def test_offline_queue_is_idempotent_tamper_evident_and_receipt_driven(tmp_path):
    signer = ArtifactSigner.generate()
    queue = OfflineVerificationQueue(
        tmp_path / "offline.db",
        trusted_receipt_keys={signer.key_id: signer.public_key_base64},
    )
    queue.initialize()
    first = queue.enqueue(event_id="EVENT-0001", device_id="PHONE-1", evidence=evidence(), queued_at=NOW)
    duplicate = queue.enqueue(event_id="EVENT-0001", device_id="PHONE-1", evidence=evidence(), queued_at=NOW)
    assert first.payload_sha256 == duplicate.payload_sha256
    assert len(queue.pending()) == 1
    with pytest.raises(ValueError, match="different evidence"):
        queue.enqueue(event_id="EVENT-0001", device_id="PHONE-1", evidence=evidence("changed"), queued_at=NOW)
    receipt_payload = {
        "event_id": "EVENT-0001", "payload_sha256": first.payload_sha256,
        "user_id": first.evidence.officer_id,
        "received_at": NOW.isoformat().replace("+00:00", "Z"), "accepted": True,
    }
    signed = signer.sign(
        artifact_type="ground_verification_receipt", artifact_id="EVENT-0001",
        payload=receipt_payload, parent_sha256=[first.payload_sha256], issued_at=NOW,
    )
    synced = queue.acknowledge(SyncReceipt(
        event_id="EVENT-0001", accepted=True, server_receipt="SERVER-ACK-1",
        received_at=NOW, signed_artifact=signed,
    ))
    assert synced.sync_status == "synced"
    assert synced.server_receipt == "SERVER-ACK-1"
    assert queue.pending() == []
