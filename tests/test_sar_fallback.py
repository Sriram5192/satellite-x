from datetime import date

from satellite_x.config import Settings
from satellite_x.preprocessing.models import SarFallbackInput
from satellite_x.preprocessing.sar import SarFallbackService


class FakeHttp:
    def post_json(self, service, url, *, payload):
        return {"features": [{
            "id": "S1_RTC_TEST",
            "properties": {"datetime": "2026-08-05T00:00:00Z", "sat:orbit_state": "descending"},
            "assets": {"vv": {"href": "https://x/vv.tif"}, "vh": {"href": "https://x/vh.tif"}},
        }]}

    def get_json(self, service, url, *, params=None):
        return {"token": "signed-token"}

    def close(self):
        pass


def test_sar_fallback_contract(monkeypatch):
    monkeypatch.setattr(
        SarFallbackService,
        "_measure",
        staticmethod(lambda feature, geometry, token: {
            "valid_pixels": 10, "vv_db_mean": -10.0,
            "vh_db_mean": -20.0, "ratio_db_mean": 10.0,
        }),
    )
    request = SarFallbackInput(
        field_id="F1",
        boundary_geojson={"type": "Polygon", "coordinates": [[[80, 16], [81, 16], [81, 17], [80, 16]]]},
        analysis_date=date(2026, 8, 17), scan_range_days=30,
    )
    result = SarFallbackService(Settings(), http=FakeHttp()).run(request)
    assert result.status == "accepted"
    assert result.scene_id == "S1_RTC_TEST"
    assert result.vv_minus_vh_db_mean == 10
