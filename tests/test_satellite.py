from datetime import date

from satellite_x.acquisition.satellite import SatelliteClient, field_bbox
from satellite_x.config import Settings
from satellite_x.errors import ExternalServiceError
from satellite_x.models import FarmInput


class SequenceHttp:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def post_json(self, service, url, *, payload):
        self.calls.append((service, payload["datetime"]))
        item = next(self.responses)
        if isinstance(item, Exception):
            raise item
        return item


def farm(**updates):
    raw = {
        "field_id": "AP_F001",
        "latitude": 16.3067,
        "longitude": 80.4365,
        "crop_type": "chilli",
        "sowing_date": "2024-01-01",
        "analysis_date": "2024-01-30",
        "scan_range_days": 30,
        "acres": 5,
    }
    raw.update(updates)
    return FarmInput.model_validate(raw)


def test_aws_selects_lowest_cloud_complete_scene(load_fixture):
    http = SequenceHttp([load_fixture("aws_stac_multiple.json")])
    result = SatelliteClient(http, Settings()).acquire(farm())
    assert result.scene.scene_id == "S2A_GOLDEN_20240125_L2A"
    assert result.scene.cloud_cover_pct == 5.0
    assert set(result.scene.assets) == {"B02", "B03", "B04", "B05", "B08", "B11", "SCL"}
    assert result.scene.assets["B04"].scale == 0.0001
    assert result.scene.assets["B04"].offset == -0.1
    assert result.scene.assets["B04"].nodata == 0
    assert result.fallback_used is False
    assert result.expanded_date_range is False


def test_empty_aws_expands_30_days_before_cdse(load_fixture):
    http = SequenceHttp([{"features": []}, load_fixture("aws_stac.json")])
    result = SatelliteClient(http, Settings(expand_days=30)).acquire(farm())
    assert result.expanded_date_range is True
    assert [attempt.outcome for attempt in result.attempts] == ["empty", "success"]
    assert http.calls[1][0] == "aws_earth_search"
    assert http.calls[1][1].startswith("2023-12-02")


def test_aws_error_uses_cdse_mapping():
    cdse_assets = {}
    for key in ["B02_10m", "B03_10m", "B04_10m", "B05_20m", "B08_10m", "B11_20m", "SCL_20m"]:
        cdse_assets[key] = {"href": f"s3://eodata/{key}.jp2", "type": "image/jp2"}
    cdse = {
        "features": [{
            "id": "CDSE_SCENE",
            "bbox": [80, 16, 81, 17],
            "properties": {"datetime": "2024-01-20T00:00:00Z", "eo:cloud_cover": 8},
            "assets": cdse_assets,
        }]
    }
    http = SequenceHttp([ExternalServiceError("aws", "down"), cdse])
    result = SatelliteClient(http, Settings()).acquire(farm())
    assert result.fallback_used is True
    assert result.scene.provider == "copernicus_cdse"
    assert all(asset.requires_authentication for asset in result.scene.assets.values())


def test_acreage_bbox_is_centered_and_nonzero():
    box = field_bbox(farm())
    assert box[0] < 80.4365 < box[2]
    assert box[1] < 16.3067 < box[3]


def test_polygon_bbox_is_exact():
    polygon = {
        "type": "Polygon",
        "coordinates": [[[80.1, 16.1], [80.3, 16.1], [80.3, 16.4], [80.1, 16.1]]],
    }
    assert field_bbox(farm(boundary_geojson=polygon)) == [80.1, 16.1, 80.3, 16.4]
