"""Cross-language PWA/Python evidence digest and static asset validation."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from satellite_x.government.offline_sync import evidence_digest
from satellite_x.government.verification import GroundVerification
from satellite_x.security import ArtifactSigner

ROOT = Path(__file__).resolve().parents[1]
evidence = GroundVerification(
    task_id="TASK-1", field_id="FIELD-1", officer_id="OFFICER-1",
    captured_at=datetime(2026, 8, 17, 12, 34, 56, 123000, tzinfo=timezone.utc),
    latitude=16.0644448134, longitude=80.6059204281,
    observation="confirmed", photo_sha256="a" * 64, notes="cross-language check",
)
python_digest = evidence_digest(evidence)
js = r'''
const crypto=require("crypto");
const e={task_id:"TASK-1",field_id:"FIELD-1",officer_id:"OFFICER-1",captured_at:"2026-08-17T12:34:56.123Z",latitude:16.0644448134,longitude:80.6059204281,observation:"confirmed",photo_sha256:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",notes:"cross-language check"};
function stable(v){if(Array.isArray(v))return `[${v.map(stable).join(",")}]`;if(v&&typeof v==="object")return `{${Object.keys(v).sort().map(k=>`${JSON.stringify(k)}:${stable(v[k])}`).join(",")}}`;return JSON.stringify(v)}
const c={captured_at:new Date(e.captured_at).toISOString(),field_id:e.field_id,latitude:Number(e.latitude).toFixed(7),longitude:Number(e.longitude).toFixed(7),notes:e.notes,observation:e.observation,officer_id:e.officer_id,photo_sha256:e.photo_sha256,task_id:e.task_id};
process.stdout.write(crypto.createHash("sha256").update(stable(c)).digest("hex"));
'''
node_digest = subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout
signer = ArtifactSigner.generate()
receipt_payload = {
    "accepted": True, "event_id": "EVENT-1", "payload_sha256": "b" * 64,
    "received_at": "2026-08-18T12:00:00Z", "user_id": "OFFICER-1",
}
signed = signer.sign(
    artifact_type="ground_verification_receipt", artifact_id="EVENT-1",
    payload=receipt_payload, parent_sha256=["b" * 64],
    issued_at=datetime(2026, 8, 18, 12, tzinfo=timezone.utc),
)
verify_js = f'''
const crypto=require("crypto").webcrypto; const a={json.dumps(signed.model_dump(mode="json"))}; const payload={json.dumps(receipt_payload)};
function stable(v){{if(Array.isArray(v))return `[${{v.map(stable).join(",")}}]`;if(v&&typeof v==="object")return `{{${{Object.keys(v).sort().map(k=>`${{JSON.stringify(k)}}:${{stable(v[k])}}`).join(",")}}}}`;return JSON.stringify(v)}}
function b64(v){{return Uint8Array.from(Buffer.from(v,"base64"))}}
(async()=>{{const digest=Buffer.from(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(stable(payload)))).toString("hex");if(digest!==a.payload_sha256)process.exit(2);const signing={{artifact_id:a.artifact_id,artifact_type:a.artifact_type,issued_at:a.issued_at,key_id:a.key_id,parent_sha256:a.parent_sha256,payload_sha256:a.payload_sha256}};const key=await crypto.subtle.importKey("raw",b64(a.public_key_base64),{{name:"Ed25519"}},false,["verify"]);const ok=await crypto.subtle.verify({{name:"Ed25519"}},key,b64(a.signature_base64),new TextEncoder().encode(stable(signing)));process.stdout.write(ok?"true":"false")}})();
'''
js_receipt_verified = subprocess.run(
    ["node", "-e", verify_js], check=True, capture_output=True, text=True
).stdout == "true"
checks = {
    "python_js_digest_equal": python_digest == node_digest,
    "ed25519_receipt_js_verify": js_receipt_verified,
    "app_js_syntax": subprocess.run(["node", "--check", str(ROOT / "mobile/app.js")], capture_output=True).returncode == 0,
    "service_worker_syntax": subprocess.run(["node", "--check", str(ROOT / "mobile/service-worker.js")], capture_output=True).returncode == 0,
    "queue_uses_no_inner_html": ".innerHTML" not in (ROOT / "mobile/app.js").read_text(),
    "service_worker_bypasses_api": 'url.pathname.startsWith("/api/")' in (ROOT / "mobile/service-worker.js").read_text(),
    "offline_index_present": (ROOT / "mobile/index.html").exists(),
    "manifest_present": (ROOT / "mobile/manifest.webmanifest").exists(),
}
report = {"python_digest": python_digest, "javascript_digest": node_digest, "checks": checks, "passed": all(checks.values())}
(ROOT / "outputs/mobile_sync_reality.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
