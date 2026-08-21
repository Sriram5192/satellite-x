#!/usr/bin/env python3
"""Independent live oracle for polygon recovery outputs.

This script intentionally does not import the satellite_x package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import requests
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform

FTW_AP = (
    "https://data.source.coop/ftw/global-data/predictions/vectors/alpha/"
    "results-by-admin-conf/admin:country_code=IN/IN_AP.parquet"
)
EARTH_RADIUS_M = 6_371_008.8


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    value = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(value))


def reverse_distance(lat, lon):
    response = requests.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 18, "addressdetails": 1},
        headers={"User-Agent": "Satellite-X-independent-polygon-audit/0.1"},
        timeout=(5, 30),
    )
    response.raise_for_status()
    payload = response.json()
    distance = haversine(lat, lon, float(payload["lat"]), float(payload["lon"]))
    return payload, distance


def direct_ftw(lat, lon, target_m2):
    connection = duckdb.connect(database=":memory:")
    try:
        for extension in ("httpfs", "spatial"):
            try:
                connection.execute(f"LOAD {extension}")
            except Exception:
                connection.execute(f"INSTALL {extension}; LOAD {extension}")
        query = f'''
            SELECT id,
                   EXTRACT(year FROM "determination:datetime")::INTEGER AS year,
                   "metrics:area" AS area_m2,
                   confidence,
                   ST_AsGeoJSON(geometry) AS geometry_json
            FROM read_parquet('{FTW_AP}')
            WHERE bbox.xmin <= {lon} AND bbox.xmax >= {lon}
              AND bbox.ymin <= {lat} AND bbox.ymax >= {lat}
              AND ST_Contains(geometry, ST_Point({lon}, {lat}))
              AND "metrics:area" BETWEEN {target_m2 * 0.2} AND {target_m2 * 5.0}
            ORDER BY year DESC, abs("metrics:area" - {target_m2}) ASC
        '''
        return connection.execute(query).fetchall()
    finally:
        connection.close()


def independent_metric_area(geometry, lat, lon):
    zone = int((lon + 180) // 6) + 1
    transformer = Transformer.from_crs(4326, 32600 + zone, always_xy=True)
    return transform(transformer.transform, shape(geometry)).area


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--road", type=Path, required=True)
    parser.add_argument("--recovery", type=Path, required=True)
    parser.add_argument("--confirmed", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    road = json.loads(args.road.read_text())
    recovery = json.loads(args.recovery.read_text())
    confirmed = json.loads(args.confirmed.read_text())

    road_request = road["request"]
    rural_request = recovery["request"]
    road_raw, road_distance = reverse_distance(
        road_request["latitude"], road_request["longitude"]
    )
    rural_raw, rural_road_distance = reverse_distance(
        rural_request["latitude"], rural_request["longitude"]
    )
    target_m2 = rural_request["acres"] * 4046.8564224
    rows = direct_ftw(
        rural_request["latitude"], rural_request["longitude"], target_m2
    )
    direct_first_id = None
    if rows:
        normalized = mapping(shape(json.loads(rows[0][4])))
        digest = hashlib.sha256(
            json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()[:10]
        direct_first_id = (
            f"ftw-{rural_request['country_code']}-"
            f"{rural_request['subdivision_code']}-{rows[0][0]}-"
            f"{rows[0][1]}-{digest}"
        )
    measured_area = independent_metric_area(
        confirmed["boundary_geojson"],
        rural_request["latitude"],
        rural_request["longitude"],
    )
    checks = {
        "road_reverse_category_is_highway": road_raw.get("category") == "highway",
        "road_distance_below_20m": road_distance <= 20,
        "road_output_rejected": road["status"] == "rejected_location",
        "rural_nearest_road_beyond_20m": rural_road_distance > 20,
        "direct_ftw_found_rows": bool(rows),
        "selected_candidate_matches_direct_ftw": recovery["selected_candidate_id"] == direct_first_id,
        "confirmed_candidate_matches_selection": confirmed["source_candidate_id"]
        == recovery["selected_candidate_id"],
        "independent_area_matches_output": abs(
            measured_area - confirmed["validation"]["area_m2"]
        ) < 0.01,
        "remote_polygon_not_claimed_legal": confirmed["legal_boundary"] is False,
    }
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "road": {
            "category": road_raw.get("category"),
            "type": road_raw.get("type"),
            "feature_distance_m": round(road_distance, 3),
            "output_status": road["status"],
        },
        "open_field": {
            "nearest_reverse_feature": rural_raw.get("display_name"),
            "nearest_feature_distance_m": round(rural_road_distance, 3),
            "direct_ftw_rows": len(rows),
            "direct_first_candidate_id": direct_first_id,
            "output_selected_candidate_id": recovery["selected_candidate_id"],
            "independent_area_m2": round(measured_area, 3),
            "output_area_m2": confirmed["validation"]["area_m2"],
        },
        "pass": all(checks.values()),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pass"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
