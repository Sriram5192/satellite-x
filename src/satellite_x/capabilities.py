"""Machine-readable activation gates for externally dependent capabilities."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Capability(BaseModel):
    code: str
    status: Literal["implemented", "implemented_evidence_only", "implemented_activation_required", "blocked_external"]
    activation_requirements: list[str]
    unsafe_shortcut: str


def capability_registry() -> list[Capability]:
    return [
        Capability(code="sentinel1_rtc", status="implemented_evidence_only", activation_requirements=["Local SAR ground labels before diagnosis thresholds"], unsafe_shortcut="Treating SAR dB as NDVI or fixed crop stress"),
        Capability(code="government_land_records", status="implemented_activation_required", activation_requirements=["Official API/MoU", "Authorized credentials", "Legal/privacy review"], unsafe_shortcut="Scraping or bypassing CAPTCHA/OTP"),
        Capability(code="phone_otp", status="implemented_activation_required", activation_requirements=["SMS provider credentials", "Consent notice", "Production secrets vault"], unsafe_shortcut="Fake OTP or hard-coded bypass"),
        Capability(code="yield_prediction", status="implemented_activation_required", activation_requirements=["Multi-season verified field yields", "District/crop human validation", "Approval report"], unsafe_shortcut="Publishing yield from unvalidated coefficients"),
        Capability(code="vra_machinery", status="implemented_activation_required", activation_requirements=["Target equipment profile", "Agronomist-approved rates", "Operator checks", "Safety field trial"], unsafe_shortcut="Generating fertilizer or spray rates from NDVI alone"),
        Capability(code="mobile_offline", status="implemented_activation_required", activation_requirements=["Target-device GPS/photo test", "Production TLS deployment", "Authorized SMS and backend secrets"], unsafe_shortcut="Claiming field deployment from automated PWA/API tests"),
        Capability(code="orbit_tle_doppler", status="implemented_evidence_only", activation_requirements=["Fresh or historical TLE near prediction epoch", "Ground-station coordinates", "Live beacon for measured validation"], unsafe_shortcut="Calling TLE/SGP4 a live telemetry or beacon measurement"),
        Capability(code="xband_atmosphere_traffic", status="implemented_evidence_only", activation_requirements=["Calibrated EIRP/G-T/noise inputs", "Local meteorology or beacon measurements", "Authorized mission contact/traffic traces"], unsafe_shortcut="Claiming a generic 100-station fixture represents Sentinel operations"),
    ]
