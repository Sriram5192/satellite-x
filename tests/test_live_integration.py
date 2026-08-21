from datetime import date

import pytest

from satellite_x.acquisition.pipeline import AcquisitionPipeline
from satellite_x.config import Settings
from satellite_x.models import FarmInput


@pytest.mark.live
def test_live_guntur_set1_contract(tmp_path):
    settings = Settings(
        cache_dir=tmp_path,
        connect_timeout_s=5,
        read_timeout_s=12,
        retries=0,
        max_cloud_pct=40,
    )
    field = FarmInput(
        field_id="AP_GNT_LIVE",
        latitude=16.3067,
        longitude=80.4365,
        crop_type="chilli",
        sowing_date=date(2026, 6, 15),
        analysis_date=date(2026, 8, 17),
        scan_range_days=30,
        acres=5,
    )
    with AcquisitionPipeline(settings) as pipeline:
        result = pipeline.run(field)

    assert result.satellite.scene.scene_id == "S2C_44QMD_20260802_0_L2A"
    assert set(result.satellite.scene.assets) == {
        "B02", "B03", "B04", "B05", "B08", "B11", "SCL"
    }
    for band in ("B02", "B03", "B04", "B05", "B08", "B11"):
        assert result.satellite.scene.assets[band].scale == 0.0001
        assert result.satellite.scene.assets[band].offset == -0.1
    assert len(result.weather.history) == 30
    assert result.weather.summary.days_available_15d == 15
    assert result.weather.summary.rain_15d_mm == round(
        sum(day.precipitation_mm for day in result.weather.history[-15:]), 3
    )
    assert result.soil.source in {
        "soilgrids_live", "cache", "regional_ag_zone_baseline"
    }
    assert result.streams[3].state == "not_supplied"
