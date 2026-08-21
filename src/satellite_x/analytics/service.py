"""Set 3 raster extraction, indices, phenology and water balance."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import numpy as np

from ..acquisition.weather import WeatherClient
from ..models import utc_now
from .errors import AnalyticsError
from .formulas import compute_indices
from .models import (
    AnalyticsInput,
    AnalyticsResult,
    IndexStatistics,
    WaterBalanceState,
)
from .phenology import phenology_state

VALID_SCL = {4, 5, 6, 7}


class AnalyticsService:
    def __init__(self, clock: Callable[[], datetime] = utc_now):
        self.clock = clock

    def run(self, request: AnalyticsInput) -> AnalyticsResult:
        preprocessing = request.preprocessing
        scene = preprocessing.selected_scene
        if scene is None:
            raise AnalyticsError("accepted preprocessing result has no selected scene")
        bands, base_valid, inside_count = self._load_bands(scene, request)
        count = int(base_valid.sum())
        if count == 0:
            raise AnalyticsError("zero all-band calibrated spectral pixels")
        arrays = compute_indices(bands)
        indices: dict[str, IndexStatistics] = {}
        for name, array in arrays.items():
            valid = base_valid & np.isfinite(array)
            if name in {"ndvi", "ndre", "ndmi", "ndwi", "gndvi"}:
                valid &= (array >= -1.0) & (array <= 1.0)
            elif name == "savi":
                valid &= (array >= -1.5) & (array <= 1.5)
            else:
                valid &= (array >= -2.0) & (array <= 2.0)
            values = array[valid]
            if values.size == 0:
                raise AnalyticsError(f"zero valid values for {name}")
            indices[name] = IndexStatistics(
                mean=round(float(np.mean(values)), 6),
                median=round(float(np.median(values)), 6),
                p10=round(float(np.percentile(values, 10)), 6),
                p90=round(float(np.percentile(values, 90)), 6),
                minimum=round(float(np.min(values)), 6),
                maximum=round(float(np.max(values)), 6),
                valid_pixels=int(values.size),
            )

        scene_date = scene.acquired_at.date()
        das = (scene_date - request.sowing_date).days
        phenology = phenology_state(
            request.crop_type, das, indices["ndvi"].mean
        )
        summary = WeatherClient.summarize(request.weather.history)
        if summary != request.weather.summary:
            raise AnalyticsError("weather summary does not match the supplied daily history")
        weather_dates = sorted(item.observation_date for item in request.weather.history)
        water_balance = round(summary.rain_15d_mm - summary.et0_15d_mm, 3)
        water = WaterBalanceState(
            reference_start_date=weather_dates[-15],
            reference_end_date=weather_dates[-1],
            scene_alignment_days=0,
            rain_15d_mm=summary.rain_15d_mm,
            et0_15d_mm=summary.et0_15d_mm,
            water_balance_15d_mm=water_balance,
            humidity_mean_5d_pct=summary.humidity_mean_5d_pct,
            deficit_flag=water_balance < -30.0,
        )
        warnings: list[str] = []
        if request.soil.source != "soilgrids_live":
            warnings.append(
                f"Soil source is {request.soil.source}; it is not treated as verified live soil."
            )
        if request.weather.fallback_used:
            warnings.append("Weather is cached fallback data.")
        if request.sowing_date_quality != "known":
            warnings.append(
                f"Sowing date quality is {request.sowing_date_quality}; phenology confidence must be penalized."
            )
        return AnalyticsResult(
            field_id=request.field_id,
            computed_at=self.clock(),
            scene_id=scene.scene_id,
            scene_date=scene_date,
            spectral_valid_pixels=count,
            spectral_valid_pct=round(100 * count / inside_count, 3),
            indices=indices,
            phenology=phenology,
            water_balance=water,
            soil=request.soil,
            data_warnings=warnings,
        )

    def _load_bands(self, scene, request):
        try:
            import rasterio
            from rasterio.mask import mask
            from rasterio.warp import Resampling, reproject, transform_geom
        except ImportError as exc:
            raise AnalyticsError("rasterio and numpy are required") from exc

        geometry_wgs84 = request.preprocessing.request.boundary_geojson
        try:
            with rasterio.open(scene.assets["SCL"].href) as scl_source:
                geometry = transform_geom(
                    "EPSG:4326", scl_source.crs, geometry_wgs84, precision=3
                )
                scl_masked, target_transform = mask(
                    scl_source, [geometry], crop=True, filled=False
                )
                target_crs = scl_source.crs
            scl = scl_masked[0]
            inside = ~np.ma.getmaskarray(scl)
            base_valid = inside & np.isin(scl.data, list(VALID_SCL))
            shape = scl.shape
            bands: dict[str, np.ndarray] = {}
            for band in ("B02", "B03", "B04", "B05", "B08", "B11"):
                asset = scene.assets[band]
                if asset.scale is None or asset.offset is None:
                    raise AnalyticsError(f"{band} has no calibration metadata")
                destination = np.full(shape, np.nan, dtype="float32")
                with rasterio.open(asset.href) as source:
                    reproject(
                        source=rasterio.band(source, 1),
                        destination=destination,
                        src_transform=source.transform,
                        src_crs=source.crs,
                        src_nodata=source.nodata,
                        dst_transform=target_transform,
                        dst_crs=target_crs,
                        dst_nodata=np.nan,
                        resampling=Resampling.bilinear,
                    )
                reflectance = destination * asset.scale + asset.offset
                bands[band] = reflectance
                base_valid &= (
                    np.isfinite(reflectance)
                    & (reflectance >= 0)
                    & (reflectance <= 1.2)
                )
            return bands, base_valid, int(inside.sum())
        except AnalyticsError:
            raise
        except Exception as exc:
            raise AnalyticsError(f"spectral raster extraction failed: {exc}") from exc
