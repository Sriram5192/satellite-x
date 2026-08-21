"""Open-Meteo archive/forecast acquisition and 15/30-day aggregation."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import fmean
from typing import Any

from ..cache import JsonCache
from ..config import Settings
from ..errors import CacheMissError, ExternalServiceError
from ..http import JsonHttpClient
from ..models import DailyWeather, FarmInput, WeatherAcquisition, WeatherSummary

_DAILY_FIELDS = (
    "precipitation_sum,et0_fao_evapotranspiration,"
    "temperature_2m_max,temperature_2m_min"
)


class WeatherClient:
    def __init__(self, http: JsonHttpClient, cache: JsonCache, settings: Settings):
        self.http = http
        self.cache = cache
        self.settings = settings

    def acquire(self, field: FarmInput) -> tuple[WeatherAcquisition, list[str]]:
        warnings: list[str] = []
        history_start = field.analysis_date - timedelta(days=29)
        history_endpoint, source = self._history_endpoint(field.analysis_date)
        history_params = self._parameters(
            field.latitude, field.longitude, history_start, field.analysis_date
        )
        history_key = self.cache.make_key(
            "weather-history", {"endpoint": history_endpoint, **history_params}
        )
        fallback_used = False
        try:
            raw_history = self.http.get_json(
                "open_meteo", history_endpoint, params=history_params
            )
            history = self._parse_days(raw_history, "open_meteo")
            self.cache.put(history_key, {"source": source, "response": raw_history})
        except (ExternalServiceError, ValueError, KeyError, TypeError) as live_error:
            try:
                cached = self.cache.get(history_key)
                raw_history = cached["response"]
                history = self._parse_days(raw_history, "weather_cache")
            except (CacheMissError, ExternalServiceError, KeyError, TypeError, ValueError) as cache_error:
                raise ExternalServiceError(
                    "open_meteo",
                    f"live history failed ({live_error}); cache unavailable ({cache_error})",
                ) from live_error
            source = "cache"
            fallback_used = True
            warnings.append(f"Weather live request failed; cached response used: {live_error}")

        forecast: list[DailyWeather] = []
        if self._should_fetch_forecast(field.analysis_date):
            start = field.analysis_date + timedelta(days=1)
            end = start + timedelta(days=self.settings.forecast_days - 1)
            params = self._parameters(field.latitude, field.longitude, start, end)
            forecast_key = self.cache.make_key(
                "weather-forecast",
                {"endpoint": self.settings.open_meteo_forecast_url, **params},
            )
            try:
                raw_forecast = self.http.get_json(
                    "open_meteo_forecast",
                    self.settings.open_meteo_forecast_url,
                    params=params,
                )
                forecast = self._parse_days(raw_forecast, "open_meteo_forecast")
                self.cache.put(
                    forecast_key,
                    {"source": "open_meteo_forecast", "response": raw_forecast},
                )
            except (ExternalServiceError, ValueError, KeyError, TypeError) as live_error:
                try:
                    cached = self.cache.get(forecast_key)
                    forecast = self._parse_days(cached["response"], "weather_cache")
                    warnings.append(
                        f"Forecast live request failed; cached response used: {live_error}"
                    )
                except (CacheMissError, ExternalServiceError, KeyError, TypeError, ValueError):
                    warnings.append(
                        f"Forecast unavailable and no cache exists: {live_error}"
                    )

        history = sorted(history, key=lambda item: item.observation_date)[-30:]
        return (
            WeatherAcquisition(
                source=source,
                history=history,
                forecast=forecast,
                summary=self.summarize(history),
                cache_key=history_key,
                fallback_used=fallback_used,
            ),
            warnings,
        )

    def _history_endpoint(self, analysis_date: date) -> tuple[str, str]:
        # Forecast API provides recent observations; Archive is safer for older dates.
        if analysis_date >= date.today() - timedelta(days=7):
            return self.settings.open_meteo_forecast_url, "open_meteo_forecast"
        return self.settings.open_meteo_archive_url, "open_meteo_archive"

    @staticmethod
    def _should_fetch_forecast(analysis_date: date) -> bool:
        return date.today() - timedelta(days=1) <= analysis_date <= date.today()

    @staticmethod
    def _parameters(
        latitude: float, longitude: float, start: date, end: date
    ) -> dict[str, Any]:
        return {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": _DAILY_FIELDS,
            "hourly": "relative_humidity_2m",
            "timezone": "UTC",
        }

    @staticmethod
    def _parse_days(payload: dict[str, Any], service: str) -> list[DailyWeather]:
        try:
            daily = payload["daily"]
            times = daily["time"]
            rain = daily["precipitation_sum"]
            et0 = daily["et0_fao_evapotranspiration"]
            max_temp = daily["temperature_2m_max"]
            min_temp = daily["temperature_2m_min"]
            hourly = payload["hourly"]
            hourly_times = hourly["time"]
            hourly_humidity = hourly["relative_humidity_2m"]
        except (KeyError, TypeError) as exc:
            raise ExternalServiceError(service, f"missing weather field: {exc}") from exc

        lengths = {len(times), len(rain), len(et0), len(max_temp), len(min_temp)}
        if len(lengths) != 1:
            raise ExternalServiceError(service, "daily arrays have different lengths")
        if len(hourly_times) != len(hourly_humidity):
            raise ExternalServiceError(service, "hourly humidity arrays have different lengths")

        humidity_by_date: dict[date, list[float]] = defaultdict(list)
        for timestamp, humidity in zip(hourly_times, hourly_humidity, strict=True):
            if humidity is None:
                continue
            observed_date = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).date()
            humidity_by_date[observed_date].append(float(humidity))

        output: list[DailyWeather] = []
        for values in zip(times, rain, et0, max_temp, min_temp, strict=True):
            day_text, rain_value, et0_value, max_value, min_value = values
            observed_date = date.fromisoformat(str(day_text))
            humidities = humidity_by_date.get(observed_date, [])
            if any(value is None for value in (rain_value, et0_value, max_value, min_value)):
                raise ExternalServiceError(service, f"null daily value on {observed_date}")
            if not humidities:
                raise ExternalServiceError(service, f"no humidity values on {observed_date}")
            output.append(
                DailyWeather(
                    observation_date=observed_date,
                    precipitation_mm=float(rain_value),
                    et0_mm=float(et0_value),
                    temperature_max_c=float(max_value),
                    temperature_min_c=float(min_value),
                    relative_humidity_mean_pct=round(fmean(humidities), 3),
                )
            )
        if not output:
            raise ExternalServiceError(service, "weather response contains zero days")
        return output

    @staticmethod
    def summarize(history: list[DailyWeather]) -> WeatherSummary:
        ordered = sorted(history, key=lambda item: item.observation_date)
        latest_15 = ordered[-15:]
        latest_30 = ordered[-30:]
        latest_5 = ordered[-5:]
        return WeatherSummary(
            days_available_15d=len(latest_15),
            rain_15d_mm=round(sum(item.precipitation_mm for item in latest_15), 3),
            et0_15d_mm=round(sum(item.et0_mm for item in latest_15), 3),
            days_available_30d=len(latest_30),
            rain_30d_mm=round(sum(item.precipitation_mm for item in latest_30), 3),
            et0_30d_mm=round(sum(item.et0_mm for item in latest_30), 3),
            humidity_mean_5d_pct=(
                round(fmean(item.relative_humidity_mean_pct for item in latest_5), 3)
                if latest_5
                else None
            ),
            complete_15d=len(latest_15) == 15,
            complete_30d=len(latest_30) == 30,
        )
