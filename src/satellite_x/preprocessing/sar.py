"""Sentinel-1 RTC cloud-independent field fallback via Planetary Computer."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from urllib.parse import urlparse

import numpy as np

from ..config import Settings
from ..http import JsonHttpClient
from ..models import utc_now
from .catalog import geometry_bbox
from .models import SarFallbackInput, SarFallbackResult


class SarFallbackService:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http: JsonHttpClient | None = None,
        clock: Callable[[], datetime] = utc_now,
    ):
        self.settings = settings or Settings.from_env()
        self.http = http or JsonHttpClient(self.settings)
        self._owns_http = http is None
        self.clock = clock

    def run(self, request: SarFallbackInput) -> SarFallbackResult:
        start = request.analysis_date - timedelta(days=request.scan_range_days - 1)
        payload = {
            "collections": ["sentinel-1-rtc"],
            "bbox": geometry_bbox(request.boundary_geojson),
            "datetime": (
                f"{datetime.combine(start, time.min, timezone.utc).isoformat()}/"
                f"{datetime.combine(request.analysis_date, time.max, timezone.utc).isoformat()}"
            ),
            "limit": 20,
        }
        try:
            response = self.http.post_json(
                "planetary_computer_stac",
                f"{self.settings.planetary_computer_stac_url}/search",
                payload=payload,
            )
            features = response.get("features", [])
            candidates = [
                feature for feature in features
                if "vv" in feature.get("assets", {}) and "vh" in feature.get("assets", {})
            ]
            if not candidates:
                return SarFallbackResult(
                    field_id=request.field_id, processed_at=self.clock(), status="no_scene",
                    warnings=["No dual-polarization Sentinel-1 RTC scene was found."],
                )
            candidates.sort(
                key=lambda item: item["properties"]["datetime"], reverse=True
            )
            token_payload = self.http.get_json(
                "planetary_computer_sas",
                self.settings.planetary_computer_s1_token_url,
            )
            token = token_payload["token"]
            errors = []
            for feature in candidates:
                try:
                    stats = self._measure(feature, request.boundary_geojson, token)
                    if stats["valid_pixels"] > 0:
                        observed = datetime.fromisoformat(
                            feature["properties"]["datetime"].replace("Z", "+00:00")
                        )
                        return SarFallbackResult(
                            field_id=request.field_id, processed_at=self.clock(), status="accepted",
                            scene_id=feature["id"], scene_date=observed.date(),
                            orbit_state=feature["properties"].get("sat:orbit_state"),
                            valid_pixels=stats["valid_pixels"],
                            vv_db_mean=stats["vv_db_mean"], vh_db_mean=stats["vh_db_mean"],
                            vv_minus_vh_db_mean=stats["ratio_db_mean"],
                            warnings=[
                                "SAR is cloud-independent evidence; it does not replace optical vegetation indices."
                            ],
                        )
                except Exception as exc:
                    errors.append(f"{feature['id']}: {exc}")
            return SarFallbackResult(
                field_id=request.field_id, processed_at=self.clock(), status="processing_error",
                warnings=errors or ["All SAR candidates had zero valid pixels."],
            )
        except Exception as exc:
            return SarFallbackResult(
                field_id=request.field_id, processed_at=self.clock(), status="processing_error",
                warnings=[str(exc)],
            )

    @staticmethod
    def _measure(feature, geometry_wgs84, token):
        import rasterio
        from rasterio.mask import mask
        from rasterio.warp import transform_geom

        arrays = {}
        shared_mask = None
        for polarization in ("vv", "vh"):
            href = feature["assets"][polarization]["href"]
            signed = f"{href}?{token}"
            with rasterio.open(signed) as source:
                geometry = transform_geom("EPSG:4326", source.crs, geometry_wgs84, precision=3)
                data, _ = mask(source, [geometry], crop=True, filled=False)
            band = data[0]
            valid = (~np.ma.getmaskarray(band)) & np.isfinite(band.data) & (band.data > 0)
            arrays[polarization] = band.data.astype("float64")
            shared_mask = valid if shared_mask is None else shared_mask & valid
        count = int(shared_mask.sum())
        if count == 0:
            return {"valid_pixels": 0}
        vv_db = 10 * np.log10(arrays["vv"][shared_mask])
        vh_db = 10 * np.log10(arrays["vh"][shared_mask])
        return {
            "valid_pixels": count,
            "vv_db_mean": round(float(np.mean(vv_db)), 6),
            "vh_db_mean": round(float(np.mean(vh_db)), 6),
            "ratio_db_mean": round(float(np.mean(vv_db - vh_db)), 6),
        }

    def close(self):
        if self._owns_http:
            self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
