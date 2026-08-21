import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from satellite_x.governance.models import AccessRequest, GovernmentAuthorization, UserContext
from satellite_x.integrations.government import GovernmentConnectorConfig, GovernmentRecordGateway
from satellite_x.integrations.otp import HttpSmsTransport


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def _send(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        assert self.headers["Authorization"] == "Bearer sms-secret"
        self._send({"message_id": "LOCAL-SMS-1"})
    def do_GET(self):
        assert self.headers["Authorization"] == "Bearer gov-secret"
        assert self.headers["X-SATELLITE-X-Authorization"] == "AUTH-1"
        self._send({"official_record": "LOCAL-ADAPTER-TEST"})


def test_real_local_http_transports_enforce_bearer_and_authorization(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        monkeypatch.setenv("SMS_TOKEN", "sms-secret")
        sms = HttpSmsTransport(f"{base}/sms", "SMS_TOKEN", "SATELLITEX")
        assert sms.send("+919876543210", "authorized test") == "LOCAL-SMS-1"

        monkeypatch.setenv("GOV_TOKEN", "gov-secret")
        authorization = GovernmentAuthorization(
            authorization_id="AUTH-1", officer_id="O1", department="Agriculture", designation="MAO",
            permission_status="approved", permissions=["VIEW_VILLAGE_SUMMARY"], village_codes=["V1"],
            order_reference="ORDER-1", valid_from=NOW-timedelta(days=1), valid_until=NOW+timedelta(days=1), approved_by="D1",
        )
        result = GovernmentRecordGateway(
            GovernmentConnectorConfig(
                provider="authorized_custom", base_url=base,
                credential_env="GOV_TOKEN", enabled=True,
            ),
            allow_unsigned_test_authorization=True,
        ).fetch(
            user=UserContext(user_id="O1", role="government_officer", consent_active=True),
            access=AccessRequest(action="VIEW_VILLAGE_SUMMARY", village_code="V1", purpose="authorized local adapter test"),
            authorization=authorization, resource_path="official", now=NOW,
        )
        assert result.status == "allowed"
        assert result.record == {"official_record": "LOCAL-ADAPTER-TEST"}
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
