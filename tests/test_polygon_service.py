import json
from datetime import datetime, timezone
from pathlib import Path

from satellite_x.config import Settings
from satellite_x.polygon.ftw import RawFtwRecord
from satellite_x.polygon.models import LocationEvidence, PolygonRecoveryInput
from satellite_x.polygon.service import PolygonRecoveryService


GOLDEN = Path(__file__).parent / "golden" / "polygon_recovery_expected.json"


class StaticLocation:
    def __init__(self, evidence):
        self.evidence = evidence

    def check(self, request):
        return self.evidence


class StaticFtw:
    def __init__(self, records):
        self.records = records
        self.calls = 0

    def query(self, request):
        self.calls += 1
        return self.records


class NoopHttp:
    def close(self):
        pass


def raw_records(load_fixture):
    return [
        RawFtwRecord(
            record_id=item["record_id"],
            observed_at=datetime.fromisoformat(item["observed_at"]),
            year=item["year"], confidence=item["confidence"],
            area_m2=item["area_m2"], perimeter_m=item["perimeter_m"],
            geometry_geojson=item["geometry_geojson"],
        )
        for item in load_fixture("ftw_polygon_records.json")
    ]


def rural_request():
    return PolygonRecoveryInput(
        field_id="AP_GNT_FTW_OPEN_TEST", latitude=16.1895796725143,
        longitude=80.3434336669471, acres=1.746115, location_consent=True,
        country_code="IN", subdivision_code=None, search_radius_m=300,
        gps_tolerance_m=30,
    )


def test_blocked_location_stops_before_ftw_query(tmp_path):
    location = LocationEvidence(
        source="nominatim_live", category="highway", feature_type="primary",
        matched_latitude=16.3066111, matched_longitude=80.4365517,
        feature_distance_m=11.321, country_code="IN", subdivision_code="AP",
        blocking=True, reason_code="POINT_ON_OR_NEXT_TO_ROAD",
    )
    repository = StaticFtw([])
    service = PolygonRecoveryService(
        Settings(cache_dir=tmp_path), http=NoopHttp(),
        location_client=StaticLocation(location), ftw_repository=repository,
        clock=lambda: datetime(2026, 8, 17, 6, 0, tzinfo=timezone.utc),
    )
    request = rural_request().model_copy(update={"latitude": 16.3067, "longitude": 80.4365})
    result = service.recover(request)
    assert result.status == "rejected_location"
    assert repository.calls == 0


def test_full_recovery_matches_golden_and_confirms(load_fixture, tmp_path):
    location = LocationEvidence(
        source="nominatim_live", category="highway", feature_type="primary",
        name="Guntur - Parchuru Road", feature_distance_m=122.978,
        country_code="IN", subdivision_code="AP", blocking=False,
        reason_code="NO_DISTANCE_BASED_LOCATION_BLOCK",
    )
    service = PolygonRecoveryService(
        Settings(cache_dir=tmp_path), http=NoopHttp(),
        location_client=StaticLocation(location),
        ftw_repository=StaticFtw(raw_records(load_fixture)),
        clock=lambda: datetime(2026, 8, 17, 6, 0, tzinfo=timezone.utc),
    )
    result = service.recover(rural_request())
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert result.model_dump(mode="json") == expected
    confirmation = service.confirm_candidate(result, result.selected_candidate_id)
    assert confirmation.user_confirmed is True
    assert confirmation.legal_boundary is False
    assert confirmation.validation.valid is True
    assert confirmation.source_candidate_id.startswith(
        "ftw-IN-AP-1537149-2025-"
    )

    uploaded_fmb = service.confirm_uploaded_or_drawn(
        result.request,
        result.candidates[0].geometry_geojson,
        source="official_fmb",
    )
    assert uploaded_fmb.boundary_source == "official_fmb"
    assert uploaded_fmb.legal_boundary is False
    assert uploaded_fmb.provenance["verification_status"] == "unverified_document_upload"
