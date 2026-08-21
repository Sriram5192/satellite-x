"""Frozen crop-stage calendars and DAS interpretation."""

from __future__ import annotations

from dataclasses import dataclass

from .models import PhenologyState


@dataclass(frozen=True, slots=True)
class Stage:
    start: int
    end: int
    name: str
    low: float
    high: float
    criticality: str


CALENDARS = {
    "cotton": [
        Stage(0, 20, "Germination", 0.12, 0.25, "LOW"),
        Stage(20, 50, "Vegetative", 0.25, 0.50, "MEDIUM"),
        Stage(50, 75, "Squaring", 0.50, 0.70, "HIGH"),
        Stage(75, 115, "Flowering", 0.65, 0.85, "CRITICAL"),
        Stage(115, 150, "Boll Development", 0.55, 0.80, "HIGH"),
        Stage(150, 190, "Maturity", 0.25, 0.55, "LOW"),
    ],
    "chilli": [
        Stage(0, 20, "Transplant", 0.10, 0.22, "MEDIUM"),
        Stage(20, 50, "Vegetative", 0.22, 0.45, "MEDIUM"),
        Stage(50, 85, "Flowering", 0.45, 0.70, "CRITICAL"),
        Stage(85, 130, "Fruiting", 0.55, 0.78, "CRITICAL"),
        Stage(130, 180, "Harvest / Pickings", 0.35, 0.65, "MEDIUM"),
    ],
    "paddy": [
        Stage(0, 20, "Nursery / Transplant", 0.10, 0.30, "MEDIUM"),
        Stage(20, 45, "Tillering", 0.30, 0.60, "HIGH"),
        Stage(45, 70, "Panicle Initiation", 0.60, 0.80, "CRITICAL"),
        Stage(70, 95, "Heading / Flowering", 0.70, 0.88, "CRITICAL"),
        Stage(95, 115, "Grain Filling", 0.60, 0.80, "HIGH"),
        Stage(115, 145, "Maturity", 0.25, 0.55, "LOW"),
    ],
}


def phenology_state(crop: str, das: int, ndvi_mean: float) -> PhenologyState:
    stages = CALENDARS[crop]
    stage = next((item for item in stages if item.start <= das < item.end), None)
    if stage is None:
        if das < 0:
            raise ValueError("scene date is before sowing date")
        last = stages[-1]
        stage = Stage(last.end, max(last.end + 60, das + 1), "Post-season", 0.0, last.low, "LOW")
    position = (
        "BELOW_EXPECTED"
        if ndvi_mean < stage.low
        else "ABOVE_EXPECTED"
        if ndvi_mean > stage.high
        else "WITHIN_EXPECTED"
    )
    return PhenologyState(
        crop_type=crop, das=das, stage_name=stage.name,
        stage_start_das=stage.start, stage_end_das=stage.end,
        expected_ndvi_low=stage.low, expected_ndvi_high=stage.high,
        criticality=stage.criticality, ndvi_position=position,
    )
