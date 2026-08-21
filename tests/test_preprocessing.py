import json
from datetime import date, datetime, timezone
from pathlib import Path

from satellite_x.config import Settings
from satellite_x.models import BandAsset, SatelliteScene
from satellite_x.preprocessing.catalog import geometry_bbox
from satellite_x.preprocessing.models import (
    PreprocessingInput,
    SceneFieldQuality,
    UrbanGateResult,
)
from satellite_x.preprocessing.quality import classify_quality
from satellite_x.preprocessing.service import PreprocessingService


GOLDEN = Path(__file__).parent / "golden" / "preprocessing_expected.json"


class NoopHttp:
    def close(self):
        pass


def scene(scene_id: str, acquired: str, cloud: float) -> SatelliteScene:
    assets = {}
    for band, resolution in {
        "B02": 10, "B03": 10, "B04": 10, "B05": 20,
        "B08": 10, "B11": 20, "SCL": 20,
    }.items():
        assets[band] = BandAsset(
            band_code=band, source_key=band.lower(),
            href=f"https://example.test/{scene_id}/{band}.tif",
            resolution_m=resolution, media_type="image/tiff",
            scale=None if band == "SCL" else 0.0001,
            offset=None if band == "SCL" else -0.1,
            nodata=0,
        )
    return SatelliteScene(
        scene_id=scene_id, provider="aws_earth_search",
        collection="sentinel-2-l2a",
        acquired_at=datetime.fromisoformat(acquired),
        cloud_cover_pct=cloud, bbox=[80, 16, 81, 17], assets=assets,
    )


ORIGINAL = scene("ORIGINAL_CLOUDY_FIELD", "2026-07-23T05:00:00+00:00", 12)
EXPANDED = scene("EXPANDED_CLEAN_FIELD", "2026-06-28T05:00:00+00:00", 25)


class FakeCatalog:
    def __init__(self):
        self.calls = []

    def list_scenes(self, request, start, end):
        self.calls.append((start, end))
        return [ORIGINAL] if start.month == 7 else [EXPANDED]


class FakeEvaluator:
    def __init__(self, urban_all=False):
        self.urban_all = urban_all

    def evaluate(self, selected, request, original_start):
        is_original = selected.scene_id.startswith("ORIGINAL")
        return SceneFieldQuality(
            scene_id=selected.scene_id,
            acquired_at=selected.acquired_at,
            scene_cloud_pct=selected.cloud_cover_pct,
            in_original_range=is_original,
            total_field_pixels=20,
            valid_field_pixels=17 if is_original else 20,
            field_valid_pct=85 if is_original else 100,
            scl_counts={"5": 17 if is_original else 20},
            quality="MEDIUM",
            rejection_reasons=[],
        )

    def urban_gate(self, selected, request):
        if self.urban_all:
            return UrbanGateResult(
                spectral_valid_pixels=20, spectral_valid_pct=100,
                mean_ndvi=0.10, mean_ndbi=0.20, built_pixel_pct=90,
                urban_rejected=True,
                condition="NDBI_MEAN_GT_0.08_AND_NDVI_MEAN_LT_0.20",
            )
        if selected.scene_id.startswith("ORIGINAL"):
            return UrbanGateResult(
                spectral_valid_pixels=1, spectral_valid_pct=5,
                mean_ndvi=0.1, mean_ndbi=0.1, built_pixel_pct=0,
                urban_rejected=False,
                condition="URBAN_MEAN_CONDITION_NOT_MET",
            )
        return UrbanGateResult(
            spectral_valid_pixels=20, spectral_valid_pct=100,
            mean_ndvi=0.45, mean_ndbi=0.03, built_pixel_pct=0,
            urban_rejected=False,
            condition="URBAN_MEAN_CONDITION_NOT_MET",
        )


def request(**updates):
    raw = {
        "field_id": "FIELD_1", "latitude": 16.1, "longitude": 80.5,
        "boundary_geojson": {
            "type": "Polygon",
            "coordinates": [[[80.49, 16.09], [80.51, 16.09],
                             [80.51, 16.11], [80.49, 16.11], [80.49, 16.09]]],
        },
        "analysis_date": "2026-08-17", "scan_range_days": 30,
        "expansion_days": 30, "location_blocking": False,
    }
    raw.update(updates)
    return PreprocessingInput.model_validate(raw)


def test_tuple_geometry_from_shapely_mapping_is_supported():
    geometry = {
        "type": "Polygon",
        "coordinates": (((80.0, 16.0), (81.0, 16.0), (81.0, 17.0), (80.0, 16.0)),),
    }
    assert geometry_bbox(geometry) == [80.0, 16.0, 81.0, 17.0]


def test_frozen_quality_matrix():
    assert classify_quality(95, 5) == "HIGH"
    assert classify_quality(80, 30) == "MEDIUM"
    assert classify_quality(95, 41) == "LOW"
    assert classify_quality(59.9, 5) == "LOW"


def test_location_block_stops_catalog(tmp_path):
    catalog = FakeCatalog()
    service = PreprocessingService(
        Settings(cache_dir=tmp_path), http=NoopHttp(), catalog=catalog,
        evaluator=FakeEvaluator(),
        clock=lambda: datetime(2026, 8, 17, 6, tzinfo=timezone.utc),
    )
    result = service.run(
        request(location_blocking=True, location_reason="POINT_ON_ROAD")
    )
    assert result.status == "rejected_location"
    assert catalog.calls == []


def test_low_spectral_original_expands_and_matches_golden(tmp_path):
    service = PreprocessingService(
        Settings(cache_dir=tmp_path), http=NoopHttp(), catalog=FakeCatalog(),
        evaluator=FakeEvaluator(),
        clock=lambda: datetime(2026, 8, 17, 6, tzinfo=timezone.utc),
    )
    result = service.run(request())
    expected = json.loads(GOLDEN.read_text())
    assert result.model_dump(mode="json") == expected
    assert result.status == "accepted"
    assert result.selected_scene.scene_id == "EXPANDED_CLEAN_FIELD"
    assert result.expanded_search_used is True


def test_absolute_spectral_pixel_floor_blocks_tiny_samples(tmp_path):
    service = PreprocessingService(
        Settings(cache_dir=tmp_path, spectral_min_valid_pixels=25),
        http=NoopHttp(), catalog=FakeCatalog(), evaluator=FakeEvaluator(),
        clock=lambda: datetime(2026, 8, 17, 6, tzinfo=timezone.utc),
    )
    result = service.run(request())
    assert result.status == "processing_error"
    assert any("absolute minimum 25" in warning for warning in result.warnings)


def test_all_spectrally_usable_candidates_urban_reject(tmp_path):
    service = PreprocessingService(
        Settings(cache_dir=tmp_path), http=NoopHttp(), catalog=FakeCatalog(),
        evaluator=FakeEvaluator(urban_all=True),
        clock=lambda: datetime(2026, 8, 17, 6, tzinfo=timezone.utc),
    )
    result = service.run(request())
    assert result.status == "urban_rejected"
    assert result.urban_gate.urban_rejected is True
