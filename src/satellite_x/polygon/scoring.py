"""Transparent scoring of FTW candidates against GPS and reported acreage."""

from __future__ import annotations

import hashlib
import json

from ..config import Settings
from .ftw import RawFtwRecord
from .geometry import normalize_and_validate
from .models import BoundaryCandidate, PolygonRecoveryInput


def score_candidates(
    records: list[RawFtwRecord],
    request: PolygonRecoveryInput,
    settings: Settings,
) -> list[BoundaryCandidate]:
    candidates: list[BoundaryCandidate] = []
    for record in records:
        normalized, validation = normalize_and_validate(record.geometry_geojson, request)
        if not validation.valid:
            continue
        if (
            validation.area_difference_pct
            > settings.max_candidate_area_difference_pct
        ):
            continue

        containment = (
            1.0
            if validation.contains_input_point
            else max(
                0.0,
                1.0 - validation.point_distance_m / request.gps_tolerance_m,
            )
        )
        area_similarity = max(
            0.0,
            1.0
            - validation.area_difference_pct
            / settings.max_candidate_area_difference_pct,
        )
        recency = 1.0 if record.year == 2025 else 0.8
        score = 100.0 * (
            0.50 * containment + 0.35 * area_similarity + 0.15 * recency
        )
        quality = (
            "HIGH"
            if score >= settings.polygon_high_score_pct
            else "MEDIUM"
            if score >= settings.polygon_medium_score_pct
            else "LOW"
        )
        geometry_digest = hashlib.sha256(
            json.dumps(
                normalized, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()[:10]
        candidate_id = (
            f"ftw-{request.country_code}-{request.subdivision_code}-"
            f"{record.record_id}-{record.year}-{geometry_digest}"
        )
        candidates.append(
            BoundaryCandidate(
                candidate_id=candidate_id,
                source=f"ftw_global_{record.year}",
                year=record.year,
                geometry_geojson=normalized,
                area_m2=validation.area_m2,
                area_acres=validation.area_acres,
                perimeter_m=validation.perimeter_m,
                source_confidence=record.confidence,
                contains_input_point=validation.contains_input_point,
                point_distance_m=validation.point_distance_m,
                area_difference_pct=validation.area_difference_pct,
                score_pct=round(score, 3),
                score_components={
                    "point_containment_pct": round(containment * 100, 3),
                    "acreage_similarity_pct": round(area_similarity * 100, 3),
                    "recency_pct": round(recency * 100, 3),
                },
                quality=quality,
                legal_boundary=False,
            )
        )
    candidates.sort(
        key=lambda item: (
            -item.score_pct,
            -item.year,
            item.area_difference_pct,
            item.candidate_id,
        )
    )
    return candidates[: settings.polygon_max_candidates]
