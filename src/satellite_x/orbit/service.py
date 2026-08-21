"""CelesTrak TLE validation and Skyfield/SGP4 pass plus Doppler prediction."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

import requests

from ..models import utc_now
from .models import (
    PassPredictionInput, PassPredictionResult, PassSample, PassWindow, TleRecord,
)

C_KM_S = 299_792.458


def _tle_checksum_valid(line: str) -> bool:
    if len(line) != 69 or not line[-1].isdigit():
        return False
    total = sum(int(ch) for ch in line[:68] if ch.isdigit())
    total += line[:68].count("-")
    return total % 10 == int(line[-1])


class CelesTrakTleClient:
    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        clock: Callable[[], datetime] = utc_now,
        timeout_seconds: float = 30,
        maximum_age_hours: float = 72,
    ):
        self.session = session or requests.Session()
        self.clock = clock
        self.timeout_seconds = timeout_seconds
        self.maximum_age_hours = maximum_age_hours

    def fetch(self, norad_id: int) -> TleRecord:
        from skyfield.api import EarthSatellite, load

        url = (
            "https://celestrak.org/NORAD/elements/gp.php"
            f"?CATNR={norad_id}&FORMAT=TLE"
        )
        response = self.session.get(
            url,
            timeout=self.timeout_seconds,
            headers={"User-Agent": "SATELLITE-X/0.8 orbital-provenance"},
            allow_redirects=False,
        )
        response.raise_for_status()
        lines = [line.strip() for line in response.text.splitlines() if line.strip()]
        if len(lines) != 3:
            raise ValueError("CelesTrak response must contain name and two TLE lines")
        name, line1, line2 = lines
        if not (_tle_checksum_valid(line1) and _tle_checksum_valid(line2)):
            raise ValueError("TLE checksum validation failed")
        if int(line1[2:7]) != norad_id or int(line2[2:7]) != norad_id:
            raise ValueError("TLE NORAD identifier does not match request")
        satellite = EarthSatellite(line1, line2, name, load.timescale())
        epoch = satellite.epoch.utc_datetime().astimezone(timezone.utc)
        fetched = self.clock().astimezone(timezone.utc)
        age_hours = (fetched - epoch).total_seconds() / 3600
        freshness = (
            "fresh" if abs(age_hours) <= self.maximum_age_hours else "stale"
        )
        return TleRecord(
            name=name,
            norad_id=norad_id,
            line1=line1,
            line2=line2,
            epoch=epoch,
            fetched_at=fetched,
            source_url=url,
            age_hours_at_fetch=round(age_hours, 6),
            freshness=freshness,
            maximum_age_hours=self.maximum_age_hours,
        )


class PassPredictionService:
    def run(self, request: PassPredictionInput) -> PassPredictionResult:
        from skyfield.api import EarthSatellite, load, wgs84

        epoch_gap = abs(
            (request.start_time.astimezone(timezone.utc) - request.tle.epoch).total_seconds()
        ) / 3600
        if epoch_gap > request.maximum_tle_epoch_gap_hours:
            return PassPredictionResult(
                norad_id=request.tle.norad_id,
                satellite_name=request.tle.name,
                station_id=request.station.station_id,
                tle_epoch=request.tle.epoch,
                prediction_start=request.start_time,
                prediction_end=request.end_time,
                tle_epoch_gap_hours=round(epoch_gap, 6),
                status="tle_epoch_out_of_policy",
                passes=[],
                warnings=[
                    "TLE epoch is too far from the prediction window; no pass or Doppler result was produced."
                ],
            )
        ts = load.timescale()
        satellite = EarthSatellite(
            request.tle.line1, request.tle.line2, request.tle.name, ts
        )
        station = wgs84.latlon(
            request.station.latitude,
            request.station.longitude,
            elevation_m=request.station.elevation_m,
        )
        difference = satellite - station
        t0 = ts.from_datetime(request.start_time.astimezone(timezone.utc))
        t1 = ts.from_datetime(request.end_time.astimezone(timezone.utc))
        times, events = satellite.find_events(
            station, t0, t1, altitude_degrees=request.minimum_elevation_deg
        )
        open_aos = None
        open_tca = None
        windows: list[PassWindow] = []
        for time, event in zip(times, events, strict=True):
            observed = time.utc_datetime().astimezone(timezone.utc)
            if int(event) == 0:
                open_aos = observed
                open_tca = None
            elif int(event) == 1 and open_aos is not None:
                open_tca = observed
            elif int(event) == 2 and open_aos is not None:
                los = observed
                tca = open_tca or open_aos + (los - open_aos) / 2
                samples = self._samples(
                    difference,
                    ts,
                    open_aos,
                    los,
                    request.sample_interval_seconds,
                    request.downlink_frequency_hz,
                )
                windows.append(
                    PassWindow(
                        aos=open_aos,
                        tca=tca,
                        los=los,
                        duration_seconds=round((los - open_aos).total_seconds(), 3),
                        max_elevation_deg=max(sample.elevation_deg for sample in samples),
                        max_absolute_doppler_hz=max(
                            abs(sample.doppler_shift_hz) for sample in samples
                        ),
                        samples=samples,
                    )
                )
                open_aos = None
                open_tca = None
        return PassPredictionResult(
            norad_id=request.tle.norad_id,
            satellite_name=request.tle.name,
            station_id=request.station.station_id,
            tle_epoch=request.tle.epoch,
            prediction_start=request.start_time,
            prediction_end=request.end_time,
            tle_epoch_gap_hours=round(epoch_gap, 6),
            status="accepted" if windows else "no_pass",
            passes=windows,
            warnings=[
                "TLE/SGP4 validates predicted geometry, not live beacon telemetry or measured atmospheric loss."
            ],
        )

    @staticmethod
    def _samples(difference, ts, aos, los, interval_s, frequency_hz):
        moments = []
        current = aos
        while current < los:
            moments.append(current)
            current += timedelta(seconds=interval_s)
        if not moments or moments[-1] != los:
            moments.append(los)
        output = []
        for moment in moments:
            sky_time = ts.from_datetime(moment)
            topocentric = difference.at(sky_time)
            altitude, azimuth, distance = topocentric.altaz()
            before = difference.at(ts.from_datetime(moment - timedelta(seconds=0.5)))
            after = difference.at(ts.from_datetime(moment + timedelta(seconds=0.5)))
            range_rate = after.distance().km - before.distance().km
            doppler = -frequency_hz * range_rate / C_KM_S
            output.append(
                PassSample(
                    timestamp=moment,
                    elevation_deg=round(float(altitude.degrees), 6),
                    azimuth_deg=round(float(azimuth.degrees), 6),
                    range_km=round(float(distance.km), 6),
                    range_rate_km_s=round(float(range_rate), 9),
                    doppler_shift_hz=round(float(doppler), 3),
                )
            )
        return output
