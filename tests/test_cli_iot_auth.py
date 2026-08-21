import json
from types import SimpleNamespace

from satellite_x import cli
from satellite_x.iot_security import sign_hmac_sha256


class FakePipeline:
    verified_values = []

    def __init__(self, settings):
        self.settings = settings

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def run(self, field, iot, *, iot_verified=False):
        self.verified_values.append(iot_verified)
        return SimpleNamespace(
            status="complete",
            satellite=SimpleNamespace(
                scene=SimpleNamespace(scene_id="scene", provider="aws_earth_search")
            ),
            weather=SimpleNamespace(source="open_meteo_forecast"),
            soil=SimpleNamespace(source="soilgrids_live"),
            iot_verified=iot_verified,
            iot_fresh=True,
            warnings=[],
            model_dump=lambda mode: {
                "status": "complete",
                "iot_verified": iot_verified,
                "iot_fresh": True,
            },
        )


def test_cli_passes_verified_hmac_to_pipeline(tmp_path, monkeypatch):
    farm = tmp_path / "farm.json"
    farm.write_text(json.dumps({
        "field_id": "AP_F001", "latitude": 16.3, "longitude": 80.4,
        "crop_type": "chilli", "sowing_date": "2026-06-15",
        "analysis_date": "2026-08-17", "scan_range_days": 30, "acres": 5,
    }))
    iot = tmp_path / "iot.json"
    iot.write_text(json.dumps({
        "field_id": "AP_F001", "device_id": "node", "timestamp": "2026-08-17T05:00:00Z",
        "soil_moisture_pct": 30, "soil_temp_c": 25, "soil_ph": 7,
        "n_mg_kg": 1, "p_mg_kg": 1, "k_mg_kg": 1, "battery_v": 3.8,
        "source": "live_hardware",
    }))
    signature = sign_hmac_sha256(iot.read_bytes(), "secret")
    monkeypatch.setenv("SATELLITE_X_IOT_HMAC_SECRET", "secret")
    monkeypatch.setattr(cli, "AcquisitionPipeline", FakePipeline)
    FakePipeline.verified_values.clear()
    output = tmp_path / "out.json"
    code = cli.main([
        "acquire", "--input", str(farm), "--iot", str(iot),
        "--iot-signature", signature, "--output", str(output),
    ])
    assert code == 0
    assert FakePipeline.verified_values == [True]
    assert json.loads(output.read_text())["iot_verified"] is True


def test_cli_rejects_invalid_hmac_before_pipeline(tmp_path, monkeypatch):
    # Re-use the valid shapes but a malformed signature.
    farm = tmp_path / "farm.json"
    farm.write_text(json.dumps({
        "field_id": "A", "latitude": 16, "longitude": 80, "crop_type": "paddy",
        "sowing_date": "2026-01-01", "analysis_date": "2026-08-17", "acres": 1,
    }))
    iot = tmp_path / "iot.json"
    iot.write_text(json.dumps({
        "field_id": "A", "device_id": "node", "timestamp": "2026-08-17T05:00:00Z",
        "soil_moisture_pct": 30, "soil_temp_c": 25, "soil_ph": 7,
        "n_mg_kg": 1, "p_mg_kg": 1, "k_mg_kg": 1, "battery_v": 3.8,
        "source": "live_hardware",
    }))
    monkeypatch.setenv("SATELLITE_X_IOT_HMAC_SECRET", "secret")
    monkeypatch.setattr(cli, "AcquisitionPipeline", FakePipeline)
    FakePipeline.verified_values.clear()
    code = cli.main([
        "acquire", "--input", str(farm), "--iot", str(iot),
        "--iot-signature", "bad", "--output", str(tmp_path / "out.json"),
    ])
    assert code == 2
    assert FakePipeline.verified_values == []
