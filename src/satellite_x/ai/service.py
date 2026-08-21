"""Frozen differential rules with transparent confidence components."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from ..models import utc_now
from .models import (
    ConfidenceBreakdown,
    DiagnosisInput,
    DiagnosisResult,
    EvidenceItem,
)


class DiagnosisService:
    def __init__(self, clock: Callable[[], datetime] = utc_now):
        self.clock = clock

    def run(self, request: DiagnosisInput) -> DiagnosisResult:
        data = request.analytics
        ndvi = data.indices["ndvi"].mean
        ndmi = data.indices["ndmi"].mean
        ndre = data.indices["ndre"].mean
        phenology = data.phenology
        water = data.water_balance
        ndvi_low = ndvi < phenology.expected_ndvi_low
        moisture_low = ndmi < 0.10
        deficit = water.water_balance_15d_mm < -30.0
        humid = (
            water.humidity_mean_5d_pct is not None
            and water.humidity_mean_5d_pct > 85.0
        )
        soil_trusted = data.soil.source in {"soilgrids_live", "cache"}
        nitrogen_low = soil_trusted and data.soil.nitrogen_g_kg < 0.20
        ndre_low = ndre < 0.20
        maturity = phenology.stage_name in {"Maturity", "Post-season"}

        evidence = [
            EvidenceItem(
                code="NDVI_STAGE_POSITION", observed=phenology.ndvi_position,
                rule=f"NDVI < {phenology.expected_ndvi_low}",
                vote="SUPPORTS" if ndvi_low else "OPPOSES", source="sentinel2",
            ),
            EvidenceItem(
                code="CANOPY_MOISTURE", observed=ndmi, rule="NDMI < 0.10",
                vote="SUPPORTS" if moisture_low else "OPPOSES", source="sentinel2",
            ),
            EvidenceItem(
                code="WATER_BALANCE", observed=water.water_balance_15d_mm,
                rule="Rain15d - ET0_15d < -30 mm",
                vote="SUPPORTS" if deficit else "OPPOSES", source="open_meteo",
            ),
            EvidenceItem(
                code="HUMIDITY", observed=water.humidity_mean_5d_pct,
                rule="5-day mean humidity > 85%",
                vote="SUPPORTS" if humid else "NEUTRAL", source="open_meteo",
            ),
            EvidenceItem(
                code="SOIL_NITROGEN", observed=data.soil.nitrogen_g_kg,
                rule="Trusted soil N < 0.20 g/kg",
                vote=("SUPPORTS" if nitrogen_low else "OPPOSES" if soil_trusted else "NEUTRAL"),
                source=data.soil.source,
            ),
        ]

        suppressed = False
        verification = True
        warnings = list(data.data_warnings)
        if ndvi_low and moisture_low and deficit:
            verdict = "CONFIRMED_WATER_STRESS"
            te = "నీటి లోటు సంకేతాలు మూడు వనరుల్లో సరిపోలాయి. నేల పరిస్థితిని చూసి ఉదయం నీటిపారుదల చేయండి."
            en = "Water-deficit evidence agrees across vegetation, moisture and weather. Verify soil condition and irrigate in the morning if needed."
        elif ndvi_low and water.water_balance_15d_mm >= 0 and humid:
            verdict = "SUSPECTED_FUNGAL_RISK"
            te = "అధిక తేమతో పంట బలహీనత ఉంది. ఆకుల క్రింది భాగాన్ని పరిశీలించి వ్యవసాయ నిపుణుడిని సంప్రదించండి."
            en = "Low vegetation with wet/humid conditions suggests fungal risk. Inspect leaves and consult an agronomist before treatment."
        elif ndvi_low and ndre_low and nitrogen_low:
            verdict = "NITROGEN_DEFICIENCY_EVIDENCE"
            te = "క్లోరోఫిల్ మరియు ధృవీకరించిన నేల నత్రజని సంకేతాలు తక్కువగా ఉన్నాయి. నేల పరీక్ష ఆధారంగా మాత్రమే ఎరువు నిర్ణయించండి."
            en = "Chlorophyll and trusted soil nitrogen evidence are low. Base fertilizer action on a verified soil test."
        elif ndvi_low and maturity and phenology.criticality == "LOW":
            verdict = "NORMAL_MATURITY"
            suppressed = True
            verification = False
            te = "ఇది పక్వ దశలో సహజ వృద్ధాప్య సంకేతం కావచ్చు. కోత సిద్ధతను పరిశీలించండి."
            en = "This may be normal senescence at maturity. Check harvest readiness."
        else:
            verdict = "NORMAL_OR_UNRESOLVED"
            verification = phenology.ndvi_position != "WITHIN_EXPECTED"
            te = "తక్షణ నిర్ధారిత ఒత్తిడి లేదు. ట్రెండ్‌ను కొనసాగించి, అసాధారణత ఉంటే క్షేత్ర పరిశీలన చేయండి."
            en = "No confirmed stress cause. Continue monitoring and inspect the field if the trend remains abnormal."

        q = {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.2}[request.quality_tag]
        available = 2 + int(soil_trusted)
        completeness = available / 3
        votes = [ndvi_low, moisture_low, deficit]
        stress_fraction = sum(votes) / len(votes)
        agreement = abs(stress_fraction - 0.5) * 2
        penalty = {"known": 0.0, "approximate_month": 10.0, "unknown": 30.0}[
            request.sowing_date_quality
        ]
        raw = (0.40 * q + 0.30 * completeness + 0.30 * agreement) * 100
        final = max(0.0, min(100.0, raw - penalty))
        tag = (
            "HIGH_CONFIDENCE" if final >= 75
            else "MEDIUM_CONFIDENCE" if final >= 50
            else "LOW_CONFIDENCE"
        )
        if not soil_trusted:
            warnings.append("Soil is baseline/untrusted and did not cast a deficiency vote.")
        return DiagnosisResult(
            field_id=data.field_id, diagnosed_at=self.clock(), verdict=verdict,
            false_alarm_suppressed=suppressed, evidence=evidence,
            confidence=ConfidenceBreakdown(
                quality_factor=q, completeness_factor=round(completeness, 6),
                agreement_factor=round(agreement, 6), sowing_penalty_pct=penalty,
                raw_confidence_pct=round(raw, 3), final_confidence_pct=round(final, 3),
            ),
            confidence_tag=tag, action_telugu=te, action_english=en,
            ground_verification_required=verification, warnings=warnings,
        )
