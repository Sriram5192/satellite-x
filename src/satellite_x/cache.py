"""Small deterministic JSON cache used only for traceable live-response fallback."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import CacheMissError


class JsonCache:
    def __init__(self, root: Path):
        self.root = root

    @staticmethod
    def make_key(namespace: str, parameters: dict[str, Any]) -> str:
        canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"{namespace}-{digest}"

    def _path(self, key: str) -> Path:
        safe = "".join(char for char in key if char.isalnum() or char in "-_")
        return self.root / f"{safe}.json"

    def put(self, key: str, payload: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(key)
        temporary = path.with_suffix(".tmp")
        envelope = {
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        temporary.write_text(
            json.dumps(envelope, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        os.replace(temporary, path)

    def get(self, key: str) -> dict[str, Any]:
        path = self._path(key)
        if not path.exists():
            raise CacheMissError(f"cache key not found: {key}")
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            payload = envelope["payload"]
            if not isinstance(payload, dict):
                raise TypeError("payload is not an object")
            return payload
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CacheMissError(f"invalid cache entry {key}: {exc}") from exc
