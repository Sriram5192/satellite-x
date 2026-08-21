from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Literal

from pydantic import Field

from ..models import StrictModel


class GroundVerification(StrictModel):
    task_id: str
    field_id: str
    officer_id: str
    captured_at: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    observation: Literal["confirmed", "not_confirmed", "inconclusive"]
    photo_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    notes: str


def hash_photo_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
