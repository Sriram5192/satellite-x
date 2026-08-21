"""ITU-R atmospheric contributions with explicit non-beacon-calibrated state."""
from __future__ import annotations

from .models import AtmosphericLossInput, AtmosphericLossResult


class AtmosphericLossService:
    def run(self, request: AtmosphericLossInput) -> AtmosphericLossResult:
        try:
            import itur
        except ImportError as exc:
            raise RuntimeError(
                "Install requirements-communications.txt for ITU-R models"
            ) from exc
        contributions = itur.atmospheric_attenuation_slant_path(
            request.latitude,
            request.longitude,
            request.frequency_ghz,
            request.elevation_deg,
            request.exceedance_probability_pct,
            request.antenna_diameter_m,
            hs=request.station_altitude_km,
            rho=request.water_vapour_density_g_m3,
            R001=request.rainfall_rate_001_mm_h,
            T=request.temperature_k,
            P=request.pressure_hpa,
            return_contributions=True,
        )
        gas, cloud, rain, scintillation, total = [
            max(0.0, float(value.value)) for value in contributions
        ]
        measured_iono = request.measured_ionospheric_fade_db
        if measured_iono is not None:
            iono_status = "measured_value_included"
        elif request.frequency_ghz > 6:
            iono_status = "not_applied_x_band_above_6_ghz"
        else:
            iono_status = "requires_measured_or_calibrated_input"
        combined = total + (measured_iono or 0.0)
        warnings = [
            "ITU-R output is a long-term statistical prediction, not live beacon telemetry.",
            "Climatology is used for omitted local meteorological inputs.",
        ]
        if measured_iono is None:
            warnings.append(
                "No measured ionospheric fade was supplied; no unverified ionospheric loss was invented."
            )
        return AtmosphericLossResult(
            model="ITU-R_P.618_with_P.676_P.837_P.840",
            gaseous_db=round(gas, 6),
            cloud_db=round(cloud, 6),
            rain_db=round(rain, 6),
            tropospheric_scintillation_db=round(scintillation, 6),
            modeled_total_db=round(total, 6),
            ionospheric_fade_db=(
                round(measured_iono, 6) if measured_iono is not None else None
            ),
            combined_total_db=round(combined, 6),
            ionospheric_status=iono_status,
            warnings=warnings,
        )
