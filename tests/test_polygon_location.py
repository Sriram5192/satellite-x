from satellite_x.cache import JsonCache
from satellite_x.config import Settings
from satellite_x.polygon.location import LocationPreflightClient
from satellite_x.polygon.models import PolygonRecoveryInput


class PayloadHttp:
    def __init__(self, payload):
        self.payload = payload

    def get_json(self, service, url, *, params=None):
        assert service == "nominatim"
        return self.payload


def make_request(lat, lon, acres=5):
    return PolygonRecoveryInput(
        field_id="AP_TEST", latitude=lat, longitude=lon, acres=acres,
        location_consent=True, country_code="IN", subdivision_code="AP",
    )


def test_exact_road_point_is_blocked(load_fixture, tmp_path):
    client = LocationPreflightClient(
        PayloadHttp(load_fixture("nominatim_road.json")),
        JsonCache(tmp_path), Settings(cache_dir=tmp_path),
    )
    evidence = client.check(make_request(16.3067, 80.4365))
    assert evidence.blocking is True
    assert evidence.reason_code == "POINT_ON_OR_NEXT_TO_ROAD"
    assert evidence.feature_distance_m < 20


def test_distant_nearest_road_does_not_block_rural_point(load_fixture, tmp_path):
    client = LocationPreflightClient(
        PayloadHttp(load_fixture("nominatim_rural.json")),
        JsonCache(tmp_path), Settings(cache_dir=tmp_path),
    )
    evidence = client.check(make_request(16.1895796725143, 80.3434336669471, 1.746115))
    assert evidence.blocking is False
    assert evidence.feature_distance_m > 100
    assert evidence.subdivision_code == "AP"
