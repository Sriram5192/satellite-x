"""FastAPI transport for authenticated offline evidence synchronization."""
from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import Field

from ..government.evidence_objects import EncryptedEvidenceObjectStore
from ..government.offline_sync import OfflineEvidenceEnvelope, SyncReceipt
from ..government.server_sync import GroundVerificationServerStore
from ..identity import AuthenticatedPrincipal, IdentityStore
from ..integrations.otp import HttpSmsTransport, OtpChallengeReceipt, OtpService
from ..models import StrictModel
from ..security import ArtifactSigner
from .rate_limit import SqliteRateLimiter


class SyncBatch(StrictModel):
    envelopes: list[OfflineEvidenceEnvelope] = Field(min_length=1, max_length=100)


class SyncBatchResult(StrictModel):
    receipts: list[SyncReceipt]


class OtpRequest(StrictModel):
    user_id: str
    phone_e164: str


class OtpVerify(StrictModel):
    challenge_id: str
    code: str = Field(pattern=r"^[0-9]{6}$")


class SessionToken(StrictModel):
    token: str
    token_type: str = "Bearer"


class ReceiptVerificationKey(StrictModel):
    algorithm: str = "Ed25519"
    key_id: str
    public_key_base64: str


def create_app(
    identity: IdentityStore,
    sync_store: GroundVerificationServerStore,
    *,
    otp: OtpService | None = None,
    rate_limiter: SqliteRateLimiter | None = None,
    mobile_directory: str | Path | None = None,
    max_json_bytes: int = 2_000_000,
    max_photo_bytes: int = 10_000_000,
) -> FastAPI:
    app = FastAPI(title="SATELLITE-X Sync API", version="1.0.0", docs_url="/api/docs")
    bearer = HTTPBearer(auto_error=False)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        content_length = request.headers.get("content-length")
        parsed_length = None
        if content_length is not None:
            try:
                parsed_length = int(content_length)
            except ValueError:
                parsed_length = -1
        protected_write = (
            request.url.path.startswith("/api/")
            and request.method in {"POST", "PUT", "PATCH"}
        )
        if protected_write and parsed_length == -1:
            response = JSONResponse(status_code=400, content={"detail": "invalid content-length"})
        elif protected_write and parsed_length is not None and parsed_length > (
            max_photo_bytes + 100_000
            if request.url.path.startswith("/api/v1/verification/photo/")
            else max_json_bytes
        ):
            response = JSONResponse(status_code=413, content={"detail": "request body is too large"})
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(self), camera=(self), microphone=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' blob: data:; connect-src 'self'; worker-src 'self'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def enforce_rate(bucket: str, key: str, *, limit: int, window_seconds: int) -> None:
        if rate_limiter is not None and not rate_limiter.consume(
            bucket, key, limit=limit, window_seconds=window_seconds
        ):
            raise HTTPException(status_code=429, detail="rate limit exceeded")

    def client_key(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def principal(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> AuthenticatedPrincipal:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Bearer session required")
        try:
            return identity.authenticate(credentials.credentials)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "satellite-x-sync"}

    @app.get("/api/v1/security/receipt-key", response_model=ReceiptVerificationKey)
    def receipt_key():
        return ReceiptVerificationKey(
            key_id=sync_store.signer.key_id,
            public_key_base64=sync_store.signer.public_key_base64,
        )

    @app.post("/api/v1/auth/otp/request", response_model=OtpChallengeReceipt)
    def request_otp(body: OtpRequest, request: Request):
        if otp is None:
            raise HTTPException(status_code=503, detail="OTP provider is not configured")
        enforce_rate("otp-request-ip", client_key(request), limit=20, window_seconds=3600)
        enforce_rate("otp-request-user", body.user_id, limit=5, window_seconds=3600)
        if not identity.is_active_user(body.user_id):
            raise HTTPException(status_code=400, detail="OTP request cannot be completed")
        try:
            return otp.request(body.user_id, body.phone_e164)
        except (ValueError, PermissionError, RuntimeError) as exc:
            raise HTTPException(status_code=429 if isinstance(exc, PermissionError) else 400, detail=str(exc)) from exc

    @app.post("/api/v1/auth/otp/verify", response_model=SessionToken)
    def verify_otp(body: OtpVerify, request: Request):
        if otp is None:
            raise HTTPException(status_code=503, detail="OTP provider is not configured")
        enforce_rate("otp-verify-ip", client_key(request), limit=30, window_seconds=3600)
        enforce_rate("otp-verify-challenge", body.challenge_id, limit=6, window_seconds=600)
        try:
            token = otp.verify_and_issue_session(body.challenge_id, body.code, identity)
            return SessionToken(token=token)
        except (ValueError, PermissionError) as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @app.get("/api/v1/me", response_model=AuthenticatedPrincipal)
    def me(user: AuthenticatedPrincipal = Depends(principal)):
        return user

    @app.put("/api/v1/verification/photo/{event_id}")
    async def upload_evidence_photo(
        event_id: str,
        request: Request,
        expected_sha256: str = Form(pattern=r"^[0-9a-f]{64}$"),
        photo: UploadFile = File(),
        user: AuthenticatedPrincipal = Depends(principal),
    ):
        if user.role not in {"government_officer", "investigator"}:
            raise HTTPException(status_code=403, detail="officer role is required")
        enforce_rate("verification-photo-user", user.user_id, limit=30, window_seconds=60)
        enforce_rate("verification-photo-ip", client_key(request), limit=60, window_seconds=60)
        content = await photo.read(max_photo_bytes + 1)
        if len(content) > max_photo_bytes:
            raise HTTPException(status_code=413, detail="evidence photo is too large")
        try:
            sync_store.object_store.store(
                event_id=event_id,
                user_id=user.user_id,
                content=content,
                expected_sha256=expected_sha256,
                media_type=photo.content_type or "application/octet-stream",
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"status": "encrypted", "event_id": event_id, "photo_sha256": expected_sha256}

    @app.post("/api/v1/verification/sync", response_model=SyncBatchResult)
    def sync(
        batch: SyncBatch,
        request: Request,
        user: AuthenticatedPrincipal = Depends(principal),
    ):
        enforce_rate("verification-sync-user", user.user_id, limit=60, window_seconds=60)
        enforce_rate("verification-sync-ip", client_key(request), limit=120, window_seconds=60)
        receipts = []
        for envelope in batch.envelopes:
            try:
                receipts.append(sync_store.receive(envelope, user))
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        return SyncBatchResult(receipts=receipts)

    if mobile_directory is not None:
        directory = Path(mobile_directory)
        if not (directory / "index.html").exists():
            raise ValueError("mobile_directory must contain index.html")
        app.mount("/", StaticFiles(directory=directory, html=True), name="mobile")
    return app


def build_app_from_env() -> FastAPI:
    data = Path(os.getenv("SATELLITE_X_API_DATA", "data/api"))
    private_key = os.getenv("SATELLITE_X_RECEIPT_ED25519_PRIVATE_KEY_BASE64", "")
    if not private_key:
        raise RuntimeError("SATELLITE_X_RECEIPT_ED25519_PRIVATE_KEY_BASE64 is required")
    signer = ArtifactSigner.from_private_key_base64(private_key)
    try:
        evidence_key = base64.b64decode(
            os.getenv("SATELLITE_X_EVIDENCE_AES256_KEY_BASE64", ""), validate=True
        )
    except Exception as exc:
        raise RuntimeError("SATELLITE_X_EVIDENCE_AES256_KEY_BASE64 is invalid") from exc
    if len(evidence_key) != 32:
        raise RuntimeError("SATELLITE_X_EVIDENCE_AES256_KEY_BASE64 must decode to 32 bytes")
    identity = IdentityStore(data / "identity.db")
    identity.initialize()
    object_store = EncryptedEvidenceObjectStore(
        data / "evidence_objects", encryption_key=evidence_key
    )
    object_store.initialize()
    sync_store = GroundVerificationServerStore(
        data / "verification.db", signer=signer, object_store=object_store
    )
    sync_store.initialize()
    rate_limiter = SqliteRateLimiter(
        data / "rate_limits.db",
        secret=hashlib.sha256(private_key.encode() + b":rate-limit").digest(),
    )
    rate_limiter.initialize()
    otp = None
    sms_endpoint = os.getenv("SATELLITE_X_SMS_ENDPOINT")
    if sms_endpoint:
        otp_secret = os.getenv("SATELLITE_X_OTP_SECRET", "").encode()
        if len(otp_secret) < 32:
            raise RuntimeError("SATELLITE_X_OTP_SECRET must contain at least 32 characters")
        transport = HttpSmsTransport(
            sms_endpoint,
            os.getenv("SATELLITE_X_SMS_CREDENTIAL_ENV", "SATELLITE_X_SMS_TOKEN"),
            os.getenv("SATELLITE_X_SMS_SENDER_ID", "SATELLITEX"),
        )
        otp = OtpService(data / "otp.db", transport=transport, secret=otp_secret)
        otp.initialize()
    mobile = Path(os.getenv("SATELLITE_X_MOBILE_DIR", "mobile"))
    return create_app(
        identity, sync_store, otp=otp, rate_limiter=rate_limiter,
        mobile_directory=mobile,
    )
