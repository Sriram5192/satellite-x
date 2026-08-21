"""Command-line entry point for SATELLITE-X field intelligence and governance."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .acquisition.pipeline import AcquisitionPipeline
from .ai.errors import DiagnosisError
from .ai.models import DiagnosisInput, DiagnosisResult
from .ai.service import DiagnosisService
from .analytics.errors import AnalyticsError
from .analytics.models import AnalyticsInput, AnalyticsResult
from .analytics.service import AnalyticsService
from .analytics.timeseries import TimeSeriesInput, TimeSeriesResult, TimeSeriesService
from .capabilities import capability_registry
from .communications import (
    AtmosphericLossInput, AtmosphericLossResult, AtmosphericLossService,
    DynamicContactScheduler, LinkBudgetInput, LinkBudgetResult, LinkBudgetService,
    TrafficSimulationInput, TrafficSimulationResult,
)
from .config import Settings
from .errors import SatelliteXError
from .government.models import AreaSummary
from .government.offline_sync import OfflineEvidenceEnvelope
from .governance.authoritative import (
    AuthoritativeGovernanceStore, AuthoritativePolicyGateway, CaseRecord,
)
from .governance.models import AccessRequest, GovernmentAuthorization
from .integrations.government import GovernmentConnectorResult, GovernmentFetchInput, GovernmentRecordGateway
from .integrations.otp import OtpChallengeReceipt, OtpVerification
from .identity import IdentityStore
from .iot_security import verify_hmac_sha256
from .models import FarmInput, IoTReading, RawDataContainer
from .orbit import (
    CelesTrakTleClient, GroundStation, PassPredictionInput,
    PassPredictionResult, PassPredictionService, SceneOrbitProvenance,
    TleRecord, validate_scene_orbit,
)
from .polygon.errors import PolygonRecoveryError
from .polygon.models import (
    BoundaryConfirmation,
    PolygonRecoveryInput,
    PolygonRecoveryResult,
)
from .polygon.service import PolygonRecoveryService
from .preprocessing.errors import PreprocessingError
from .preprocessing.models import (
    PreprocessingInput,
    PreprocessingResult,
    SarFallbackInput,
    SarFallbackResult,
)
from .preprocessing.sar import SarFallbackService
from .preprocessing.service import PreprocessingService
from .recommendations.management_zones import ManagementZoneResult, ManagementZoneService
from .recommendations.machinery import EquipmentProfile, MachineryTransferResult, MachineryTransferService, OperatorApproval
from .recommendations.prescription import ApprovedPrescription, PrescriptionApproval, PrescriptionService
from .resilience import ResilienceDecision, ResilienceInput, ResilienceService
from .security import ArtifactSigner, SignedArtifact
from .yielding import YieldEstimateResult, YieldModelCandidate, YieldTrainingInput, YieldTrainingService


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _trusted_issuer_keys() -> dict[str, str]:
    value = os.getenv("SATELLITE_X_TRUSTED_ISSUER_KEYS_JSON")
    if not value:
        raise ValueError("SATELLITE_X_TRUSTED_ISSUER_KEYS_JSON is required")
    payload = json.loads(value)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("SATELLITE_X_TRUSTED_ISSUER_KEYS_JSON must be a non-empty object")
    return {str(key): str(public) for key, public in payload.items()}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="satellite-x",
        description="SATELLITE-X transparent field intelligence, governance, and offline verification engine",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    acquire = sub.add_parser("acquire", help="run all Set 1 sources")
    acquire.add_argument("--input", type=Path, required=True, help="farm input JSON")
    acquire.add_argument("--iot", type=Path, help="optional ESP32 payload JSON")
    acquire.add_argument(
        "--iot-signature",
        help="HMAC-SHA256 of the exact IoT file bytes (secret comes from SATELLITE_X_IOT_HMAC_SECRET)",
    )
    acquire.add_argument("--output", type=Path, required=True, help="result JSON")

    validate = sub.add_parser("validate-iot", help="validate an ESP32 payload")
    validate.add_argument("--input", type=Path, required=True)

    register = sub.add_parser("identity-register", help="register an account using password from SATELLITE_X_INITIAL_PASSWORD")
    register.add_argument("--db", type=Path, required=True)
    register.add_argument("--user-id", required=True)
    register.add_argument(
        "--role",
        choices=["farmer", "government_officer", "investigator", "admin", "agronomist", "machinery_operator"],
        required=True,
    )

    link = sub.add_parser("identity-link-field", help="link a hashed BoundaryConfirmation to an existing farmer")
    link.add_argument("--db", type=Path, required=True)
    link.add_argument("--user-id", required=True)
    link.add_argument("--confirmation", type=Path, required=True)

    recover = sub.add_parser(
        "recover-polygon", help="find open FTW field-boundary candidates"
    )
    recover.add_argument("--input", type=Path, required=True)
    recover.add_argument("--output", type=Path, required=True)

    confirm = sub.add_parser(
        "confirm-polygon", help="confirm a candidate from a recovery result"
    )
    confirm.add_argument("--recovery", type=Path, required=True)
    confirm.add_argument("--candidate-id", required=True)
    confirm.add_argument("--output", type=Path, required=True)

    drawn = sub.add_parser(
        "confirm-drawn", help="validate and confirm user-drawn or official geometry"
    )
    drawn.add_argument("--input", type=Path, required=True, help="recovery request JSON")
    drawn.add_argument("--geometry", type=Path, required=True, help="Polygon GeoJSON")
    drawn.add_argument("--source", choices=["user_drawn", "official_fmb"], required=True)
    drawn.add_argument("--output", type=Path, required=True)

    preprocess = sub.add_parser(
        "preprocess-field", help="run Set 2 SCL quality, scene selection and urban gate"
    )
    preprocess.add_argument("--input", type=Path, required=True)
    preprocess.add_argument("--output", type=Path, required=True)

    analyze = sub.add_parser("analyze-field", help="run Set 3 indices, phenology and water balance")
    analyze.add_argument("--preprocessing", type=Path, required=True)
    analyze.add_argument("--set1", type=Path, required=True)
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument(
        "--sowing-date-quality",
        choices=["known", "approximate_month", "unknown"],
        default="known",
    )

    timeseries = sub.add_parser("analyze-timeseries", help="summarize crop-aware multi-scene Set 3 trends")
    timeseries.add_argument("--input", type=Path, required=True)
    timeseries.add_argument("--output", type=Path, required=True)

    diagnose = sub.add_parser("diagnose-field", help="run Set 4 differential diagnosis")
    diagnose.add_argument("--analytics", type=Path, required=True)
    diagnose.add_argument("--quality", choices=["HIGH", "MEDIUM", "LOW"], required=True)
    diagnose.add_argument(
        "--sowing-date-quality",
        choices=["known", "approximate_month", "unknown"],
        default="known",
    )
    diagnose.add_argument("--output", type=Path, required=True)

    sar = sub.add_parser("sar-fallback", help="run cloud-independent Sentinel-1 RTC field summary")
    sar.add_argument("--input", type=Path, required=True)
    sar.add_argument("--output", type=Path, required=True)

    resilience = sub.add_parser("resilience-route", help="route optical/SAR evidence without fabricating indices")
    resilience.add_argument("--preprocessing", type=Path, required=True)
    resilience.add_argument("--sar", type=Path)
    resilience.add_argument("--output", type=Path, required=True)

    zones = sub.add_parser("management-zones", help="build experimental relative-NDVI zones")
    zones.add_argument("--preprocessing", type=Path, required=True)
    zones.add_argument("--output", type=Path, required=True)

    prescription = sub.add_parser("approve-prescription", help="attach human-approved rates without authorizing machinery")
    prescription.add_argument("--zones", type=Path, required=True)
    prescription.add_argument("--approval", type=Path, required=True)
    prescription.add_argument("--identity-db", type=Path, required=True)
    prescription.add_argument("--output", type=Path, required=True)

    machinery = sub.add_parser("machinery-transfer", help="build operator-approved non-automatic transfer package")
    machinery.add_argument("--prescription", type=Path, required=True)
    machinery.add_argument("--equipment", type=Path, required=True)
    machinery.add_argument("--operator", type=Path, required=True)
    machinery.add_argument("--identity-db", type=Path, required=True)
    machinery.add_argument("--output", type=Path, required=True)

    yield_train = sub.add_parser("train-yield-candidate", help="train season-held-out candidate from verified labels")
    yield_train.add_argument("--input", type=Path, required=True)
    yield_train.add_argument("--output", type=Path, required=True)

    government_fetch = sub.add_parser("government-fetch", help="call an authorization-gated official JSON API")
    government_fetch.add_argument("--input", type=Path, required=True)
    government_fetch.add_argument("--governance-db", type=Path, required=True)
    government_fetch.add_argument("--output", type=Path, required=True)

    store_auth = sub.add_parser("governance-store-authorization", help="store a signed authoritative government authorization")
    store_auth.add_argument("--governance-db", type=Path, required=True)
    store_auth.add_argument("--authorization", type=Path, required=True)
    store_auth.add_argument("--signature", type=Path, required=True)

    store_case = sub.add_parser("governance-store-case", help="store a signed investigation case")
    store_case.add_argument("--governance-db", type=Path, required=True)
    store_case.add_argument("--case", type=Path, required=True)
    store_case.add_argument("--signature", type=Path, required=True)

    serve = sub.add_parser("serve-api", help="serve authenticated OTP/offline-sync API and PWA")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8080)

    fetch_tle = sub.add_parser("fetch-tle", help="fetch and checksum-validate a live CelesTrak TLE")
    fetch_tle.add_argument("--norad-id", type=int, required=True)
    fetch_tle.add_argument("--output", type=Path, required=True)

    predict_pass = sub.add_parser("predict-passes", help="predict SGP4 passes and dynamic Doppler")
    predict_pass.add_argument("--input", type=Path, required=True)
    predict_pass.add_argument("--output", type=Path, required=True)

    orbit_check = sub.add_parser("validate-scene-orbit", help="check selected Sentinel scene against TLE epoch policy")
    orbit_check.add_argument("--preprocessing", type=Path, required=True)
    orbit_check.add_argument("--tle", type=Path, required=True)
    orbit_check.add_argument("--output", type=Path, required=True)

    atmosphere = sub.add_parser("atmospheric-loss", help="run ITU-R slant-path attenuation contributions")
    atmosphere.add_argument("--input", type=Path, required=True)
    atmosphere.add_argument("--output", type=Path, required=True)

    link_budget = sub.add_parser("link-budget", help="compute calibrated thermal-noise link budget and Doppler")
    link_budget.add_argument("--input", type=Path, required=True)
    link_budget.add_argument("--output", type=Path, required=True)

    traffic = sub.add_parser("simulate-contact-traffic", help="run scheduled-contact dynamic channel DES")
    traffic.add_argument("--input", type=Path, required=True)
    traffic.add_argument("--output", type=Path, required=True)

    capabilities = sub.add_parser("capability-status", help="export honest external activation gates")
    capabilities.add_argument("--output", type=Path, required=True)

    schemas = sub.add_parser("export-schemas", help="write JSON schemas")
    schemas.add_argument("--directory", type=Path, default=Path("schemas"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-iot":
            reading = IoTReading.model_validate(_read_json(args.input))
            print(reading.model_dump_json(indent=2))
            return 0

        if args.command == "identity-register":
            password = os.getenv("SATELLITE_X_INITIAL_PASSWORD")
            if not password:
                raise ValueError("SATELLITE_X_INITIAL_PASSWORD is required")
            identity = IdentityStore(args.db)
            identity.initialize()
            identity.register(args.user_id, password, role=args.role)
            print(json.dumps({"status": "registered", "user_id": args.user_id, "role": args.role, "db": str(args.db)}, indent=2))
            return 0

        if args.command == "identity-link-field":
            identity = IdentityStore(args.db)
            identity.initialize()
            confirmation = BoundaryConfirmation.model_validate(_read_json(args.confirmation))
            digest = identity.link_confirmed_boundary(args.user_id, confirmation)
            print(json.dumps({"status": "linked", "user_id": args.user_id, "field_id": confirmation.field_id, "confirmation_sha256": digest}, indent=2))
            return 0

        if args.command == "serve-api":
            import uvicorn
            from .api import build_app_from_env
            uvicorn.run(build_app_from_env(), host=args.host, port=args.port)
            return 0

        if args.command == "capability-status":
            rows = [item.model_dump(mode="json") for item in capability_registry()]
            _write_json(args.output, {"capabilities": rows})
            print(json.dumps({"status": "written", "output": str(args.output), "count": len(rows)}, indent=2))
            return 0

        if args.command == "fetch-tle":
            result = CelesTrakTleClient().fetch(args.norad_id)
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": result.freshness, "norad_id": result.norad_id, "epoch": result.epoch.isoformat(), "output": str(args.output)}, indent=2))
            return 0 if result.freshness == "fresh" else 3

        if args.command == "predict-passes":
            request = PassPredictionInput.model_validate(_read_json(args.input))
            result = PassPredictionService().run(request)
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": result.status, "pass_count": len(result.passes), "output": str(args.output)}, indent=2))
            return 0 if result.status in {"accepted", "no_pass"} else 3

        if args.command == "validate-scene-orbit":
            preprocessing = PreprocessingResult.model_validate(_read_json(args.preprocessing))
            tle = TleRecord.model_validate(_read_json(args.tle))
            result = validate_scene_orbit(preprocessing, tle)
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": result.status, "usable": result.usable_for_pass_validation, "output": str(args.output)}, indent=2))
            return 0 if result.usable_for_pass_validation else 3

        if args.command == "atmospheric-loss":
            result = AtmosphericLossService().run(AtmosphericLossInput.model_validate(_read_json(args.input)))
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": "modeled_not_beacon_calibrated", "total_db": result.combined_total_db, "output": str(args.output)}, indent=2))
            return 0

        if args.command == "link-budget":
            result = LinkBudgetService().run(LinkBudgetInput.model_validate(_read_json(args.input)))
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": result.status, "margin_db": result.link_margin_db, "doppler_hz": result.doppler_shift_hz, "output": str(args.output)}, indent=2))
            return 0 if result.status == "margin_positive" else 3

        if args.command == "simulate-contact-traffic":
            result = DynamicContactScheduler().run(TrafficSimulationInput.model_validate(_read_json(args.input)))
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": "simulated", "completed": result.completed_requests, "dropped": result.dropped_requests, "utilization_pct": result.channel_utilization_pct, "output": str(args.output)}, indent=2))
            return 0

        if args.command in {"governance-store-authorization", "governance-store-case"}:
            store = AuthoritativeGovernanceStore(
                args.governance_db, trusted_public_keys=_trusted_issuer_keys()
            )
            store.initialize()
            signed = SignedArtifact.model_validate(_read_json(args.signature))
            if args.command == "governance-store-authorization":
                authorization = GovernmentAuthorization.model_validate(
                    _read_json(args.authorization)
                )
                store.save_authorization(authorization, signed)
                stored_id = authorization.authorization_id
            else:
                case = CaseRecord.model_validate(_read_json(args.case))
                store.save_case(case, signed)
                stored_id = case.case_id
            print(json.dumps({"status": "stored_signed", "id": stored_id}, indent=2))
            return 0

        if args.command == "government-fetch":
            request = GovernmentFetchInput.model_validate(_read_json(args.input))
            store = AuthoritativeGovernanceStore(
                args.governance_db, trusted_public_keys=_trusted_issuer_keys()
            )
            store.initialize()
            result = GovernmentRecordGateway(
                request.config,
                authoritative_policy=AuthoritativePolicyGateway(store),
            ).fetch(
                user=request.user,
                access=request.access,
                authorization=request.authorization,
                resource_path=request.resource_path,
                params=request.params,
            )
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": result.status, "reason_code": result.reason_code, "output": str(args.output)}, indent=2))
            return 0 if result.status == "allowed" else 3

        if args.command == "export-schemas":
            args.directory.mkdir(parents=True, exist_ok=True)
            _write_json(args.directory / "farm_input.schema.json", FarmInput.model_json_schema())
            _write_json(args.directory / "iot_reading.schema.json", IoTReading.model_json_schema())
            _write_json(
                args.directory / "raw_data_container.schema.json",
                RawDataContainer.model_json_schema(),
            )
            _write_json(
                args.directory / "polygon_recovery_input.schema.json",
                PolygonRecoveryInput.model_json_schema(),
            )
            _write_json(
                args.directory / "polygon_recovery_result.schema.json",
                PolygonRecoveryResult.model_json_schema(),
            )
            _write_json(
                args.directory / "boundary_confirmation.schema.json",
                BoundaryConfirmation.model_json_schema(),
            )
            _write_json(
                args.directory / "preprocessing_input.schema.json",
                PreprocessingInput.model_json_schema(),
            )
            _write_json(
                args.directory / "preprocessing_result.schema.json",
                PreprocessingResult.model_json_schema(),
            )
            _write_json(
                args.directory / "analytics_result.schema.json",
                AnalyticsResult.model_json_schema(),
            )
            _write_json(
                args.directory / "diagnosis_result.schema.json",
                DiagnosisResult.model_json_schema(),
            )
            _write_json(
                args.directory / "sar_fallback_result.schema.json",
                SarFallbackResult.model_json_schema(),
            )
            for filename, model in [
                ("timeseries_result.schema.json", TimeSeriesResult),
                ("management_zone_result.schema.json", ManagementZoneResult),
                ("approved_prescription.schema.json", ApprovedPrescription),
                ("yield_estimate_result.schema.json", YieldEstimateResult),
                ("government_authorization.schema.json", GovernmentAuthorization),
                ("government_access_request.schema.json", AccessRequest),
                ("area_summary.schema.json", AreaSummary),
                ("offline_evidence_envelope.schema.json", OfflineEvidenceEnvelope),
                ("resilience_decision.schema.json", ResilienceDecision),
                ("yield_model_candidate.schema.json", YieldModelCandidate),
                ("machinery_transfer_result.schema.json", MachineryTransferResult),
                ("government_connector_result.schema.json", GovernmentConnectorResult),
                ("government_fetch_input.schema.json", GovernmentFetchInput),
                ("otp_challenge_receipt.schema.json", OtpChallengeReceipt),
                ("otp_verification.schema.json", OtpVerification),
                ("tle_record.schema.json", TleRecord),
                ("pass_prediction_result.schema.json", PassPredictionResult),
                ("scene_orbit_provenance.schema.json", SceneOrbitProvenance),
                ("atmospheric_loss_result.schema.json", AtmosphericLossResult),
                ("link_budget_result.schema.json", LinkBudgetResult),
                ("traffic_simulation_result.schema.json", TrafficSimulationResult),
            ]:
                _write_json(args.directory / filename, model.model_json_schema())
            print(f"Exported schemas to {args.directory}")
            return 0

        if args.command == "recover-polygon":
            request = PolygonRecoveryInput.model_validate(_read_json(args.input))
            with PolygonRecoveryService(Settings.from_env()) as service:
                result = service.recover(request)
            _write_json(args.output, result.model_dump(mode="json"))
            print(
                json.dumps(
                    {
                        "status": result.status,
                        "output": str(args.output),
                        "candidate_count": len(result.candidates),
                        "selected_candidate_id": result.selected_candidate_id,
                        "reason_codes": result.reason_codes,
                    },
                    indent=2,
                )
            )
            return 0 if result.status == "candidates_found" else 3

        if args.command == "confirm-polygon":
            recovery = PolygonRecoveryResult.model_validate(_read_json(args.recovery))
            with PolygonRecoveryService(Settings.from_env()) as service:
                confirmed = service.confirm_candidate(recovery, args.candidate_id)
            _write_json(args.output, confirmed.model_dump(mode="json"))
            print(json.dumps({"status": "confirmed", "output": str(args.output)}, indent=2))
            return 0

        if args.command == "confirm-drawn":
            request = PolygonRecoveryInput.model_validate(_read_json(args.input))
            geometry_payload = _read_json(args.geometry)
            geometry = (
                geometry_payload["geometry"]
                if geometry_payload.get("type") == "Feature"
                else geometry_payload
            )
            with PolygonRecoveryService(Settings.from_env()) as service:
                confirmed = service.confirm_uploaded_or_drawn(
                    request, geometry, source=args.source
                )
            _write_json(args.output, confirmed.model_dump(mode="json"))
            print(json.dumps({"status": "confirmed", "output": str(args.output)}, indent=2))
            return 0

        if args.command == "preprocess-field":
            request = PreprocessingInput.model_validate(_read_json(args.input))
            with PreprocessingService(Settings.from_env()) as service:
                result = service.run(request)
            _write_json(args.output, result.model_dump(mode="json"))
            print(
                json.dumps(
                    {
                        "status": result.status,
                        "output": str(args.output),
                        "selected_scene_id": (
                            result.selected_scene.scene_id
                            if result.selected_scene
                            else None
                        ),
                        "quality": (
                            result.selected_quality.quality
                            if result.selected_quality
                            else None
                        ),
                        "expanded_search_used": result.expanded_search_used,
                    },
                    indent=2,
                )
            )
            return 0 if result.status == "accepted" else 3

        if args.command == "analyze-field":
            preprocessing = PreprocessingResult.model_validate(
                _read_json(args.preprocessing)
            )
            raw = RawDataContainer.model_validate(_read_json(args.set1))
            analytics_input = AnalyticsInput(
                field_id=raw.field.field_id,
                crop_type=raw.field.crop_type,
                sowing_date=raw.field.sowing_date,
                sowing_date_quality=args.sowing_date_quality,
                preprocessing=preprocessing,
                weather=raw.weather,
                soil=raw.soil,
            )
            result = AnalyticsService().run(analytics_input)
            _write_json(args.output, result.model_dump(mode="json"))
            print(
                json.dumps(
                    {
                        "status": "computed",
                        "output": str(args.output),
                        "scene_id": result.scene_id,
                        "ndvi_mean": result.indices["ndvi"].mean,
                        "stage": result.phenology.stage_name,
                        "water_balance_mm": result.water_balance.water_balance_15d_mm,
                    },
                    indent=2,
                )
            )
            return 0

        if args.command == "analyze-timeseries":
            request = TimeSeriesInput.model_validate(_read_json(args.input))
            result = TimeSeriesService().run(request)
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": "analyzed", "output": str(args.output), "quality": result.quality, "observations": result.observation_count}, indent=2))
            return 0

        if args.command == "diagnose-field":
            analytics = AnalyticsResult.model_validate(_read_json(args.analytics))
            result = DiagnosisService().run(
                DiagnosisInput(
                    analytics=analytics,
                    quality_tag=args.quality,
                    sowing_date_quality=args.sowing_date_quality,
                )
            )
            _write_json(args.output, result.model_dump(mode="json"))
            print(
                json.dumps(
                    {
                        "status": "diagnosed",
                        "output": str(args.output),
                        "verdict": result.verdict,
                        "confidence_pct": result.confidence.final_confidence_pct,
                        "confidence_tag": result.confidence_tag,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        if args.command == "resilience-route":
            optical = PreprocessingResult.model_validate(_read_json(args.preprocessing))
            sar = SarFallbackResult.model_validate(_read_json(args.sar)) if args.sar else None
            result = ResilienceService().run(
                ResilienceInput(field_id=optical.request.field_id, optical=optical, sar=sar)
            )
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": result.status, "output": str(args.output), "diagnosis_allowed": result.diagnosis_allowed}, indent=2))
            return 0

        if args.command == "train-yield-candidate":
            request = YieldTrainingInput.model_validate(_read_json(args.input))
            private_key = os.getenv("SATELLITE_X_ARTIFACT_SIGNING_KEY_BASE64")
            if not private_key:
                raise ValueError("SATELLITE_X_ARTIFACT_SIGNING_KEY_BASE64 is required")
            trusted_label_keys = json.loads(
                os.getenv("SATELLITE_X_TRUSTED_LABEL_KEYS_JSON", "{}")
            )
            result = YieldTrainingService(
                candidate_signer=ArtifactSigner.from_private_key_base64(private_key),
                trusted_label_keys=trusted_label_keys,
            ).train(request)
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": result.status, "output": str(args.output), "validation_r2": result.validation_r2}, indent=2))
            return 0

        if args.command == "management-zones":
            preprocessing = PreprocessingResult.model_validate(_read_json(args.preprocessing))
            result = ManagementZoneService().run(preprocessing)
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": result.status, "output": str(args.output), "zones": len(result.zones)}, indent=2))
            return 0

        if args.command == "approve-prescription":
            zones = ManagementZoneResult.model_validate(_read_json(args.zones))
            approval = PrescriptionApproval.model_validate(_read_json(args.approval))
            token = os.getenv("SATELLITE_X_SESSION_TOKEN")
            if not token:
                raise ValueError("SATELLITE_X_SESSION_TOKEN is required")
            identity = IdentityStore(args.identity_db); identity.initialize()
            private_key = os.getenv("SATELLITE_X_ARTIFACT_SIGNING_KEY_BASE64")
            if not private_key:
                raise ValueError("SATELLITE_X_ARTIFACT_SIGNING_KEY_BASE64 is required")
            result = PrescriptionService().approve(
                zones, approval, identity, token,
                ArtifactSigner.from_private_key_base64(private_key),
            )
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": result.status, "output": str(args.output), "machinery_execution_authorized": result.machinery_execution_authorized}, indent=2))
            return 0

        if args.command == "machinery-transfer":
            prescription = ApprovedPrescription.model_validate(_read_json(args.prescription))
            equipment = EquipmentProfile.model_validate(_read_json(args.equipment))
            operator = OperatorApproval.model_validate(_read_json(args.operator))
            token = os.getenv("SATELLITE_X_SESSION_TOKEN")
            if not token:
                raise ValueError("SATELLITE_X_SESSION_TOKEN is required")
            identity = IdentityStore(args.identity_db); identity.initialize()
            private_key = os.getenv("SATELLITE_X_ARTIFACT_SIGNING_KEY_BASE64")
            if not private_key:
                raise ValueError("SATELLITE_X_ARTIFACT_SIGNING_KEY_BASE64 is required")
            trusted_approval_keys = json.loads(
                os.getenv("SATELLITE_X_TRUSTED_APPROVAL_KEYS_JSON", "{}")
            )
            if not trusted_approval_keys:
                raise ValueError("SATELLITE_X_TRUSTED_APPROVAL_KEYS_JSON is required")
            result = MachineryTransferService().build(
                prescription, equipment, operator, identity, token,
                ArtifactSigner.from_private_key_base64(private_key),
                trusted_approval_keys,
            )
            _write_json(args.output, result.model_dump(mode="json"))
            print(json.dumps({"status": result.status, "output": str(args.output), "automatic_execution_authorized": result.automatic_execution_authorized}, indent=2))
            return 0

        if args.command == "sar-fallback":
            request = SarFallbackInput.model_validate(_read_json(args.input))
            with SarFallbackService(Settings.from_env()) as service:
                result = service.run(request)
            _write_json(args.output, result.model_dump(mode="json"))
            print(
                json.dumps(
                    {
                        "status": result.status,
                        "output": str(args.output),
                        "scene_id": result.scene_id,
                        "valid_pixels": result.valid_pixels,
                    },
                    indent=2,
                )
            )
            return 0 if result.status == "accepted" else 3

        field = FarmInput.model_validate(_read_json(args.input))
        iot = None
        iot_verified = False
        if args.iot:
            iot_bytes = args.iot.read_bytes()
            raw_iot = json.loads(iot_bytes.decode("utf-8"))
            if not isinstance(raw_iot, dict):
                raise ValueError(f"{args.iot} must contain a JSON object")
            iot = IoTReading.model_validate(raw_iot)
            if args.iot_signature:
                secret = os.getenv("SATELLITE_X_IOT_HMAC_SECRET", "")
                if not secret:
                    raise ValueError(
                        "SATELLITE_X_IOT_HMAC_SECRET is required with --iot-signature"
                    )
                if not verify_hmac_sha256(iot_bytes, args.iot_signature, secret):
                    raise ValueError("invalid IoT HMAC-SHA256 signature")
                iot_verified = True
        elif args.iot_signature:
            raise ValueError("--iot-signature requires --iot")

        settings = Settings.from_env()
        with AcquisitionPipeline(settings) as pipeline:
            result = pipeline.run(field, iot, iot_verified=iot_verified)
        _write_json(args.output, result.model_dump(mode="json"))
        summary = {
            "status": result.status,
            "output": str(args.output),
            "scene_id": result.satellite.scene.scene_id,
            "scene_provider": result.satellite.scene.provider,
            "weather_source": result.weather.source,
            "soil_source": result.soil.source,
            "iot_verified": result.iot_verified,
            "iot_fresh": result.iot_fresh,
            "warning_count": len(result.warnings),
        }
        print(json.dumps(summary, indent=2))
        return 0
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
        SatelliteXError,
        PolygonRecoveryError,
        PreprocessingError,
        AnalyticsError,
        DiagnosisError,
    ) as exc:
        print(
            json.dumps(
                {"status": "error", "error_type": type(exc).__name__, "detail": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
