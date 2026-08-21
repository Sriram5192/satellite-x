"""SQLite-backed fixed-window limiter shared by API workers."""
from __future__ import annotations

import hashlib
import hmac
import sqlite3
import time
from pathlib import Path


class SqliteRateLimiter:
    def __init__(self, path: str | Path, *, secret: bytes, clock=None):
        if len(secret) < 32:
            raise ValueError("rate-limit secret must contain at least 32 bytes")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.secret = secret
        self.clock = clock or time.time

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS rate_limit_windows (
                    bucket TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    window_start INTEGER NOT NULL,
                    count INTEGER NOT NULL,
                    PRIMARY KEY(bucket,key_hash,window_start)
                );
                CREATE INDEX IF NOT EXISTS rate_limit_window_idx
                ON rate_limit_windows(window_start);
            """)

    def _key_hash(self, value: str) -> str:
        return hmac.new(self.secret, value.encode(), hashlib.sha256).hexdigest()

    def consume(self, bucket: str, key: str, *, limit: int, window_seconds: int) -> bool:
        if limit < 1 or window_seconds < 1:
            raise ValueError("rate limit and window must be positive")
        now = int(self.clock())
        window_start = now - (now % window_seconds)
        key_hash = self._key_hash(key)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT count FROM rate_limit_windows
                WHERE bucket=? AND key_hash=? AND window_start=?""",
                (bucket, key_hash, window_start),
            ).fetchone()
            if row and row[0] >= limit:
                return False
            connection.execute(
                """INSERT INTO rate_limit_windows(bucket,key_hash,window_start,count)
                VALUES (?,?,?,1)
                ON CONFLICT(bucket,key_hash,window_start)
                DO UPDATE SET count=count+1""",
                (bucket, key_hash, window_start),
            )
            connection.execute(
                "DELETE FROM rate_limit_windows WHERE window_start < ?",
                (window_start - 86400,),
            )
        return True
