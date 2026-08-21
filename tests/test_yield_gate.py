from datetime import datetime, timezone

from satellite_x.security import ArtifactSigner
from satellite_x.yielding import ApprovedYieldModel, YieldEstimateRequest, YieldService


NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


def test_yield_is_unavailable_without_validated_local_model():
    request = YieldEstimateRequest(field_id="F1", crop_type="chilli", district_code="GNT", season="kharif-2026", features={"ndvi": 0.4})
    result = YieldService().estimate(request)
    assert result.status == "unavailable_unvalidated_model"
    assert result.estimate_kg_per_acre is None
    assert result.production_authorized is False


def test_even_approved_model_output_remains_experimental():
    request = YieldEstimateRequest(field_id="F1", crop_type="chilli", district_code="GNT", season="kharif-2026", features={"ndvi": 0.4})
    model = ApprovedYieldModel(
        model_id="MODEL-1", crop_type="chilli", district_code="GNT",
        coefficients={"ndvi": 100}, intercept_kg_per_acre=500,
        residual_mae_kg_per_acre=50,
        prediction_interval_half_width_kg_per_acre=98,
        validation_r2=0.6,
        training_records=100, independent_seasons=2,
        approved_by="AGRONOMIST-1", approved_at=NOW,
        validation_report_reference="REPORT-1",
    )
    signer = ArtifactSigner.generate()
    signature = signer.sign(
        artifact_type="approved_yield_model", artifact_id=model.model_id,
        payload=model.signature_payload(), issued_at=NOW,
    )
    model = model.model_copy(update={"approval_signature": signature})
    result = YieldService(
        trusted_model_keys={signer.key_id: signer.public_key_base64}
    ).estimate(request, model)
    assert result.status == "experimental_human_review_required"
    assert result.estimate_kg_per_acre == 540
    assert result.production_authorized is False
