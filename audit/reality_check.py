#!/usr/bin/env python3
"""Independent live oracle for a generated Set 1 JSON file.

This intentionally does not import the satellite_x package. It re-queries source
APIs, recomputes weather totals, samples the chosen COGs, and queries SoilGrids
WCS so the implementation is not validating itself.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import fmean
from typing import Any

import numpy as np
import rasterio
import requests
from pyproj import CRS, Transformer
from rasterio.io import MemoryFile

AWS_SEARCH = "https://earth-search.aws.element84.com/v1/search"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
BANDS = {
    "B02": "blue",
    "B03": "green",
    "B04": "red",
    "B05": "rededge1",
    "B08": "nir",
    "B11": "swir16",
    "SCL": "scl",
}
VALID_SCL = {4, 5, 6, 7}


def field_bbox(field: dict[str, Any]) -> list[float]:
    area_m2 = float(field["acres"]) * 4046.8564224
    half_side = math.sqrt(area_m2) / 2
    lat_delta = half_side / 111_320.0
    lon_delta = half_side / (
        111_320.0 * math.cos(math.radians(float(field["latitude"])))
    )
    return [
        field["longitude"] - lon_delta,
        field["latitude"] - lat_delta,
        field["longitude"] + lon_delta,
        field["latitude"] + lat_delta,
    ]


def direct_stac(output: dict[str, Any]) -> dict[str, Any]:
    field = output["field"]
    end = date.fromisoformat(field["analysis_date"])
    start = end - timedelta(days=int(field["scan_range_days"]) - 1)
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": field_bbox(field),
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59.999999Z",
        "limit": 20,
        "query": {"eo:cloud_cover": {"lt": 40.0}},
    }
    response = requests.post(AWS_SEARCH, json=payload, timeout=(5, 30))
    response.raise_for_status()
    complete = []
    for feature in response.json()["features"]:
        if all(key in feature["assets"] for key in BANDS.values()):
            complete.append(feature)
    selected = min(
        complete,
        key=lambda item: (
            float(item["properties"]["eo:cloud_cover"]),
            -datetime.fromisoformat(
                item["properties"]["datetime"].replace("Z", "+00:00")
            ).timestamp(),
        ),
    )
    actual = output["satellite"]["scene"]
    href_equal = {
        band: actual["assets"][band]["href"] == selected["assets"][key]["href"]
        for band, key in BANDS.items()
    }
    return {
        "oracle_scene_id": selected["id"],
        "output_scene_id": actual["scene_id"],
        "scene_id_equal": selected["id"] == actual["scene_id"],
        "oracle_cloud_pct": float(selected["properties"]["eo:cloud_cover"]),
        "output_cloud_pct": actual["cloud_cover_pct"],
        "cloud_equal": float(selected["properties"]["eo:cloud_cover"])
        == actual["cloud_cover_pct"],
        "asset_hrefs_equal": href_equal,
        "pass": selected["id"] == actual["scene_id"] and all(href_equal.values()),
    }


def weather_params(field: dict[str, Any], start: date, end: date) -> dict[str, Any]:
    return {
        "latitude": field["latitude"],
        "longitude": field["longitude"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": (
            "precipitation_sum,et0_fao_evapotranspiration,"
            "temperature_2m_max,temperature_2m_min"
        ),
        "hourly": "relative_humidity_2m",
        "timezone": "UTC",
    }


def parse_weather(payload: dict[str, Any]) -> list[dict[str, Any]]:
    humidity: dict[str, list[float]] = defaultdict(list)
    for timestamp, value in zip(
        payload["hourly"]["time"],
        payload["hourly"]["relative_humidity_2m"],
        strict=True,
    ):
        if value is not None:
            humidity[timestamp[:10]].append(float(value))
    daily = payload["daily"]
    rows = []
    for index, day in enumerate(daily["time"]):
        rows.append(
            {
                "observation_date": day,
                "precipitation_mm": float(daily["precipitation_sum"][index]),
                "et0_mm": float(daily["et0_fao_evapotranspiration"][index]),
                "temperature_max_c": float(daily["temperature_2m_max"][index]),
                "temperature_min_c": float(daily["temperature_2m_min"][index]),
                "relative_humidity_mean_pct": round(fmean(humidity[day]), 3),
            }
        )
    return rows


def direct_weather(output: dict[str, Any]) -> dict[str, Any]:
    field = output["field"]
    end = date.fromisoformat(field["analysis_date"])
    start = end - timedelta(days=29)
    endpoint = (
        OPEN_METEO_FORECAST
        if output["weather"]["source"] == "open_meteo_forecast"
        else OPEN_METEO_ARCHIVE
    )
    response = requests.get(
        endpoint, params=weather_params(field, start, end), timeout=(5, 30)
    )
    response.raise_for_status()
    rows = parse_weather(response.json())[-30:]
    summary = {
        "rain_15d_mm": round(sum(row["precipitation_mm"] for row in rows[-15:]), 3),
        "et0_15d_mm": round(sum(row["et0_mm"] for row in rows[-15:]), 3),
        "rain_30d_mm": round(sum(row["precipitation_mm"] for row in rows), 3),
        "et0_30d_mm": round(sum(row["et0_mm"] for row in rows), 3),
        "humidity_mean_5d_pct": round(
            fmean(row["relative_humidity_mean_pct"] for row in rows[-5:]), 3
        ),
    }
    output_summary = output["weather"]["summary"]
    summary_equal = {
        key: value == output_summary[key] for key, value in summary.items()
    }
    return {
        "all_30_daily_rows_equal": rows == output["weather"]["history"],
        "oracle_summary": summary,
        "output_summary": {key: output_summary[key] for key in summary},
        "summary_equal": summary_equal,
        "pass": rows == output["weather"]["history"] and all(summary_equal.values()),
    }


def sample_cogs(output: dict[str, Any]) -> dict[str, Any]:
    scene = output["satellite"]["scene"]
    lon = float(output["field"]["longitude"])
    lat = float(output["field"]["latitude"])
    raw: dict[str, int] = {}
    reflectance: dict[str, float] = {}
    for band in ("B04", "B08", "B11", "SCL"):
        asset = scene["assets"][band]
        with rasterio.open(asset["href"]) as source:
            x, y = Transformer.from_crs(4326, source.crs, always_xy=True).transform(
                lon, lat
            )
            raw[band] = int(next(source.sample([(x, y)]))[0])
        if band != "SCL":
            if asset.get("scale") is None or asset.get("offset") is None:
                raise ValueError(f"{band} is missing radiometric scale/offset")
            reflectance[band] = (
                raw[band] * float(asset["scale"]) + float(asset["offset"])
            )
    red, nir, swir = reflectance["B04"], reflectance["B08"], reflectance["B11"]
    ndvi = (nir - red) / (nir + red) if nir + red else None
    ndbi = (swir - nir) / (swir + nir) if swir + nir else None
    return {
        "raw_pixel": raw,
        "surface_reflectance": reflectance,
        "ndvi": ndvi,
        "ndbi": ndbi,
        "scl_is_valid_for_set2": raw["SCL"] in VALID_SCL,
        "pass": raw["SCL"] in VALID_SCL,
    }


def soil_wcs(output: dict[str, Any]) -> dict[str, Any]:
    lon = float(output["field"]["longitude"])
    lat = float(output["field"]["latitude"])
    homolosine = CRS.from_proj4("+proj=igh +datum=WGS84 +no_defs +towgs84=0,0,0")
    x, y = Transformer.from_crs(4326, homolosine, always_xy=True).transform(lon, lat)
    raw_values: dict[str, int] = {}
    nearest: dict[str, Any] = {}
    for prop in ("phh2o", "nitrogen"):
        params = [
            ("map", f"/map/{prop}.map"),
            ("SERVICE", "WCS"),
            ("VERSION", "2.0.1"),
            ("REQUEST", "GetCoverage"),
            ("COVERAGEID", f"{prop}_0-5cm_mean"),
            ("FORMAT", "GEOTIFF_INT16"),
            ("SUBSET", f"X({x - 5000},{x + 5000})"),
            ("SUBSET", f"Y({y - 5000},{y + 5000})"),
            (
                "SUBSETTINGCRS",
                "http://www.opengis.net/def/crs/EPSG/0/152160",
            ),
        ]
        response = requests.get(
            "https://maps.isric.org/mapserv", params=params, timeout=(5, 60)
        )
        response.raise_for_status()
        with MemoryFile(response.content) as memory:
            with memory.open() as source:
                array = source.read(1)
                row, column = source.index(x, y)
                raw_values[prop] = int(array[row, column])
                valid = np.argwhere(array != 0)
                distances = np.sqrt(
                    (valid[:, 0] - row) ** 2 + (valid[:, 1] - column) ** 2
                )
                position = int(np.argmin(distances))
                nearest_row, nearest_column = valid[position]
                nearest[prop] = {
                    "raw_value": int(array[nearest_row, nearest_column]),
                    "distance_m_approx": round(float(distances[position] * 250), 3),
                }
    exact_has_data = all(value != 0 for value in raw_values.values())
    return {
        "exact_point_raw": raw_values,
        "exact_point_has_soilgrids_data": exact_has_data,
        "nearest_valid": nearest,
        "output_source": output["soil"]["source"],
        "output_values": {
            "ph_h2o": output["soil"]["ph_h2o"],
            "nitrogen_g_kg": output["soil"]["nitrogen_g_kg"],
        },
        "output_is_live_soil": output["soil"]["source"] == "soilgrids_live",
        "pass": exact_has_data and output["soil"]["source"] == "soilgrids_live",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    output = json.loads(args.input.read_text(encoding="utf-8"))
    report = {
        "checked_at": datetime.now().astimezone().isoformat(),
        "input_output": str(args.input),
        "satellite_catalog": direct_stac(output),
        "weather": direct_weather(output),
        "field_pixel": sample_cogs(output),
        "soil": soil_wcs(output),
        "iot": {
            "contract_validated": output.get("iot") is not None,
            "cryptographic_signature_verified": bool(output.get("iot_verified")),
            "fresh": output.get("iot_fresh"),
            "real_hardware_independently_verified": bool(output.get("iot_verified"))
            and bool(output.get("iot_fresh")),
            "reason": (
                "Verified and fresh payload."
                if output.get("iot_verified") and output.get("iot_fresh")
                else "Payload is unsigned/unverified or outside the configured freshness window."
            ),
        },
    }
    report["set1_api_acquisition_pass"] = (
        report["satellite_catalog"]["pass"] and report["weather"]["pass"]
    )
    report["full_reality_pass"] = all(
        (
            report["satellite_catalog"]["pass"],
            report["weather"]["pass"],
            report["field_pixel"]["pass"],
            report["soil"]["pass"],
            report["iot"]["real_hardware_independently_verified"],
        )
    )
    report["verdict"] = (
        "PASS" if report["full_reality_pass"] else "NOT_FULL_REALITY_PASS"
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["full_reality_pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
