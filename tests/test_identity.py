import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from satellite_x.identity import IdentityStore


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


def test_authenticated_farmer_is_limited_to_linked_confirmed_fields(tmp_path):
    store = IdentityStore(tmp_path / "identity.db")
    store.initialize()
    store.register("farmer-1", "correct horse field", now=NOW)
    confirmation = json.loads(Path("outputs/polygon_crop_field_confirmed.json").read_text())
    digest = store.link_confirmed_boundary("farmer-1", confirmation, now=NOW)
    field_id = confirmation["field_id"]
    token = store.login("farmer-1", "correct horse field", now=NOW)
    principal = store.require_owned_field(token, field_id, now=NOW)
    assert principal.user_id == "farmer-1" and principal.owned_field_ids == [field_id]
    assert store.field_confirmation_sha256("farmer-1", field_id) == digest
    with pytest.raises(PermissionError, match="not linked"):
        store.require_owned_field(token, "F2", now=NOW)
    with pytest.raises(PermissionError, match="invalid credentials"):
        store.login("farmer-1", "wrong password!", now=NOW)
    store.revoke(token)
    with pytest.raises(PermissionError, match="invalid or expired"):
        store.authenticate(token, now=NOW)


def test_expired_session_is_rejected(tmp_path):
    store = IdentityStore(tmp_path / "identity.db")
    store.initialize()
    store.register("farmer-1", "correct horse field", now=NOW)
    token = store.login("farmer-1", "correct horse field", ttl_hours=1, now=NOW)
    with pytest.raises(PermissionError, match="invalid or expired"):
        store.authenticate(token, now=NOW + timedelta(hours=2))
