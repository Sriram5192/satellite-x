from datetime import datetime, timezone

import pytest

from satellite_x.identity import IdentityStore
from satellite_x.security import ArtifactSigner
from satellite_x.yielding import (
    YieldModelHumanApproval,
    YieldTrainingInput,
    YieldTrainingService,
    candidate_digest,
)


NOW = datetime.now(timezone.utc)


def records():
    rows = []
    for season in ["2024-kharif", "2025-kharif"]:
        for i in range(50):
            ndvi = 0.2 + (i % 25) * 0.02
            rain = 300 + (i * 17 % 200)
            value = 200 + 700 * ndvi + 0.4 * rain + ((i % 3) - 1) * 2
            rows.append({
                "field_id": f"{season}-F{i}", "crop_type": "chilli", "district_code": "GNT",
                "season": season, "yield_kg_per_acre": value,
                "features": {"ndvi_peak": ndvi, "rain_mm": rain},
                "verification_source": "crop_cutting_experiment",
                "evidence_reference": f"CCE-{season}-{i}",
            })
    return rows


def test_verified_yield_training_is_season_held_out_and_human_gated(tmp_path):
    signer = ArtifactSigner.generate()
    service = YieldTrainingService(candidate_signer=signer)
    candidate = service.train(YieldTrainingInput(crop_type="chilli", district_code="GNT", dataset_purpose="deterministic_validation_fixture", records=records()))
    assert candidate.training_records == 100
    assert candidate.independent_seasons == 2
    assert candidate.validation_method == "leave_one_season_out"
    assert candidate.validation_r2 > 0.99
    assert candidate.production_authorized is False
    assert candidate.status == "validation_fixture_only"
    approval = YieldModelHumanApproval(
        model_id="YIELD-GNT-CHILLI-1", approved_by="AGRONOMIST-1", approved_at=NOW,
        validation_report_reference="REPORT-1",
        accepted_candidate_sha256=candidate_digest(candidate),
    )
    identity = IdentityStore(tmp_path / "identity.db"); identity.initialize()
    identity.register("AGRONOMIST-1", "agronomist password", role="agronomist", now=NOW)
    token = identity.login("AGRONOMIST-1", "agronomist password", now=NOW)
    with pytest.raises(ValueError, match="cannot be approved"):
        service.approve(candidate, approval, identity, token)

    production_contract_candidate = candidate.model_copy(update={
        "dataset_purpose": "production_verified",
        "status": "candidate_requires_human_approval",
        "model_signature": None,
    })
    production_signature = signer.sign(
        artifact_type="yield_model_candidate",
        artifact_id=production_contract_candidate.candidate_id,
        payload=production_contract_candidate.signature_payload(),
        parent_sha256=[production_contract_candidate.dataset_sha256],
        issued_at=production_contract_candidate.generated_at,
    )
    production_contract_candidate = production_contract_candidate.model_copy(
        update={"model_signature": production_signature}
    )
    contract_approval = approval.model_copy(update={
        "accepted_candidate_sha256": candidate_digest(production_contract_candidate)
    })
    model = service.approve(
        production_contract_candidate, contract_approval, identity, token
    )
    assert model.validation_r2 == candidate.validation_r2
    assert model.approval_signature is not None
    assert model.prediction_interval_half_width_kg_per_acre == candidate.validation_abs_residual_q95_kg_per_acre


def test_production_training_rejects_unsigned_labels():
    service = YieldTrainingService(candidate_signer=ArtifactSigner.generate())
    with pytest.raises(ValueError, match="trusted label issuer keys"):
        service.train(YieldTrainingInput(
            crop_type="chilli", district_code="GNT",
            dataset_purpose="production_verified", records=records(),
        ))


def test_yield_training_rejects_duplicate_field_season():
    rows = records()
    rows[-1] = rows[0]
    with pytest.raises(ValueError, match="duplicate"):
        YieldTrainingInput(crop_type="chilli", district_code="GNT", dataset_purpose="deterministic_validation_fixture", records=rows)
