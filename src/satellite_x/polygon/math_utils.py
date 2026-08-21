"""Small geodesic helpers with deterministic behavior."""

from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_008.8
ACRE_M2 = 4046.8564224


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(value))


def search_bbox(latitude: float, longitude: float, radius_m: float) -> list[float]:
    lat_delta = radius_m / 111_320.0
    lon_delta = radius_m / max(
        111_320.0 * math.cos(math.radians(latitude)), 1.0
    )
    return [
        longitude - lon_delta,
        latitude - lat_delta,
        longitude + lon_delta,
        latitude + lat_delta,
    ]
