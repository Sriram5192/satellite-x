#!/usr/bin/env python3
"""Independent oracle for a Set 2 preprocessing JSON output.

Does not import satellite_x. Re-reads the public COGs and recomputes quality
and calibrated indices from the confirmed polygon.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.warp import Resampling, reproject, transform_geom

VALID_SCL = {4, 5, 6, 7}


def recompute(result):
    request = result["request"]
    scene = result["selected_scene"]
    geometry_wgs84 = request["boundary_geojson"]
    assets = scene["assets"]
    with rasterio.open(assets["SCL"]["href"]) as source:
        geometry = transform_geom("EPSG:4326", source.crs, geometry_wgs84, precision=3)
        scl_masked, target_transform = mask(
            source, [geometry], crop=True, all_touched=False, filled=False
        )
        target_crs = source.crs
    scl = scl_masked[0]
    inside = ~np.ma.getmaskarray(scl)
    values = scl.data[inside]
    scl_valid = inside & np.isin(scl.data, list(VALID_SCL))
    counts = {
        str(code): int((values == code).sum())
        for code in range(12)
        if (values == code).any()
    }
    reflectance = {}
    for band in ("B04", "B08", "B11"):
        asset = assets[band]
        destination = np.full(scl.shape, np.nan, dtype="float32")
        with rasterio.open(asset["href"]) as source:
            reproject(
                source=rasterio.band(source, 1), destination=destination,
                src_transform=source.transform, src_crs=source.crs,
                src_nodata=source.nodata, dst_transform=target_transform,
                dst_crs=target_crs, dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
        reflectance[band] = destination * asset["scale"] + asset["offset"]
    red, nir, swir = reflectance["B04"], reflectance["B08"], reflectance["B11"]
    physical = (
        np.isfinite(red) & np.isfinite(nir) & np.isfinite(swir)
        & (red >= 0) & (nir >= 0) & (swir >= 0)
        & (red <= 1.2) & (nir <= 1.2) & (swir <= 1.2)
    )
    spectral = scl_valid & physical & (np.abs(nir + red) > 1e-6) & (
        np.abs(swir + nir) > 1e-6
    )
    ndvi = (nir - red) / (nir + red + 1e-10)
    ndbi = (swir - nir) / (swir + nir + 1e-10)
    built = spectral & (ndbi > 0.08) & (ndvi < 0.20)
    return {
        "total": int(values.size),
        "valid": int(scl_valid.sum()),
        "valid_pct": round(100 * int(scl_valid.sum()) / int(values.size), 3),
        "counts": counts,
        "spectral": int(spectral.sum()),
        "spectral_pct": round(100 * int(spectral.sum()) / int(inside.sum()), 3),
        "mean_ndvi": round(float(np.mean(ndvi[spectral])), 6),
        "mean_ndbi": round(float(np.mean(ndbi[spectral])), 6),
        "built_pct": round(100 * int(built.sum()) / int(spectral.sum()), 3),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = json.loads(args.input.read_text())
    oracle = recompute(result)
    quality = result["selected_quality"]
    urban = result["urban_gate"]
    request = result["request"]
    original_start = date.fromisoformat(request["analysis_date"]) - timedelta(
        days=request["scan_range_days"] - 1
    )
    selected_date = datetime.fromisoformat(
        result["selected_scene"]["acquired_at"].replace("Z", "+00:00")
    ).date()
    checks = {
        "status_accepted": result["status"] == "accepted",
        "expanded_scene_is_older_than_original_start": selected_date < original_start,
        "expanded_flag_true": result["expanded_search_used"] is True,
        "total_pixels_equal": oracle["total"] == quality["total_field_pixels"],
        "valid_pixels_equal": oracle["valid"] == quality["valid_field_pixels"],
        "valid_pct_equal": oracle["valid_pct"] == quality["field_valid_pct"],
        "scl_counts_equal": oracle["counts"] == quality["scl_counts"],
        "spectral_pixels_equal": oracle["spectral"] == urban["spectral_valid_pixels"],
        "spectral_pct_equal": oracle["spectral_pct"] == urban["spectral_valid_pct"],
        "ndvi_equal": oracle["mean_ndvi"] == urban["mean_ndvi"],
        "ndbi_equal": oracle["mean_ndbi"] == urban["mean_ndbi"],
        "built_pct_equal": oracle["built_pct"] == urban["built_pixel_pct"],
        "urban_not_rejected": urban["urban_rejected"] is False,
    }
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "scene_id": result["selected_scene"]["scene_id"],
        "oracle": oracle,
        "output_quality": quality,
        "output_urban_gate": urban,
        "checks": checks,
        "pass": all(checks.values()),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pass"] else 5


if __name__ == "__main__":
    raise SystemExit(main())
