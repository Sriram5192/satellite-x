"""Polygon topology repair and metric validation in a local metric CRS."""

from __future__ import annotations

from typing import Any

from .errors import BoundaryValidationError
from .math_utils import ACRE_M2
from .models import GeometryValidation, PolygonRecoveryInput


def _imports():
    try:
        from pyproj import Transformer
        from shapely import make_valid
        from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, mapping, shape
        from shapely.ops import transform, unary_union
    except ImportError as exc:
        raise BoundaryValidationError(
            "shapely and pyproj are required; install project dependencies"
        ) from exc
    return {
        "Transformer": Transformer,
        "make_valid": make_valid,
        "GeometryCollection": GeometryCollection,
        "MultiPolygon": MultiPolygon,
        "Point": Point,
        "Polygon": Polygon,
        "mapping": mapping,
        "shape": shape,
        "transform": transform,
        "unary_union": unary_union,
    }


def metric_epsg(latitude: float, longitude: float) -> int:
    zone = int((longitude + 180) // 6) + 1
    return (32600 if latitude >= 0 else 32700) + zone


def normalize_and_validate(
    geometry_geojson: dict[str, Any],
    request: PolygonRecoveryInput,
) -> tuple[dict[str, Any], GeometryValidation]:
    geo = _imports()
    try:
        original = geo["shape"](geometry_geojson)
    except Exception as exc:
        raise BoundaryValidationError(f"invalid GeoJSON: {exc}") from exc
    if original.is_empty:
        raise BoundaryValidationError("boundary geometry is empty")

    repaired = not original.is_valid
    candidate = geo["make_valid"](original) if repaired else original
    if isinstance(candidate, geo["GeometryCollection"]):
        polygons = [
            item
            for item in candidate.geoms
            if isinstance(item, (geo["Polygon"], geo["MultiPolygon"]))
            and not item.is_empty
        ]
        if not polygons:
            raise BoundaryValidationError("geometry repair produced no polygon")
        candidate = geo["unary_union"](polygons)
        repaired = True
    if not isinstance(candidate, (geo["Polygon"], geo["MultiPolygon"])):
        raise BoundaryValidationError("boundary must be Polygon or MultiPolygon")
    if candidate.is_empty or not candidate.is_valid:
        raise BoundaryValidationError("boundary remains invalid after repair")

    transformer = geo["Transformer"].from_crs(
        4326, metric_epsg(request.latitude, request.longitude), always_xy=True
    )
    metric_geometry = geo["transform"](transformer.transform, candidate)
    point = geo["Point"](request.longitude, request.latitude)
    metric_point = geo["transform"](transformer.transform, point)
    area_m2 = float(metric_geometry.area)
    perimeter_m = float(metric_geometry.length)
    if area_m2 <= 0 or perimeter_m <= 0:
        raise BoundaryValidationError("boundary has zero area or perimeter")

    distance_m = float(metric_geometry.distance(metric_point))
    contains = bool(candidate.covers(point))
    area_acres = area_m2 / ACRE_M2
    area_difference_pct = abs(area_acres - request.acres) / request.acres * 100
    warnings: list[str] = []
    if repaired:
        warnings.append("Invalid topology was repaired with make_valid.")
    if distance_m > request.gps_tolerance_m:
        warnings.append(
            f"Boundary is {distance_m:.2f} m from the GPS point; "
            f"tolerance is {request.gps_tolerance_m:.2f} m."
        )
    if area_difference_pct > 50:
        warnings.append(
            f"Boundary area differs from farmer-reported acres by {area_difference_pct:.2f}%."
        )

    normalized = geo["mapping"](candidate)
    validation = GeometryValidation(
        valid=distance_m <= request.gps_tolerance_m,
        geometry_type=candidate.geom_type,
        area_m2=round(area_m2, 3),
        area_acres=round(area_acres, 6),
        perimeter_m=round(perimeter_m, 3),
        contains_input_point=contains,
        point_distance_m=round(distance_m, 3),
        area_difference_pct=round(area_difference_pct, 3),
        repaired=repaired,
        warnings=warnings,
    )
    return normalized, validation
