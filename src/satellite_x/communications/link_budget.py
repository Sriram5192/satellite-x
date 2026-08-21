"""Calibratable downlink budget with thermal noise and Doppler."""
from __future__ import annotations

import math

from .models import LinkBudgetInput, LinkBudgetResult

C_M_S = 299_792_458.0
K_BOLTZMANN = 1.380649e-23


class LinkBudgetService:
    def run(self, request: LinkBudgetInput) -> LinkBudgetResult:
        wavelength_m = C_M_S / (request.frequency_ghz * 1e9)
        fspl = (
            92.45
            + 20 * math.log10(request.frequency_ghz)
            + 20 * math.log10(request.range_km)
        )
        receive_gain = 10 * math.log10(
            request.receive_antenna_efficiency
            * (math.pi * request.receive_antenna_diameter_m / wavelength_m) ** 2
        )
        received = (
            request.transmit_eirp_dbw
            + receive_gain
            - fspl
            - request.atmospheric_loss_db
            - request.other_losses_db
        )
        n0 = 10 * math.log10(K_BOLTZMANN * request.system_noise_temperature_k)
        c_n0 = received - n0
        eb_n0 = c_n0 - 10 * math.log10(request.data_rate_bps)
        margin = eb_n0 - request.required_eb_n0_db
        doppler = -(
            request.frequency_ghz * 1e9 * request.range_rate_km_s / 299_792.458
        )
        return LinkBudgetResult(
            calibration_status=request.calibration_status,
            free_space_path_loss_db=round(fspl, 6),
            receive_antenna_gain_dbi=round(receive_gain, 6),
            received_carrier_power_dbw=round(received, 6),
            noise_density_dbw_hz=round(n0, 6),
            c_n0_db_hz=round(c_n0, 6),
            eb_n0_db=round(eb_n0, 6),
            link_margin_db=round(margin, 6),
            doppler_shift_hz=round(doppler, 3),
            status="margin_positive" if margin >= 0 else "margin_negative",
            assumptions=[
                "Transmit EIRP, receiver noise temperature, antenna efficiency and required Eb/N0 are caller-supplied calibration inputs.",
                "No live beacon measurement is inferred from this calculation.",
            ],
        )
