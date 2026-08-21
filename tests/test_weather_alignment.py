from pathlib import Path

import pytest

from satellite_x.analytics.models import AnalyticsInput
from satellite_x.models import RawDataContainer
from satellite_x.preprocessing.models import PreprocessingResult


def build(raw_path: str):
    preprocessing = PreprocessingResult.model_validate_json(
        Path("outputs/preprocessing_crop_field_result.json").read_text()
    )
    raw = RawDataContainer.model_validate_json(Path(raw_path).read_text())
    return AnalyticsInput(
        field_id=raw.field.field_id,
        crop_type=raw.field.crop_type,
        sowing_date=raw.field.sowing_date,
        preprocessing=preprocessing,
        weather=raw.weather,
        soil=raw.soil,
    )


def test_weather_must_end_on_optical_scene_date():
    with pytest.raises(ValueError, match="weather history must end on selected scene date"):
        build("outputs/set1_crop_field_live.json")


def test_scene_aligned_weather_is_accepted():
    request = build("outputs/set1_crop_field_scene_aligned.json")
    assert request.weather.history[-1].observation_date == request.preprocessing.selected_scene.acquired_at.date()


def test_tampered_weather_summary_is_rejected():
    preprocessing = PreprocessingResult.model_validate_json(
        Path("outputs/preprocessing_crop_field_result.json").read_text()
    )
    raw = RawDataContainer.model_validate_json(
        Path("outputs/set1_crop_field_scene_aligned.json").read_text()
    )
    altered_summary = raw.weather.summary.model_copy(
        update={"rain_15d_mm": raw.weather.summary.rain_15d_mm + 1}
    )
    altered_weather = raw.weather.model_copy(update={"summary": altered_summary})
    with pytest.raises(ValueError, match="weather summary does not match"):
        AnalyticsInput(
            field_id=raw.field.field_id,
            crop_type=raw.field.crop_type,
            sowing_date=raw.field.sowing_date,
            preprocessing=preprocessing,
            weather=altered_weather,
            soil=raw.soil,
        )
