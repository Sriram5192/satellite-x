"""Independent Sentinel-1 RTC oracle: direct STAC/token/COG calculations.

This script intentionally imports no SATELLITE-X application modules.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import numpy as np
import requests
import rasterio
from pyproj import Transformer
from rasterio.mask import mask
from shapely.geometry import mapping, shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
request = json.loads((ROOT / "examples/sar_fallback_crop_field_request.json").read_text())
actual = json.loads((ROOT / "outputs/sar_fallback_crop_field_result.json").read_text())
geom = request["boundary_geojson"]
xs = [point[0] for ring in geom["coordinates"] for point in ring]
ys = [point[1] for ring in geom["coordinates"] for point in ring]
search_response = requests.post("https://planetarycomputer.microsoft.com/api/stac/v1/search", json={
    "collections": ["sentinel-1-rtc"],
    "bbox": [min(xs), min(ys), max(xs), max(ys)],
    "datetime": "2026-07-19T00:00:00+00:00/2026-08-17T23:59:59.999999+00:00",
    "limit": 20,
}, timeout=60)
search_response.raise_for_status()
search = search_response.json()
features = sorted(search["features"], key=lambda f: f["properties"]["datetime"], reverse=True)
feature = next(f for f in features if "vv" in f["assets"] and "vh" in f["assets"])
token_response = requests.get("https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel1euwestrtc/sentinel1-grd-rtc", timeout=30)
token_response.raise_for_status()
token = token_response.json()["token"]

arrays = {}
common = None
for band in ("vv", "vh"):
    href = feature["assets"][band]["href"] + "?" + token
    with rasterio.open(href) as src:
        project = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True).transform
        projected = mapping(transform(project, shape(geom)))
        raster, _ = mask(src, [projected], crop=True, filled=False)
        arr = np.ma.asarray(raster[0], dtype="float64")
        valid = ~np.ma.getmaskarray(arr) & np.isfinite(arr.data) & (arr.data > 0)
        arrays[band] = arr.data
        common = valid if common is None else common & valid

vv = arrays["vv"][common]
vh = arrays["vh"][common]
vv_db = 10 * np.log10(vv)
vh_db = 10 * np.log10(vh)
expected = {
    "scene_id": feature["id"],
    "valid_pixels": int(common.sum()),
    "vv_db_mean": round(float(vv_db.mean()), 6),
    "vh_db_mean": round(float(vh_db.mean()), 6),
    "vv_minus_vh_db_mean": round(float((vv_db - vh_db).mean()), 6),
}
checks = {
    key: (actual[key] == value if isinstance(value, (str, int)) else abs(actual[key] - value) <= 1e-6)
    for key, value in expected.items()
}
report = {"oracle": "independent_direct_planetary_computer_cog", "expected": expected, "actual": {k: actual[k] for k in expected}, "checks": checks, "passed": all(checks.values())}
(ROOT / "outputs/sar_reality.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
