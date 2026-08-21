"""Experimental relative-NDVI management zones; no agronomic rates are inferred."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

import numpy as np
from pydantic import Field

from ..models import StrictModel, utc_now
from ..preprocessing.models import PreprocessingResult

VALID_SCL = {4, 5, 6, 7}


class ManagementZoneFeature(StrictModel):
    zone: Literal["low_relative_ndvi", "medium_relative_ndvi", "high_relative_ndvi"]
    pixel_count: int = Field(gt=0)
    approximate_acres: float = Field(gt=0)
    ndvi_mean: float
    geometry_geojson: dict


class ManagementZoneResult(StrictModel):
    field_id: str
    scene_id: str
    generated_at: datetime
    status: Literal["experimental_requires_approval"] = "experimental_requires_approval"
    zoning_basis: Literal["within_field_ndvi_tertiles"] = "within_field_ndvi_tertiles"
    thresholds: dict[str, float]
    zones: list[ManagementZoneFeature]
    application_rates: None = None
    human_approval_required: Literal[True] = True
    warnings: list[str]


class ManagementZoneService:
    def run(self, preprocessing: PreprocessingResult) -> ManagementZoneResult:
        if preprocessing.status != "accepted" or preprocessing.selected_scene is None:
            raise ValueError("accepted preprocessing with selected scene is required")
        try:
            import rasterio
            from rasterio.features import shapes
            from rasterio.mask import mask
            from rasterio.warp import Resampling, reproject, transform_geom
        except ImportError as exc:
            raise RuntimeError("rasterio is required") from exc

        scene = preprocessing.selected_scene
        geometry_wgs84 = preprocessing.request.boundary_geojson
        with rasterio.open(scene.assets["SCL"].href) as scl_source:
            geometry = transform_geom("EPSG:4326", scl_source.crs, geometry_wgs84, precision=3)
            scl_masked, target_transform = mask(scl_source, [geometry], crop=True, filled=False)
            target_crs = scl_source.crs
        scl = scl_masked[0]
        inside = ~np.ma.getmaskarray(scl)
        valid = inside & np.isin(scl.data, list(VALID_SCL))
        bands = {}
        for band in ("B04", "B08"):
            asset = scene.assets[band]
            destination = np.full(scl.shape, np.nan, dtype="float32")
            with rasterio.open(asset.href) as source:
                reproject(
                    source=rasterio.band(source, 1), destination=destination,
                    src_transform=source.transform, src_crs=source.crs,
                    dst_transform=target_transform, dst_crs=target_crs,
                    dst_nodata=np.nan, resampling=Resampling.bilinear,
                )
            bands[band] = destination * float(asset.scale) + float(asset.offset)
            valid &= np.isfinite(bands[band]) & (bands[band] >= 0) & (bands[band] <= 1.2)
        ndvi = (bands["B08"] - bands["B04"]) / (bands["B08"] + bands["B04"] + 1e-10)
        valid &= np.isfinite(ndvi) & (ndvi >= -1) & (ndvi <= 1)
        values = ndvi[valid]
        if values.size < 3:
            raise ValueError("at least three valid NDVI pixels are required")
        low, high = [float(value) for value in np.quantile(values, [1 / 3, 2 / 3])]
        classes = np.zeros(scl.shape, dtype="uint8")
        classes[valid & (ndvi <= low)] = 1
        classes[valid & (ndvi > low) & (ndvi <= high)] = 2
        classes[valid & (ndvi > high)] = 3
        names = {1: "low_relative_ndvi", 2: "medium_relative_ndvi", 3: "high_relative_ndvi"}
        pixel_acres = abs(target_transform.a * target_transform.e) / 4046.8564224
        features = []
        for class_id, name in names.items():
            class_mask = classes == class_id
            count = int(class_mask.sum())
            if not count:
                continue
            class_geometry = [item for item, value in shapes(classes, mask=class_mask, transform=target_transform) if int(value) == class_id]
            if len(class_geometry) == 1:
                combined = class_geometry[0]
            else:
                polygons = []
                for item in class_geometry:
                    if item["type"] == "Polygon":
                        polygons.append(item["coordinates"])
                    else:
                        polygons.extend(item["coordinates"])
                combined = {"type": "MultiPolygon", "coordinates": polygons}
            geometry_4326 = transform_geom(target_crs, "EPSG:4326", combined, precision=7)
            features.append(ManagementZoneFeature(
                zone=name,
                pixel_count=count,
                approximate_acres=round(count * pixel_acres, 4),
                ndvi_mean=round(float(np.mean(ndvi[class_mask])), 6),
                geometry_geojson=geometry_4326,
            ))
        return ManagementZoneResult(
            field_id=preprocessing.request.field_id,
            scene_id=scene.scene_id,
            generated_at=utc_now(),
            thresholds={"lower_tertile": round(low, 6), "upper_tertile": round(high, 6)},
            zones=features,
            warnings=[
                "Zones are within-field relative NDVI classes, not fertilizer or spray prescriptions.",
                "An agronomist and equipment-specific field trial are required before application.",
            ],
        )
