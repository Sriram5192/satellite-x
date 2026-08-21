import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from satellite_x.identity import IdentityStore
from satellite_x.integrations.otp import OtpService


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


class Transport:
    def __init__(self): self.messages = []
    def send(self, phone, message):
        self.messages.append((phone, message))
        return "SMS-1"


def test_provider_backed_otp_is_hashed_single_use_and_issues_session(tmp_path):
    transport = Transport()
    service = OtpService(
        tmp_path / "otp.db", transport=transport, secret=b"x" * 32,
        code_generator=lambda: "123456", clock=lambda: NOW,
    )
    service.initialize()
    identity = IdentityStore(tmp_path / "identity.db")
    identity.initialize()
    identity.register("farmer-1", "correct horse field", now=NOW)
    confirmation = json.loads(Path("outputs/polygon_crop_field_confirmed.json").read_text())
    identity.link_confirmed_boundary("farmer-1", confirmation, now=NOW)
    field_id = confirmation["field_id"]
    receipt = service.request("farmer-1", "+919876543210")
    assert receipt.masked_phone.endswith("3210")
    assert transport.messages and "123456" in transport.messages[0][1]
    with pytest.raises(PermissionError, match="invalid OTP"):
        service.verify(receipt.challenge_id, "000000")
    token = service.verify_and_issue_session(receipt.challenge_id, "123456", identity)
    assert identity.require_owned_field(token, field_id, now=NOW).user_id == "farmer-1"
    with pytest.raises(PermissionError, match="already consumed"):
        service.verify(receipt.challenge_id, "123456")


def test_otp_claim_rolls_back_if_session_creation_fails(tmp_path):
    service = OtpService(
        tmp_path / "otp.db", transport=Transport(), secret=b"x" * 32,
        code_generator=lambda: "123456", clock=lambda: NOW,
    )
    service.initialize()
    identity = IdentityStore(tmp_path / "identity.db"); identity.initialize()
    receipt = service.request("future-user", "+919876543210")
    with pytest.raises(PermissionError, match="active user"):
        service.verify_and_issue_session(receipt.challenge_id, "123456", identity)
    identity.register("future-user", "correct horse field", now=NOW)
    token = service.verify_and_issue_session(receipt.challenge_id, "123456", identity)
    assert identity.authenticate(token, now=NOW).user_id == "future-user"


def test_otp_expiry_and_rate_limit(tmp_path):
    now = [NOW]
    service = OtpService(
        tmp_path / "otp.db", transport=Transport(), secret=b"x" * 32,
        code_generator=lambda: "123456", clock=lambda: now[0], hourly_requests=1,
    )
    service.initialize()
    receipt = service.request("U1", "+919876543210")
    with pytest.raises(PermissionError, match="hourly"):
        service.request("U1", "+919876543210")
    now[0] += timedelta(minutes=6)
    with pytest.raises(PermissionError, match="expired"):
        service.verify(receipt.challenge_id, "123456")
