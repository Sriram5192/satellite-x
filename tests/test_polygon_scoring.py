from datetime import datetime

from satellite_x.config import Settings
from satellite_x.polygon.ftw import RawFtwRecord
from satellite_x.polygon.models import PolygonRecoveryInput
from satellite_x.polygon.scoring import score_candidates


def request(acres=1.746115):
    return PolygonRecoveryInput(
        field_id="AP_TEST", latitude=16.1895796725143, longitude=80.3434336669471,
        acres=acres, location_consent=True, country_code="IN", subdivision_code="AP",
    )


def records(load_fixture):
    return [
        RawFtwRecord(
            record_id=item["record_id"],
            observed_at=datetime.fromisoformat(item["observed_at"]),
            year=item["year"],
            confidence=item["confidence"],
            area_m2=item["area_m2"],
            perimeter_m=item["perimeter_m"],
            geometry_geojson=item["geometry_geojson"],
        )
        for item in load_fixture("ftw_polygon_records.json")
    ]


def test_transparent_score_ranks_matching_2025_polygon_first(load_fixture):
    candidates = score_candidates(records(load_fixture), request(), Settings())
    assert candidates[0].candidate_id.startswith("ftw-IN-AP-1537149-2025-")
    assert candidates[0].quality == "HIGH"
    assert candidates[0].contains_input_point is True
    assert candidates[0].score_pct > 99
    assert candidates[0].legal_boundary is False


def test_large_acreage_mismatch_filters_all_candidates(load_fixture):
    assert score_candidates(records(load_fixture), request(acres=100), Settings()) == []
