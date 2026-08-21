"""Sentinel-2 candidate listing for field-level quality selection."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

from ..acquisition.satellite import SatelliteClient
from ..config import Settings
from ..errors import ExternalServiceError
from ..http import JsonHttpClient
from ..models import SatelliteScene
from .errors import SceneCatalogError
from .models import PreprocessingInput


def geometry_bbox(geometry: dict[str, Any]) -> list[float]:
    points: list[tuple[float, float]] = []

    def collect(node: Any) -> None:
        if (
            isinstance(node, (list, tuple))
            and len(node) >= 2
            and isinstance(node[0], (int, float))
            and isinstance(node[1], (int, float))
        ):
            points.append((float(node[0]), float(node[1])))
        elif isinstance(node, (list, tuple)):
            for child in node:
                collect(child)

    collect(geometry["coordinates"])
    if not points:
        raise SceneCatalogError("boundary contains no coordinate pairs")
    longitudes, latitudes = zip(*points)
    return [min(longitudes), min(latitudes), max(longitudes), max(latitudes)]


class SentinelCandidateCatalog:
    def __init__(self, http: JsonHttpClient, settings: Settings):
        self.http = http
        self.settings = settings

    def list_scenes(
        self, request: PreprocessingInput, start: date, end: date
    ) -> list[SatelliteScene]:
        start_text = datetime.combine(start, time.min, timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        end_text = datetime.combine(end, time.max, timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        bbox = geometry_bbox(request.boundary_geojson)
        payload = {
            "collections": ["sentinel-2-l2a"],
            "bbox": bbox,
            "datetime": f"{start_text}/{end_text}",
            "limit": 100,
        }
        try:
            response = self.http.post_json(
                "aws_earth_search",
                f"{self.settings.aws_stac_url}/search",
                payload=payload,
            )
        except ExternalServiceError as exc:
            raise SceneCatalogError(str(exc)) from exc
        features = response.get("features")
        if not isinstance(features, list):
            raise SceneCatalogError("STAC response has no features array")

        scenes: list[SatelliteScene] = []
        for feature in features:
            try:
                scenes.append(
                    SatelliteClient._parse_scene("aws_earth_search", feature, bbox)
                )
            except (KeyError, TypeError, ValueError):
                continue
        scenes.sort(key=lambda scene: scene.acquired_at)
        return scenes
