"""SCL field-quality measurement and calibrated NDBI/NDVI urban gate."""

from __future__ import annotations

import warnings
from datetime import date

import numpy as np

from ..models import SatelliteScene
from .errors import RasterQualityError
from .models import PreprocessingInput, SceneFieldQuality, UrbanGateResult

VALID_SCL = {4, 5, 6, 7}


def classify_quality(valid_pct: float, cloud_pct: float) -> str:
    if valid_pct >= 90 and cloud_pct < 10:
        return "HIGH"
    if valid_pct >= 60 and cloud_pct <= 40:
        return "MEDIUM"
    return "LOW"


class RasterQualityEvaluator:
    def evaluate(
        self,
        scene: SatelliteScene,
        request: PreprocessingInput,
        original_start: date,
    ) -> SceneFieldQuality:
        try:
            import rasterio
            from rasterio.errors import NotGeoreferencedWarning
            from rasterio.mask import mask
            from rasterio.warp import transform_geom
        except ImportError as exc:
            raise RasterQualityError("rasterio and numpy are required") from exc
        warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
        try:
            with rasterio.open(scene.assets["SCL"].href) as source:
                geometry = transform_geom(
                    "EPSG:4326", source.crs, request.boundary_geojson, precision=3
                )
                masked, _ = mask(
                    source,
                    [geometry],
                    crop=True,
                    all_touched=False,
                    filled=False,
                )
            scl = masked[0]
            inside = ~np.ma.getmaskarray(scl)
            values = scl.data[inside]
        except Exception as exc:
            raise RasterQualityError(
                f"failed to read SCL for {scene.scene_id}: {exc}"
            ) from exc
        total = int(values.size)
        if total == 0:
            raise RasterQualityError(f"field has zero SCL pixels in {scene.scene_id}")
        valid = int(np.isin(values, list(VALID_SCL)).sum())
        valid_pct = 100.0 * valid / total
        counts = {
            str(code): int((values == code).sum())
            for code in range(12)
            if (values == code).any()
        }
        quality = classify_quality(valid_pct, scene.cloud_cover_pct)
        reasons: list[str] = []
        if valid_pct < 60:
            reasons.append("FIELD_VALID_PIXELS_BELOW_60_PERCENT")
        if scene.cloud_cover_pct > 40:
            reasons.append("SCENE_CLOUD_ABOVE_40_PERCENT")
        return SceneFieldQuality(
            scene_id=scene.scene_id,
            acquired_at=scene.acquired_at,
            scene_cloud_pct=scene.cloud_cover_pct,
            in_original_range=scene.acquired_at.date() >= original_start,
            total_field_pixels=total,
            valid_field_pixels=valid,
            field_valid_pct=round(valid_pct, 3),
            scl_counts=counts,
            quality=quality,
            rejection_reasons=reasons,
        )

    def urban_gate(
        self, scene: SatelliteScene, request: PreprocessingInput
    ) -> UrbanGateResult:
        try:
            import rasterio
            from rasterio.mask import mask
            from rasterio.warp import Resampling, reproject, transform_geom
        except ImportError as exc:
            raise RasterQualityError("rasterio and numpy are required") from exc

        try:
            with rasterio.open(scene.assets["SCL"].href) as scl_source:
                geometry = transform_geom(
                    "EPSG:4326", scl_source.crs, request.boundary_geojson, precision=3
                )
                scl_masked, target_transform = mask(
                    scl_source,
                    [geometry],
                    crop=True,
                    all_touched=False,
                    filled=False,
                )
                target_crs = scl_source.crs
            scl = scl_masked[0]
            inside = ~np.ma.getmaskarray(scl)
            scl_valid = inside & np.isin(scl.data, list(VALID_SCL))
            shape = scl.shape

            reflectance: dict[str, np.ndarray] = {}
            # Set 2 must validate every calibrated band consumed by Set 3, not only
            # the three bands used by the urban heuristic.
            for band in ("B02", "B03", "B04", "B05", "B08", "B11"):
                asset = scene.assets[band]
                if asset.scale is None or asset.offset is None:
                    raise RasterQualityError(
                        f"{band} is missing radiometric scale/offset"
                    )
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
                reflectance[band] = (
                    destination * float(asset.scale) + float(asset.offset)
                )
        except RasterQualityError:
            raise
        except Exception as exc:
            raise RasterQualityError(
                f"urban gate raster processing failed for {scene.scene_id}: {exc}"
            ) from exc

        red = reflectance["B04"]
        nir = reflectance["B08"]
        swir = reflectance["B11"]
        physical = np.ones(shape, dtype=bool)
        for values in reflectance.values():
            physical &= np.isfinite(values) & (values >= 0) & (values <= 1.2)
        denominators = (np.abs(nir + red) > 1e-6) & (
            np.abs(swir + nir) > 1e-6
        )
        spectral_valid = scl_valid & physical & denominators
        inside_count = int(inside.sum())
        valid_count = int(spectral_valid.sum())
        valid_pct = 100.0 * valid_count / inside_count if inside_count else 0.0
        if valid_count == 0:
            return UrbanGateResult(
                spectral_valid_pixels=0,
                spectral_valid_pct=0,
                mean_ndvi=None,
                mean_ndbi=None,
                built_pixel_pct=None,
                urban_rejected=False,
                condition="INSUFFICIENT_SPECTRAL_PIXELS",
            )

        ndvi = (nir - red) / (nir + red + 1e-10)
        ndbi = (swir - nir) / (swir + nir + 1e-10)
        mean_ndvi = float(np.mean(ndvi[spectral_valid]))
        mean_ndbi = float(np.mean(ndbi[spectral_valid]))
        built = spectral_valid & (ndbi > 0.08) & (ndvi < 0.20)
        built_pct = 100.0 * int(built.sum()) / valid_count
        rejected = mean_ndbi > 0.08 and mean_ndvi < 0.20
        return UrbanGateResult(
            spectral_valid_pixels=valid_count,
            spectral_valid_pct=round(valid_pct, 3),
            mean_ndvi=round(mean_ndvi, 6),
            mean_ndbi=round(mean_ndbi, 6),
            built_pixel_pct=round(built_pct, 3),
            urban_rejected=rejected,
            condition=(
                "NDBI_MEAN_GT_0.08_AND_NDVI_MEAN_LT_0.20"
                if rejected
                else "URBAN_MEAN_CONDITION_NOT_MET"
            ),
        )
