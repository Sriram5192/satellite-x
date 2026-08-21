from datetime import datetime, timezone

from satellite_x.security import ArtifactSigner


def test_ed25519_artifact_chain_is_publicly_verifiable_and_tamper_evident():
    signer = ArtifactSigner.generate()
    payload = {"field_id": "F1", "geometry_sha256": "a" * 64}
    artifact = signer.sign(
        artifact_type="boundary_confirmation", artifact_id="CONF-1",
        payload=payload, parent_sha256=["b" * 64],
        issued_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
    )
    trusted = {artifact.key_id: artifact.public_key_base64}
    assert ArtifactSigner.verify(artifact, payload, trusted_public_keys=trusted)
    assert not ArtifactSigner.verify(artifact, {**payload, "field_id": "F2"}, trusted_public_keys=trusted)
    assert not ArtifactSigner.verify(artifact, payload, trusted_public_keys={})
