#!/usr/bin/env python3
"""Independently evaluate SCL field-valid percentage for all candidate scenes."""

from __future__ import annotations

import argparse
import json
import math
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import requests
from rasterio.errors import NotGeoreferencedWarning
from rasterio.mask import mask
from rasterio.warp import transform_geom


def bbox_and_geometry(field: dict[str, Any]) -> tuple[list[float], dict[str, Any]]:
    if field.get("boundary_geojson"):
        geometry = field["boundary_geojson"]
        points: list[tuple[float, float]] = []

        def collect(node: Any) -> None:
            if (
                isinstance(node, list)
                and len(node) >= 2
                and isinstance(node[0], (int, float))
                and isinstance(node[1], (int, float))
            ):
                points.append((float(node[0]), float(node[1])))
            elif isinstance(node, list):
                for child in node:
                    collect(child)

        collect(geometry["coordinates"])
        longitudes, latitudes = zip(*points)
        return [min(longitudes), min(latitudes), max(longitudes), max(latitudes)], geometry

    area_m2 = float(field["acres"]) * 4046.8564224
    half_side = math.sqrt(area_m2) / 2
    lat = float(field["latitude"])
    lon = float(field["longitude"])
    lat_delta = half_side / 111_320.0
    lon_delta = half_side / (111_320.0 * math.cos(math.radians(lat)))
    bbox = [lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta]
    geometry = {
        "type": "Polygon",
        "coordinates": [[
            [bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]],
            [bbox[0], bbox[3]], [bbox[0], bbox[1]],
        ]],
    }
    return bbox, geometry


def classify(valid_pct: float, cloud_pct: float) -> str:
    if valid_pct >= 90 and cloud_pct < 10:
        return "HIGH"
    if valid_pct >= 60 and cloud_pct <= 40:
        return "MEDIUM"
    return "LOW"


def main() -> int:
    warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expand-days", type=int, default=30)
    args = parser.parse_args()
    core = json.loads(args.input.read_text(encoding="utf-8"))
    field = core["field"]
    bbox, geometry = bbox_and_geometry(field)
    end = date.fromisoformat(field["analysis_date"])
    start = end - timedelta(days=int(field["scan_range_days"]) - 1 + args.expand_days)
    query = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "limit": 100,
    }
    response = requests.post(
        "https://earth-search.aws.element84.com/v1/search",
        json=query,
        timeout=(5, 60),
    )
    response.raise_for_status()
    features = response.json()["features"]

    def inspect(feature: dict[str, Any]) -> dict[str, Any]:
        with rasterio.open(feature["assets"]["scl"]["href"]) as source:
            projected = transform_geom("EPSG:4326", source.crs, geometry, precision=3)
            array, _ = mask(
                source, [projected], crop=True, all_touched=False, filled=False
            )
            scl = array[0]
            inside = ~scl.mask if np.ndim(scl.mask) else scl.data != source.nodata
            values = scl.data[inside]
        valid = int(np.isin(values, [4, 5, 6, 7]).sum())
        total = int(values.size)
        valid_pct = round(100.0 * valid / total, 2) if total else 0.0
        cloud = float(feature["properties"]["eo:cloud_cover"])
        counts = {
            str(code): int((values == code).sum())
            for code in range(12)
            if (values == code).any()
        }
        return {
            "date": feature["properties"]["datetime"][:10],
            "scene_id": feature["id"],
            "scene_cloud_pct": cloud,
            "field_pixels": total,
            "valid_pixels": valid,
            "field_valid_pct": valid_pct,
            "scl_counts": counts,
            "quality": classify(valid_pct, cloud),
            "selected_by_set1": feature["id"]
            == core["satellite"]["scene"]["scene_id"],
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(inspect, features))
    results.sort(key=lambda item: (item["date"], item["scene_id"]))
    report = {
        "search_start": start.isoformat(),
        "search_end": end.isoformat(),
        "field_boundary_source": "acreage_square" if not field.get("boundary_geojson") else "geojson",
        "selected_scene_id": core["satellite"]["scene"]["scene_id"],
        "selected_scene_quality": next(
            item["quality"] for item in results if item["selected_by_set1"]
        ),
        "acceptable_alternatives": [
            item["scene_id"] for item in results if item["quality"] in {"HIGH", "MEDIUM"}
        ],
        "scenes": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
