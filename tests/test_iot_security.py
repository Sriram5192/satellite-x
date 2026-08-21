from satellite_x.iot_security import sign_hmac_sha256, verify_hmac_sha256


def test_hmac_signature_round_trip_and_prefix():
    payload = b'{"device_id":"ESP32_01","value":7}\n'
    signature = sign_hmac_sha256(payload, "test-secret")
    assert len(signature) == 64
    assert verify_hmac_sha256(payload, signature, "test-secret")
    assert verify_hmac_sha256(payload, f"sha256={signature}", "test-secret")


def test_hmac_rejects_tampering_wrong_secret_and_malformed_signature():
    payload = b'{"value":7}'
    signature = sign_hmac_sha256(payload, "test-secret")
    assert not verify_hmac_sha256(b'{"value":8}', signature, "test-secret")
    assert not verify_hmac_sha256(payload, signature, "wrong-secret")
    assert not verify_hmac_sha256(payload, "not-a-signature", "test-secret")
