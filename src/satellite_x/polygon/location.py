"""Consent-bound reverse-location preflight with explicit distance-based blocking."""

from __future__ import annotations

from typing import Any

from ..cache import JsonCache
from ..config import Settings
from ..errors import CacheMissError, ExternalServiceError
from ..http import JsonHttpClient
from .errors import LocationPreflightError
from .math_utils import haversine_m
from .models import LocationEvidence, PolygonRecoveryInput


class LocationPreflightClient:
    def __init__(self, http: JsonHttpClient, cache: JsonCache, settings: Settings):
        self.http = http
        self.cache = cache
        self.settings = settings

    def check(self, request: PolygonRecoveryInput) -> LocationEvidence:
        parameters = {
            "format": "jsonv2",
            "lat": round(request.latitude, 7),
            "lon": round(request.longitude, 7),
            "zoom": 18,
            "addressdetails": 1,
        }
        cache_key = self.cache.make_key("nominatim-reverse", parameters)
        source = "nominatim_live"
        try:
            payload = self.http.get_json(
                "nominatim", self.settings.nominatim_url, params=parameters
            )
            self.cache.put(cache_key, {"response": payload})
        except ExternalServiceError as live_error:
            try:
                payload = self.cache.get(cache_key)["response"]
                source = "cache"
            except (CacheMissError, KeyError, TypeError) as cache_error:
                raise LocationPreflightError(
                    f"reverse-location live request failed ({live_error}); "
                    f"cache unavailable ({cache_error})"
                ) from live_error

        try:
            matched_lat = float(payload["lat"])
            matched_lon = float(payload["lon"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LocationPreflightError(
                "reverse-location response has no valid matched coordinate"
            ) from exc

        distance = haversine_m(
            request.latitude, request.longitude, matched_lat, matched_lon
        )
        category = self._text(payload.get("category"))
        feature_type = self._text(payload.get("type"))
        address = payload.get("address") if isinstance(payload.get("address"), dict) else {}
        iso_code = self._text(address.get("ISO3166-2-lvl4"))
        country_code = self._text(address.get("country_code"))
        if country_code:
            country_code = country_code.upper()
        subdivision_code = None
        if iso_code and "-" in iso_code:
            subdivision_code = iso_code.split("-", 1)[1].upper()

        blocking, reason = self._classify(category, feature_type, distance)
        return LocationEvidence(
            source=source,
            category=category,
            feature_type=feature_type,
            name=self._text(payload.get("name")),
            display_name=self._text(payload.get("display_name")),
            matched_latitude=matched_lat,
            matched_longitude=matched_lon,
            feature_distance_m=round(distance, 3),
            country_code=country_code,
            subdivision_code=subdivision_code,
            blocking=blocking,
            reason_code=reason,
            raw_osm_type=self._text(payload.get("osm_type")),
            raw_osm_id=(
                int(payload["osm_id"]) if payload.get("osm_id") is not None else None
            ),
        )
    def _classify(
        self, category: str | None, feature_type: str | None, distance_m: float
    ) -> tuple[bool, str]:
        # Farm access tracks/paths are expected to be near cropland by design
        # (fields need an access route) — only block on real public roads.
        non_blocking_highway_types = {
            "track", "path", "footway", "service", "bridleway", "cycleway",
        }
        if (
            category == "highway"
            and feature_type not in non_blocking_highway_types
            and distance_m <= self.settings.road_reject_distance_m
        ):
            return True, "POINT_ON_OR_NEXT_TO_ROAD"
        if category in {"building", "shop", "office", "amenity"} and (
            distance_m <= self.settings.structure_reject_distance_m
        ):
            return True, "POINT_ON_OR_NEXT_TO_STRUCTURE"
              # Irrigation canals/drains/ditches are expected to run alongside
        # cropland by design (fields need irrigation access) — only block
        # on natural water bodies (rivers, streams), not irrigation infra.
        irrigation_waterway_types = {"canal", "drain", "ditch"}
        if (
            category == "waterway"
            and feature_type not in irrigation_waterway_types
            and distance_m <= self.settings.water_reject_distance_m
        ):
            return True, "POINT_ON_OR_NEXT_TO_WATER"
        if category == "natural" and feature_type in {
            "water",
            "bay",
            "wetland",
            "coastline",
        } and distance_m <= self.settings.water_reject_distance_m:
            return True, "POINT_ON_OR_NEXT_TO_WATER"
        return False, "NO_DISTANCE_BASED_LOCATION_BLOCK"

    @staticmethod
    def _text(value: Any) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None
