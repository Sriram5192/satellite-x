import json
from pathlib import Path

import pytest

from satellite_x.config import Settings
from satellite_x.polygon.models import PolygonRecoveryInput
from satellite_x.polygon.service import PolygonRecoveryService
from satellite_x.preprocessing.models import PreprocessingInput
from satellite_x.preprocessing.service import PreprocessingService


@pytest.mark.live
def test_live_road_reject_and_open_ftw_recovery(tmp_path):
    settings = Settings(
        cache_dir=tmp_path, connect_timeout_s=5, read_timeout_s=20, retries=0
    )
    road = PolygonRecoveryInput.model_validate_json(
        Path("examples/polygon_road_request.json").read_text()
    )
    rural = PolygonRecoveryInput.model_validate_json(
        Path("examples/polygon_open_field_request.json").read_text()
    )
    with PolygonRecoveryService(settings) as service:
        blocked = service.recover(road)
        recovered = service.recover(rural)
        confirmed = service.confirm_candidate(
            recovered, recovered.selected_candidate_id
        )

    assert blocked.status == "rejected_location"
    assert blocked.reason_codes == ["POINT_ON_OR_NEXT_TO_ROAD"]
    assert recovered.status == "candidates_found"
    assert recovered.selected_candidate_id.startswith(
        "ftw-IN-AP-1537149-2025-"
    )
    assert recovered.candidates[0].score_pct > 99
    assert recovered.candidates[0].area_difference_pct < 0.1
    assert confirmed.legal_boundary is False
    assert confirmed.validation.valid is True


@pytest.mark.live
def test_live_set2_selects_spectrally_usable_expanded_scene(tmp_path):
    settings = Settings(
        cache_dir=tmp_path, connect_timeout_s=5, read_timeout_s=20, retries=0
    )
    request = PreprocessingInput.model_validate_json(
        Path("examples/preprocessing_crop_field_request.json").read_text()
    )
    with PreprocessingService(settings) as service:
        result = service.run(request)

    assert result.status == "accepted"
    assert result.selected_scene.scene_id == "S2B_44PMC_20260628_0_L2A"
    assert result.selected_quality.quality == "MEDIUM"
    assert result.selected_quality.field_valid_pct == 100
    assert result.urban_gate.spectral_valid_pct == 100
    assert result.urban_gate.urban_rejected is False
    assert result.expanded_search_used is True
