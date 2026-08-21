from pathlib import Path

import pytest

from satellite_x.analytics.models import AnalyticsInput
from satellite_x.analytics.service import AnalyticsService
from satellite_x.models import RawDataContainer
from satellite_x.preprocessing.models import PreprocessingResult, SarFallbackInput
from satellite_x.preprocessing.sar import SarFallbackService
from satellite_x.recommendations.management_zones import ManagementZoneService


@pytest.mark.live
def test_live_set3_extracts_all_indices_from_selected_cogs():
    preprocessing = PreprocessingResult.model_validate_json(
        Path("outputs/preprocessing_crop_field_result.json").read_text()
    )
    raw = RawDataContainer.model_validate_json(
        Path("outputs/set1_crop_field_scene_aligned.json").read_text()
    )
    result = AnalyticsService().run(
        AnalyticsInput(
            field_id=raw.field.field_id, crop_type=raw.field.crop_type,
            sowing_date=raw.field.sowing_date, preprocessing=preprocessing,
            weather=raw.weather, soil=raw.soil,
        )
    )
    assert set(result.indices) == {"ndvi", "evi", "savi", "ndre", "ndmi", "ndwi", "gndvi"}
    assert result.indices["ndvi"].mean == 0.324206
    assert result.spectral_valid_pct == 100
    assert result.phenology.stage_name == "Transplant"
    assert result.water_balance.reference_end_date == result.scene_date
    assert result.water_balance.scene_alignment_days == 0
    assert result.water_balance.water_balance_15d_mm == -12.67
    assert result.water_balance.deficit_flag is False


@pytest.mark.live
def test_live_sentinel1_rtc_fallback_has_valid_dual_pol_pixels(tmp_path):
    request = SarFallbackInput.model_validate_json(
        Path("examples/sar_fallback_crop_field_request.json").read_text()
    )
    with SarFallbackService() as service:
        result = service.run(request)
    assert result.status == "accepted"
    assert result.valid_pixels > 0
    assert result.vv_db_mean is not None
    assert result.vh_db_mean is not None
    assert result.vv_minus_vh_db_mean is not None


@pytest.mark.live
def test_live_management_zones_have_no_automatic_application_rates():
    preprocessing = PreprocessingResult.model_validate_json(
        Path("outputs/preprocessing_crop_field_result.json").read_text()
    )
    result = ManagementZoneService().run(preprocessing)
    assert len(result.zones) == 3
    assert result.application_rates is None
    assert result.human_approval_required is True
