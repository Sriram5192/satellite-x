from datetime import datetime, timezone
from pathlib import Path

from satellite_x.preprocessing.models import PreprocessingResult, SarFallbackResult
from satellite_x.resilience import ResilienceInput, ResilienceService


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


def test_accepted_optical_keeps_sar_ancillary_only():
    optical = PreprocessingResult.model_validate_json(Path("outputs/preprocessing_crop_field_result.json").read_text())
    sar = SarFallbackResult.model_validate_json(Path("outputs/sar_fallback_crop_field_result.json").read_text())
    result = ResilienceService().run(ResilienceInput(field_id=sar.field_id, optical=optical, sar=sar))
    assert result.status == "OPTICAL_PRIMARY_SAR_ANCILLARY"
    assert result.optical_indices_available and result.diagnosis_allowed


def test_sar_only_path_never_fabricates_indices_or_diagnosis():
    optical = PreprocessingResult.model_validate_json(Path("outputs/preprocessing_crop_field_result.json").read_text()).model_copy(
        update={"status": "no_acceptable_scene", "selected_scene": None, "selected_quality": None, "urban_gate": None}
    )
    sar = SarFallbackResult.model_validate_json(Path("outputs/sar_fallback_crop_field_result.json").read_text())
    result = ResilienceService().run(ResilienceInput(field_id=sar.field_id, optical=optical, sar=sar))
    assert result.status == "SAR_ONLY_UNRESOLVED"
    assert not result.optical_indices_available
    assert not result.optical_analytics_allowed
    assert not result.diagnosis_allowed


def test_sar_cannot_override_urban_rejection():
    optical = PreprocessingResult.model_validate_json(Path("outputs/preprocessing_crop_field_result.json").read_text()).model_copy(update={"status": "urban_rejected"})
    sar = SarFallbackResult.model_validate_json(Path("outputs/sar_fallback_crop_field_result.json").read_text())
    result = ResilienceService().run(ResilienceInput(field_id=sar.field_id, optical=optical, sar=sar))
    assert result.status == "LOCATION_OR_URBAN_REJECTED"
    assert not result.diagnosis_allowed
