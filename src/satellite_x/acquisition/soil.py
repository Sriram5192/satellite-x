"""ISRIC SoilGrids topsoil properties with cache and explicit baseline fallback."""

from __future__ import annotations

from typing import Any

from ..cache import JsonCache
from ..config import Settings
from ..errors import CacheMissError, ExternalServiceError
from ..http import JsonHttpClient
from ..models import FarmInput, SoilProperties


class SoilGridsClient:
    def __init__(self, http: JsonHttpClient, cache: JsonCache, settings: Settings):
        self.http = http
        self.cache = cache
        self.settings = settings

    def acquire(self, field: FarmInput) -> tuple[SoilProperties, list[str]]:
        params: dict[str, Any] = {
            "lat": field.latitude,
            "lon": field.longitude,
            "property": ["phh2o", "nitrogen"],
            "depth": ["0-5cm"],
            "value": ["mean"],
        }
        cache_key = self.cache.make_key("soilgrids", params)
        try:
            payload = self.http.get_json(
                "soilgrids", self.settings.soilgrids_url, params=params
            )
            ph, nitrogen = self._parse(payload)
            self.cache.put(cache_key, {"response": payload})
            return (
                SoilProperties(
                    ph_h2o=ph,
                    nitrogen_g_kg=nitrogen,
                    source="soilgrids_live",
                    fallback_used=False,
                    cache_key=cache_key,
                ),
                [],
            )
        except (ExternalServiceError, KeyError, TypeError, ValueError) as live_error:
            try:
                payload = self.cache.get(cache_key)["response"]
                ph, nitrogen = self._parse(payload)
                return (
                    SoilProperties(
                        ph_h2o=ph,
                        nitrogen_g_kg=nitrogen,
                        source="cache",
                        fallback_used=True,
                        cache_key=cache_key,
                    ),
                    [f"SoilGrids live request failed; cached response used: {live_error}"],
                )
            except (CacheMissError, ExternalServiceError, KeyError, TypeError, ValueError):
                return (
                    SoilProperties(
                        ph_h2o=self.settings.soil_baseline_ph,
                        nitrogen_g_kg=self.settings.soil_baseline_n_g_kg,
                        source="regional_ag_zone_baseline",
                        fallback_used=True,
                        cache_key=cache_key,
                    ),
                    [
                        "SoilGrids live request and cache failed; frozen regional "
                        f"baseline used (pH={self.settings.soil_baseline_ph}, "
                        f"N={self.settings.soil_baseline_n_g_kg} g/kg): {live_error}"
                    ],
                )

    @staticmethod
    def _parse(payload: dict[str, Any]) -> tuple[float, float]:
        layers = payload["properties"]["layers"]
        if not isinstance(layers, list):
            raise ExternalServiceError("soilgrids", "properties.layers must be an array")
        raw: dict[str, float] = {}
        for layer in layers:
            name = layer.get("name")
            if name not in {"phh2o", "nitrogen"}:
                continue
            depths = layer.get("depths", [])
            selected = next(
                (depth for depth in depths if depth.get("label") == "0-5cm"), None
            )
            if selected is None:
                raise ExternalServiceError(
                    "soilgrids", f"0-5cm depth absent for {name}"
                )
            mean_value = selected.get("values", {}).get("mean")
            if mean_value is None:
                raise ExternalServiceError("soilgrids", f"mean absent for {name}")
            raw[name] = float(mean_value)
        if set(raw) != {"phh2o", "nitrogen"}:
            raise ExternalServiceError(
                "soilgrids", "response must contain phh2o and nitrogen"
            )
        # SoilGrids integer storage conversion factors from the frozen specification.
        return round(raw["phh2o"] / 10.0, 3), round(raw["nitrogen"] / 100.0, 3)
