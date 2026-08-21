"""Fail-closed TLE provenance check for a selected Sentinel scene."""
from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Literal

from pydantic import Field

from ..models import StrictModel
from ..preprocessing.models import PreprocessingResult
from .models import TleRecord

SENTINEL_NORAD = {"S2A": 40697, "S2B": 42063, "S2C": 60989}


class SceneOrbitProvenance(StrictModel):
    scene_id: str
    spacecraft_code: str | None
    expected_norad_id: int | None
    tle_norad_id: int
    scene_time_utc: datetime
    tle_epoch: datetime
    absolute_epoch_gap_hours: float
    status: Literal[
        "validated_epoch_near_scene",
        "historical_tle_required",
        "spacecraft_or_norad_mismatch",
    ]
    usable_for_pass_validation: bool
    warnings: list[str] = Field(default_factory=list)


def validate_scene_orbit(
    preprocessing: PreprocessingResult,
    tle: TleRecord,
    *,
    maximum_epoch_gap_hours: float = 168,
) -> SceneOrbitProvenance:
    scene = preprocessing.selected_scene
    if scene is None:
        raise ValueError("selected scene is required")
    code = scene.scene_id.split("_")[0]
    expected = SENTINEL_NORAD.get(code)
    scene_time = scene.acquired_at.astimezone(timezone.utc)
    gap = abs((scene_time - tle.epoch).total_seconds()) / 3600
    if expected is None or expected != tle.norad_id:
        status = "spacecraft_or_norad_mismatch"
        usable = False
        warnings = ["Scene spacecraft code and TLE NORAD ID do not match."]
    elif gap > maximum_epoch_gap_hours:
        status = "historical_tle_required"
        usable = False
        warnings = [
            "Latest TLE is too far from the historical scene; obtain an authorized historical TLE instead of back-propagating it."
        ]
    else:
        status = "validated_epoch_near_scene"
        usable = True
        warnings = [
            "TLE confirms orbital geometry only; it does not validate image radiometry or live beacon performance."
        ]
    return SceneOrbitProvenance(
        scene_id=scene.scene_id,
        spacecraft_code=code,
        expected_norad_id=expected,
        tle_norad_id=tle.norad_id,
        scene_time_utc=scene_time,
        tle_epoch=tle.epoch,
        absolute_epoch_gap_hours=round(gap, 6),
        status=status,
        usable_for_pass_validation=usable,
        warnings=warnings,
    )
