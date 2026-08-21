from datetime import date, datetime, timezone

import numpy as np

from satellite_x.ai.models import DiagnosisInput
from satellite_x.ai.service import DiagnosisService
from satellite_x.analytics.formulas import compute_indices
from satellite_x.analytics.models import (
    AnalyticsResult, IndexStatistics, PhenologyState, WaterBalanceState,
)
from satellite_x.analytics.phenology import phenology_state
from satellite_x.models import SoilProperties


def stat(value):
    return IndexStatistics(
        mean=value, median=value, p10=value, p90=value,
        minimum=value, maximum=value, valid_pixels=10,
    )


def analytics(*, ndvi=0.2, ndmi=0.0, ndre=0.1, balance=-40, humidity=60,
              stage="Vegetative", criticality="MEDIUM", position="BELOW_EXPECTED",
              soil_source="soilgrids_live", nitrogen=0.1):
    return AnalyticsResult(
        field_id="F1", computed_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        scene_id="S", scene_date=date(2026, 8, 1), spectral_valid_pixels=10,
        spectral_valid_pct=100,
        indices={name: stat(value) for name, value in {
            "ndvi": ndvi, "evi": ndvi, "savi": ndvi, "ndre": ndre,
            "ndmi": ndmi, "ndwi": -0.2, "gndvi": 0.3,
        }.items()},
        phenology=PhenologyState(
            crop_type="chilli", das=40, stage_name=stage,
            stage_start_das=20, stage_end_das=50,
            expected_ndvi_low=0.3, expected_ndvi_high=0.6,
            criticality=criticality, ndvi_position=position,
        ),
        water_balance=WaterBalanceState(
            reference_start_date=date(2026, 7, 18),
            reference_end_date=date(2026, 8, 1),
            rain_15d_mm=20, et0_15d_mm=20-balance,
            water_balance_15d_mm=balance, humidity_mean_5d_pct=humidity,
            deficit_flag=balance < -30,
        ),
        soil=SoilProperties(
            ph_h2o=6.5, nitrogen_g_kg=nitrogen, source=soil_source,
            fallback_used=soil_source != "soilgrids_live",
        ),
    )


def test_seven_formulas_on_known_reflectance():
    bands = {name: np.array([value], dtype=float) for name, value in {
        "B02": 0.1, "B03": 0.2, "B04": 0.3,
        "B05": 0.4, "B08": 0.7, "B11": 0.5,
    }.items()}
    result = compute_indices(bands)
    assert set(result) == {"ndvi", "evi", "savi", "ndre", "ndmi", "ndwi", "gndvi"}
    assert np.isclose(result["ndvi"][0], 0.4)
    assert np.isclose(result["ndre"][0], 0.3 / 1.1)
    assert np.isclose(result["ndmi"][0], 0.2 / 1.2)
    assert np.isclose(result["gndvi"][0], 0.5 / 0.9)


def test_phenology_uses_das_and_expected_range():
    state = phenology_state("paddy", 50, 0.55)
    assert state.stage_name == "Panicle Initiation"
    assert state.criticality == "CRITICAL"
    assert state.ndvi_position == "BELOW_EXPECTED"


def test_confirmed_water_stress_rule():
    result = DiagnosisService().run(
        DiagnosisInput(analytics=analytics(), quality_tag="HIGH", sowing_date_quality="known")
    )
    assert result.verdict == "CONFIRMED_WATER_STRESS"
    assert result.ground_verification_required is True


def test_fungal_risk_is_suspected_not_confirmed():
    result = DiagnosisService().run(
        DiagnosisInput(
            analytics=analytics(ndmi=0.2, balance=5, humidity=90),
            quality_tag="MEDIUM", sowing_date_quality="known",
        )
    )
    assert result.verdict == "SUSPECTED_FUNGAL_RISK"
    assert "inspect" in result.action_english.lower()


def test_baseline_soil_cannot_vote_nitrogen_deficiency():
    result = DiagnosisService().run(
        DiagnosisInput(
            analytics=analytics(ndmi=0.2, balance=5, humidity=60,
                                soil_source="regional_ag_zone_baseline", nitrogen=0.05),
            quality_tag="HIGH", sowing_date_quality="known",
        )
    )
    assert result.verdict != "NITROGEN_DEFICIENCY_EVIDENCE"
    soil_evidence = next(e for e in result.evidence if e.code == "SOIL_NITROGEN")
    assert soil_evidence.vote == "NEUTRAL"


def test_maturity_false_alarm_is_suppressed():
    result = DiagnosisService().run(
        DiagnosisInput(
            analytics=analytics(ndmi=0.2, ndre=0.3, nitrogen=2.0, balance=0, stage="Maturity", criticality="LOW"),
            quality_tag="HIGH", sowing_date_quality="known",
        )
    )
    assert result.verdict == "NORMAL_MATURITY"
    assert result.false_alarm_suppressed is True
