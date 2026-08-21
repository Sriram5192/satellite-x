"""Sentinel-2 L2A discovery with AWS primary and CDSE fallback."""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from ..config import Settings
from ..errors import ExternalServiceError, NoSatelliteSceneError
from ..http import JsonHttpClient
from ..models import (
    AcquisitionAttempt,
    BandAsset,
    FarmInput,
    SatelliteAcquisition,
    SatelliteScene,
)

_REQUIRED = ("B02", "B03", "B04", "B05", "B08", "B11", "SCL")

_PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "aws_earth_search": {
        "collection": "sentinel-2-l2a",
        "assets": {
            "B02": ("blue", 10),
            "B03": ("green", 10),
            "B04": ("red", 10),
            "B05": ("rededge1", 20),
            "B08": ("nir", 10),
            "B11": ("swir16", 20),
            "SCL": ("scl", 20),
        },
    },
    "copernicus_cdse": {
        "collection": "sentinel-2-l2a",
        "assets": {
            "B02": ("B02_10m", 10),
            "B03": ("B03_10m", 10),
            "B04": ("B04_10m", 10),
            "B05": ("B05_20m", 20),
            "B08": ("B08_10m", 10),
            "B11": ("B11_20m", 20),
            "SCL": ("SCL_20m", 20),
        },
    },
}


def field_bbox(field: FarmInput) -> list[float]:
    """Return a WGS84 bbox from a supplied polygon or an acreage-based square."""
    if field.boundary_geojson:
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

        collect(field.boundary_geojson["coordinates"])
        if not points:
            raise ValueError("boundary_geojson contains no coordinate pairs")
        longitudes, latitudes = zip(*points)
        return [min(longitudes), min(latitudes), max(longitudes), max(latitudes)]

    area_m2 = field.acres * 4046.8564224
    half_side_m = math.sqrt(area_m2) / 2
    lat_delta = half_side_m / 111_320.0
    lon_scale = max(111_320.0 * math.cos(math.radians(field.latitude)), 1.0)
    lon_delta = half_side_m / lon_scale
    return [
        field.longitude - lon_delta,
        field.latitude - lat_delta,
        field.longitude + lon_delta,
        field.latitude + lat_delta,
    ]


class SatelliteClient:
    def __init__(self, http: JsonHttpClient, settings: Settings):
        self.http = http
        self.settings = settings

    def acquire(self, field: FarmInput) -> SatelliteAcquisition:
        attempts: list[AcquisitionAttempt] = []
        original_start = field.analysis_date - timedelta(days=field.scan_range_days - 1)
        end = field.analysis_date
        expanded_start = original_start - timedelta(days=self.settings.expand_days)

        scene, aws_failed = self._attempt(
            "aws_earth_search", original_start, end, field, attempts
        )
        if scene:
            return SatelliteAcquisition(
                scene=scene,
                attempts=attempts,
                expanded_date_range=False,
                fallback_used=False,
            )

        expanded = False
        if not aws_failed:
            expanded = True
            scene, _ = self._attempt(
                "aws_earth_search", expanded_start, end, field, attempts
            )
            if scene:
                return SatelliteAcquisition(
                    scene=scene,
                    attempts=attempts,
                    expanded_date_range=True,
                    fallback_used=False,
                )

        cdse_start = expanded_start if expanded else original_start
        scene, cdse_failed = self._attempt(
            "copernicus_cdse", cdse_start, end, field, attempts
        )
        if scene:
            return SatelliteAcquisition(
                scene=scene,
                attempts=attempts,
                expanded_date_range=expanded,
                fallback_used=True,
            )

        if not expanded and not cdse_failed:
            expanded = True
            scene, _ = self._attempt(
                "copernicus_cdse", expanded_start, end, field, attempts
            )
            if scene:
                return SatelliteAcquisition(
                    scene=scene,
                    attempts=attempts,
                    expanded_date_range=True,
                    fallback_used=True,
                )

        details = "; ".join(
            f"{item.source}:{item.outcome}:{item.detail}" for item in attempts
        )
        raise NoSatelliteSceneError(
            f"No complete Sentinel-2 L2A scene found for {field.field_id}. {details}"
        )

    def _attempt(
        self,
        provider: str,
        start: date,
        end: date,
        field: FarmInput,
        attempts: list[AcquisitionAttempt],
    ) -> tuple[SatelliteScene | None, bool]:
        try:
            scene = self.search(provider, start, end, field)
        except ExternalServiceError as exc:
            attempts.append(
                AcquisitionAttempt(
                    source=provider,
                    date_start=start,
                    date_end=end,
                    outcome="error",
                    detail=exc.message,
                )
            )
            return None, True
        if scene is None:
            attempts.append(
                AcquisitionAttempt(
                    source=provider,
                    date_start=start,
                    date_end=end,
                    outcome="empty",
                    detail="no scene below cloud threshold with all 7 required assets",
                )
            )
            return None, False
        attempts.append(
            AcquisitionAttempt(
                source=provider,
                date_start=start,
                date_end=end,
                outcome="success",
                detail=f"selected {scene.scene_id} at {scene.cloud_cover_pct:.2f}% cloud",
            )
        )
        return scene, False

    def search(
        self, provider: str, start: date, end: date, field: FarmInput
    ) -> SatelliteScene | None:
        config = _PROVIDER_CONFIG[provider]
        base_url = (
            self.settings.aws_stac_url
            if provider == "aws_earth_search"
            else self.settings.cdse_stac_url
        )
        start_dt = datetime.combine(start, time.min, timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        end_dt = datetime.combine(end, time.max, timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        payload = {
            "collections": [config["collection"]],
            "bbox": field_bbox(field),
            "datetime": f"{start_dt}/{end_dt}",
            "limit": 20,
            "query": {"eo:cloud_cover": {"lt": self.settings.max_cloud_pct}},
        }
        response = self.http.post_json(provider, f"{base_url}/search", payload=payload)
        features = response.get("features")
        if not isinstance(features, list):
            raise ExternalServiceError(provider, "STAC response has no features array")

        candidates: list[SatelliteScene] = []
        for feature in features:
            try:
                scene = self._parse_scene(provider, feature, payload["bbox"])
            except (KeyError, TypeError, ValueError):
                continue
            if scene.cloud_cover_pct < self.settings.max_cloud_pct:
                candidates.append(scene)
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda item: (item.cloud_cover_pct, -item.acquired_at.timestamp()),
        )

    @staticmethod
    def _parse_scene(
        provider: str, feature: dict[str, Any], query_bbox: list[float]
    ) -> SatelliteScene:
        config = _PROVIDER_CONFIG[provider]
        raw_assets = feature["assets"]
        if not isinstance(raw_assets, dict):
            raise TypeError("assets must be an object")
        assets: dict[str, BandAsset] = {}
        for band_code in _REQUIRED:
            source_key, resolution = config["assets"][band_code]
            raw = raw_assets[source_key]
            href = raw["href"]
            raster_bands = raw.get("raster:bands") or []
            raster_metadata = raster_bands[0] if raster_bands else {}
            assets[band_code] = BandAsset(
                band_code=band_code,
                source_key=source_key,
                href=href,
                resolution_m=resolution,
                media_type=raw.get("type"),
                scale=(
                    float(raster_metadata["scale"])
                    if raster_metadata.get("scale") is not None
                    else None
                ),
                offset=(
                    float(raster_metadata["offset"])
                    if raster_metadata.get("offset") is not None
                    else None
                ),
                nodata=(
                    float(raster_metadata["nodata"])
                    if raster_metadata.get("nodata") is not None
                    else None
                ),
                requires_authentication=(
                    provider == "copernicus_cdse" and not str(href).startswith("https://")
                ),
            )
        properties = feature["properties"]
        timestamp_text = properties["datetime"]
        acquired_at = datetime.fromisoformat(str(timestamp_text).replace("Z", "+00:00"))
        if acquired_at.tzinfo is None:
            acquired_at = acquired_at.replace(tzinfo=timezone.utc)
        cloud = float(properties.get("eo:cloud_cover", 100.0))
        bbox = feature.get("bbox", query_bbox)
        return SatelliteScene(
            scene_id=str(feature["id"]),
            provider=provider,
            collection=config["collection"],
            acquired_at=acquired_at,
            cloud_cover_pct=cloud,
            bbox=[float(value) for value in bbox],
            assets=assets,
        )
