from datetime import datetime, timedelta, timezone

import pytest

from satellite_x.communications import (
    AtmosphericLossInput, AtmosphericLossService, ContactWindow,
    DynamicContactScheduler, LinkBudgetInput, LinkBudgetService,
    TrafficRequest, TrafficSimulationInput,
)
from satellite_x.orbit import (
    CelesTrakTleClient, GroundStation, PassPredictionInput, PassPredictionService,
)


NAME = "SENTINEL-2A"
LINE1 = "1 40697U 15028A   26231.78110885 -.00000139  00000+0 -36533-4 0  9992"
LINE2 = "2 40697  98.5643 305.7179 0001319  86.0998 274.0335 14.30821672582822"


class Response:
    text = f"{NAME}\n{LINE1}\n{LINE2}\n"
    def raise_for_status(self): pass


class Session:
    def get(self, *args, **kwargs):
        assert kwargs["allow_redirects"] is False
        return Response()


@pytest.mark.live
def test_live_celestrak_tle_and_current_pass_prediction():
    tle = CelesTrakTleClient(maximum_age_hours=72).fetch(40697)
    assert tle.freshness == "fresh"
    start = datetime.now(timezone.utc)
    result = PassPredictionService().run(
        PassPredictionInput(
            tle=tle,
            station=GroundStation(
                station_id="GUNTUR-LIVE", latitude=16.3067,
                longitude=80.4365, elevation_m=30,
            ),
            start_time=start, end_time=start + timedelta(days=1),
            minimum_elevation_deg=5, downlink_frequency_hz=8.2e9,
            sample_interval_seconds=30,
        )
    )
    assert result.status in {"accepted", "no_pass"}
    if result.passes:
        assert result.passes[0].max_absolute_doppler_hz > 0


def test_checksum_validated_tle_pass_and_dynamic_doppler():
    now = datetime(2026, 8, 19, 20, tzinfo=timezone.utc)
    tle = CelesTrakTleClient(
        session=Session(), clock=lambda: now, maximum_age_hours=72
    ).fetch(40697)
    assert tle.freshness == "fresh"
    request = PassPredictionInput(
        tle=tle,
        station=GroundStation(
            station_id="GUNTUR-VALIDATION", latitude=16.3067,
            longitude=80.4365, elevation_m=30,
        ),
        start_time=tle.epoch,
        end_time=tle.epoch + timedelta(days=1),
        minimum_elevation_deg=10,
        downlink_frequency_hz=8.2e9,
        sample_interval_seconds=30,
    )
    result = PassPredictionService().run(request)
    assert result.status == "accepted"
    assert result.passes
    assert result.passes[0].max_absolute_doppler_hz > 100_000
    stale = PassPredictionService().run(
        request.model_copy(update={"start_time": tle.epoch + timedelta(days=20), "end_time": tle.epoch + timedelta(days=21)})
    )
    assert stale.status == "tle_epoch_out_of_policy"
    assert stale.passes == []


def test_itu_atmosphere_and_calibrated_link_budget_are_explicitly_not_live_beacon():
    atmosphere = AtmosphericLossService().run(
        AtmosphericLossInput(
            latitude=16.3067, longitude=80.4365, frequency_ghz=8.2,
            elevation_deg=30, exceedance_probability_pct=0.01,
            antenna_diameter_m=3.0,
        )
    )
    assert atmosphere.modeled_total_db > 0
    assert atmosphere.rain_db >= 0
    assert atmosphere.live_beacon_calibrated is False
    assert atmosphere.ionospheric_status == "not_applied_x_band_above_6_ghz"
    budget = LinkBudgetService().run(
        LinkBudgetInput(
            calibration_status="caller_supplied_validation_fixture",
            frequency_ghz=8.2, range_km=1000, data_rate_bps=560e6,
            transmit_eirp_dbw=60, receive_antenna_diameter_m=3,
            receive_antenna_efficiency=0.6, system_noise_temperature_k=150,
            atmospheric_loss_db=atmosphere.combined_total_db,
            other_losses_db=2, required_eb_n0_db=6,
            range_rate_km_s=5,
        )
    )
    assert abs(budget.doppler_shift_hz) > 100_000
    assert budget.calibration_status == "caller_supplied_validation_fixture"


def test_dynamic_contact_scheduler_handles_120_station_requests_and_reports_drops():
    requests = [
        TrafficRequest(
            request_id=f"R{i:03d}", station_id=f"STATION-{i:03d}",
            arrival_second=i % 60, deadline_second=300 + (i % 5) * 30,
            data_megabits=4000 + (i % 4) * 500, priority=1 + (i % 10),
        )
        for i in range(120)
    ]
    result = DynamicContactScheduler().run(
        TrafficSimulationInput(
            scenario_purpose="deterministic_validation_fixture",
            simulation_duration_seconds=600,
            contacts=[
                ContactWindow(
                    window_id="PASS-1", start_second=0, end_second=600,
                    channel_count=2, per_channel_capacity_mbps=280,
                )
            ],
            requests=requests,
        )
    )
    assert result.total_requests == 120
    assert result.completed_requests > 0
    assert result.dropped_requests > 0
    assert 0 < result.channel_utilization_pct <= 100
    assert result.dropped_megabits > 0
