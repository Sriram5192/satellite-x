"""Encrypted-at-rest evidence photo objects with digest and owner binding."""
from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptedEvidenceObjectStore:
    def __init__(self, root: str | Path, *, encryption_key: bytes, max_bytes: int = 10_000_000):
        if len(encryption_key) != 32:
            raise ValueError("evidence encryption key must contain exactly 32 bytes")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "evidence_objects.db"
        self.aes = AESGCM(encryption_key)
        self.max_bytes = max_bytes

    def connect(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS evidence_objects (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    photo_sha256 TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    nonce_hex TEXT NOT NULL,
                    object_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

    @staticmethod
    def _allowed_image(content: bytes, media_type: str) -> bool:
        signatures = {
            "image/jpeg": content.startswith(b"\xff\xd8\xff"),
            "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/webp": len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP",
        }
        return signatures.get(media_type, False)

    def store(
        self,
        *,
        event_id: str,
        user_id: str,
        content: bytes,
        expected_sha256: str,
        media_type: str,
    ) -> str:
        if not content or len(content) > self.max_bytes:
            raise ValueError("evidence photo size is outside allowed limits")
        if not self._allowed_image(content, media_type):
            raise ValueError("evidence photo type/signature is not allowed")
        digest = hashlib.sha256(content).hexdigest()
        if digest != expected_sha256:
            raise ValueError("evidence photo digest mismatch")
        filename = hashlib.sha256(event_id.encode()).hexdigest() + ".enc"
        target = self.root / filename
        aad = f"{event_id}:{user_id}:{digest}".encode()
        nonce = os.urandom(12)
        encrypted = self.aes.encrypt(nonce, content, aad)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT user_id,photo_sha256,object_path FROM evidence_objects WHERE event_id=?",
                (event_id,),
            ).fetchone()
            if row:
                if row["user_id"] != user_id or row["photo_sha256"] != digest:
                    raise ValueError("event photo already exists with different owner or digest")
                return row["object_path"]
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(encrypted)
            os.replace(temporary, target)
            connection.execute(
                """INSERT INTO evidence_objects
                (event_id,user_id,photo_sha256,media_type,size_bytes,nonce_hex,object_path,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    event_id, user_id, digest, media_type, len(content), nonce.hex(),
                    str(target), datetime.now(timezone.utc).isoformat(),
                ),
            )
        return str(target)

    def has(self, *, event_id: str, user_id: str, photo_sha256: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT object_path FROM evidence_objects
                WHERE event_id=? AND user_id=? AND photo_sha256=?""",
                (event_id, user_id, photo_sha256),
            ).fetchone()
        return bool(row and Path(row["object_path"]).exists())

    def decrypt_for_authorized_audit(
        self, *, event_id: str, requesting_user_id: str
    ) -> tuple[bytes, str]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM evidence_objects WHERE event_id=?", (event_id,)
            ).fetchone()
        if row is None or row["user_id"] != requesting_user_id:
            raise PermissionError("evidence object is unavailable to this principal")
        aad = f"{event_id}:{row['user_id']}:{row['photo_sha256']}".encode()
        content = self.aes.decrypt(
            bytes.fromhex(row["nonce_hex"]), Path(row["object_path"]).read_bytes(), aad
        )
        if hashlib.sha256(content).hexdigest() != row["photo_sha256"]:
            raise ValueError("decrypted evidence digest mismatch")
        return content, row["media_type"]
