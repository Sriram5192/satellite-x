#!/usr/bin/env python3
"""Independent Set 3/4 oracle. Does not import satellite_x."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.warp import Resampling, reproject, transform_geom


def load_means(preprocessing):
    scene = preprocessing["selected_scene"]
    geometry = preprocessing["request"]["boundary_geojson"]
    with rasterio.open(scene["assets"]["SCL"]["href"]) as source:
        projected = transform_geom("EPSG:4326", source.crs, geometry, precision=3)
        scl_masked, target_transform = mask(source, [projected], crop=True, filled=False)
        target_crs = source.crs
    scl = scl_masked[0]
    valid = (~np.ma.getmaskarray(scl)) & np.isin(scl.data, [4, 5, 6, 7])
    bands = {}
    for band in ["B02", "B03", "B04", "B05", "B08", "B11"]:
        asset = scene["assets"][band]
        destination = np.full(scl.shape, np.nan, dtype="float32")
        with rasterio.open(asset["href"]) as source:
            reproject(
                rasterio.band(source, 1), destination,
                src_transform=source.transform, src_crs=source.crs,
                src_nodata=source.nodata, dst_transform=target_transform,
                dst_crs=target_crs, dst_nodata=np.nan, resampling=Resampling.bilinear,
            )
        values = destination * asset["scale"] + asset["offset"]
        bands[band] = values
        valid &= np.isfinite(values) & (values >= 0) & (values <= 1.2)
    b, g, r, re, n, s = [bands[k] for k in ["B02", "B03", "B04", "B05", "B08", "B11"]]
    eps = 1e-10
    arrays = {
        "ndvi": (n-r)/(n+r+eps),
        "evi": 2.5*(n-r)/(n+6*r-7.5*b+1+eps),
        "savi": 1.5*(n-r)/(n+r+0.5+eps),
        "ndre": (n-re)/(n+re+eps),
        "ndmi": (n-s)/(n+s+eps),
        "ndwi": (g-n)/(g+n+eps),
        "gndvi": (n-g)/(n+g+eps),
    }
    means = {}
    for name, array in arrays.items():
        index_valid = valid & np.isfinite(array)
        if name in {"ndvi", "ndre", "ndmi", "ndwi", "gndvi"}:
            index_valid &= (array >= -1) & (array <= 1)
        elif name == "savi":
            index_valid &= (array >= -1.5) & (array <= 1.5)
        else:
            index_valid &= (array >= -2) & (array <= 2)
        means[name] = round(float(np.mean(array[index_valid])), 6)
    return means, int(valid.sum()), int((~np.ma.getmaskarray(scl)).sum())


def independent_verdict(analytics, quality, sowing_quality):
    ndvi = analytics["indices"]["ndvi"]["mean"]
    ndmi = analytics["indices"]["ndmi"]["mean"]
    ndre = analytics["indices"]["ndre"]["mean"]
    p = analytics["phenology"]
    w = analytics["water_balance"]
    soil = analytics["soil"]
    ndvi_low = ndvi < p["expected_ndvi_low"]
    moisture_low = ndmi < 0.10
    deficit = w["water_balance_15d_mm"] < -30
    humid = w["humidity_mean_5d_pct"] is not None and w["humidity_mean_5d_pct"] > 85
    trusted = soil["source"] in {"soilgrids_live", "cache"}
    nitrogen = trusted and soil["nitrogen_g_kg"] < 0.20
    if ndvi_low and moisture_low and deficit:
        verdict = "CONFIRMED_WATER_STRESS"
    elif ndvi_low and w["water_balance_15d_mm"] >= 0 and humid:
        verdict = "SUSPECTED_FUNGAL_RISK"
    elif ndvi_low and ndre < 0.20 and nitrogen:
        verdict = "NITROGEN_DEFICIENCY_EVIDENCE"
    elif ndvi_low and p["stage_name"] in {"Maturity", "Post-season"} and p["criticality"] == "LOW":
        verdict = "NORMAL_MATURITY"
    else:
        verdict = "NORMAL_OR_UNRESOLVED"
    q = {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.2}[quality]
    completeness = (2 + int(trusted)) / 3
    fraction = sum([ndvi_low, moisture_low, deficit]) / 3
    agreement = abs(fraction - 0.5) * 2
    penalty = {"known": 0, "approximate_month": 10, "unknown": 30}[sowing_quality]
    confidence = round(max(0, min(100, (0.4*q+0.3*completeness+0.3*agreement)*100-penalty)), 3)
    return verdict, confidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preprocessing", type=Path, required=True)
    parser.add_argument("--set1", type=Path, required=True)
    parser.add_argument("--analytics", type=Path, required=True)
    parser.add_argument("--diagnosis", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    preprocessing = json.loads(args.preprocessing.read_text())
    set1 = json.loads(args.set1.read_text())
    analytics = json.loads(args.analytics.read_text())
    diagnosis = json.loads(args.diagnosis.read_text())
    means, valid, inside = load_means(preprocessing)
    expected_water = round(
        set1["weather"]["summary"]["rain_15d_mm"]
        - set1["weather"]["summary"]["et0_15d_mm"], 3
    )
    expected_das = (
        date.fromisoformat(analytics["scene_date"])
        - date.fromisoformat(set1["field"]["sowing_date"])
    ).days
    verdict, confidence = independent_verdict(
        analytics, preprocessing["selected_quality"]["quality"], "known"
    )
    checks = {
        **{f"{name}_mean_equal": value == analytics["indices"][name]["mean"] for name, value in means.items()},
        "spectral_pixels_equal": valid == analytics["spectral_valid_pixels"],
        "water_balance_equal": expected_water == analytics["water_balance"]["water_balance_15d_mm"],
        "das_equal": expected_das == analytics["phenology"]["das"],
        "verdict_equal": verdict == diagnosis["verdict"],
        "confidence_equal": confidence == diagnosis["confidence"]["final_confidence_pct"],
    }
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "means": means, "spectral_pixels": valid, "inside_pixels": inside,
        "water_balance_mm": expected_water, "das": expected_das,
        "verdict": verdict, "confidence_pct": confidence,
        "checks": checks, "pass": all(checks.values()),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pass"] else 6


if __name__ == "__main__":
    raise SystemExit(main())
