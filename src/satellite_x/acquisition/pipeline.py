"""Set 1 acquisition orchestration and provenance assembly."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from ..cache import JsonCache
from ..config import Settings
from ..http import JsonHttpClient
from ..models import (
    FarmInput,
    IoTReading,
    RawDataContainer,
    StreamState,
    utc_now,
)
from .satellite import SatelliteClient
from .soil import SoilGridsClient
from .weather import WeatherClient


class AcquisitionPipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http: JsonHttpClient | None = None,
        satellite_client: SatelliteClient | None = None,
        weather_client: WeatherClient | None = None,
        soil_client: SoilGridsClient | None = None,
        clock: Callable[[], datetime] = utc_now,
    ):
        self.settings = settings or Settings.from_env()
        self.http = http or JsonHttpClient(self.settings)
        self._owns_http = http is None
        cache = JsonCache(self.settings.cache_dir)
        self.satellite_client = satellite_client or SatelliteClient(
            self.http, self.settings
        )
        self.weather_client = weather_client or WeatherClient(
            self.http, cache, self.settings
        )
        self.soil_client = soil_client or SoilGridsClient(
            self.http, cache, self.settings
        )
        self.clock = clock

    def run(
        self,
        field: FarmInput,
        iot: IoTReading | None = None,
        *,
        iot_verified: bool = False,
    ) -> RawDataContainer:
        if iot is None and iot_verified:
            raise ValueError("iot_verified cannot be true without an IoT reading")
        if iot is not None and iot.field_id != field.field_id:
            raise ValueError(
                f"IoT field_id {iot.field_id!r} does not match {field.field_id!r}"
            )

        satellite = self.satellite_client.acquire(field)
        weather, weather_warnings = self.weather_client.acquire(field)
        soil, soil_warnings = self.soil_client.acquire(field)
        acquired_at = self.clock()

        warnings = [*weather_warnings, *soil_warnings]
        iot_fresh: bool | None = None
        iot_age_hours: float | None = None
        if iot is not None:
            iot_age_hours = (acquired_at - iot.timestamp).total_seconds() / 3600.0
            iot_fresh = -5.0 / 60.0 <= iot_age_hours <= self.settings.iot_max_age_hours
            if not iot_verified:
                warnings.append(
                    "IoT payload schema is valid but hardware provenance is unverified; "
                    "a valid HMAC-SHA256 signature is required for live status."
                )
            if not iot_fresh:
                warnings.append(
                    f"IoT payload is outside the freshness window: age={iot_age_hours:.2f}h, "
                    f"allowed=-0.08h to {self.settings.iot_max_age_hours:.2f}h."
                )
        if satellite.expanded_date_range:
            warnings.append(
                f"Satellite search range was expanded by {self.settings.expand_days} days."
            )
        if satellite.fallback_used:
            warnings.append("AWS STAC was unavailable/empty; Copernicus CDSE was used.")
        if any(
            asset.requires_authentication for asset in satellite.scene.assets.values()
        ):
            warnings.append(
                "Selected CDSE assets include authenticated s3:// URLs; CDSE credentials "
                "are required before raster download."
            )

        streams = [
            StreamState(
                stream="satellite",
                state="live",
                detail=(
                    f"{satellite.scene.provider}:{satellite.scene.scene_id}"
                    + (" (expanded range)" if satellite.expanded_date_range else "")
                ),
            ),
            StreamState(
                stream="weather",
                state="cache" if weather.source == "cache" else "live",
                detail=weather.source,
            ),
            StreamState(
                stream="soil",
                state=(
                    "baseline"
                    if soil.source == "regional_ag_zone_baseline"
                    else "cache"
                    if soil.source == "cache"
                    else "live"
                ),
                detail=soil.source,
            ),
            StreamState(
                stream="iot",
                state=(
                    "not_supplied"
                    if iot is None
                    else "unverified"
                    if not iot_verified
                    else "stale"
                    if not iot_fresh
                    else "live"
                ),
                detail=(
                    "optional stream not supplied"
                    if iot is None
                    else (
                        f"{iot.device_id}; verified={iot_verified}; "
                        f"age_hours={iot_age_hours:.2f}"
                    )
                ),
            ),
        ]
        mandatory_non_live = any(
            stream.stream in {"satellite", "weather", "soil"}
            and stream.state in {"cache", "baseline"}
            for stream in streams
        )
        iot_not_live = iot is not None and (not iot_verified or not iot_fresh)
        status = "degraded" if (
            mandatory_non_live
            or iot_not_live
            or any(
                asset.requires_authentication for asset in satellite.scene.assets.values()
            )
        ) else "complete"
        return RawDataContainer(
            field=field,
            acquired_at=acquired_at,
            status=status,
            satellite=satellite,
            weather=weather,
            soil=soil,
            iot=iot,
            iot_verified=iot_verified,
            iot_fresh=iot_fresh,
            streams=streams,
            warnings=warnings,
        )

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> "AcquisitionPipeline":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
