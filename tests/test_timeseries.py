from datetime import date, timedelta
import json
from pathlib import Path

from satellite_x.analytics.models import AnalyticsResult
from satellite_x.analytics.timeseries import TimeSeriesInput, TimeSeriesService


def test_crop_aware_multiscene_trend_uses_scene_dates_and_all_indices():
    base = AnalyticsResult.model_validate_json(Path("outputs/analytics_crop_field_result.json").read_text())
    rows = []
    for offset, delta in [(0, -0.08), (10, -0.03), (20, 0.0)]:
        indices = {
            key: value.model_copy(update={"mean": value.mean + (delta if key == "ndvi" else 0)})
            for key, value in base.indices.items()
        }
        rows.append(base.model_copy(update={"scene_id": f"S{offset}", "scene_date": base.scene_date + timedelta(days=offset), "indices": indices}))
    result = TimeSeriesService().run(TimeSeriesInput(field_id=base.field_id, observations=rows))
    assert result.quality == "usable"
    assert result.observation_count == 3
    assert set(result.index_trends) == {"ndvi", "evi", "savi", "ndre", "ndmi", "ndwi", "gndvi"}
    assert result.index_trends["ndvi"].direction == "increasing"
    assert result.index_trends["ndvi"].total_change == 0.08
