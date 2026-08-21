"""Orchestration for location preflight, FTW recovery, and confirmation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from ..cache import JsonCache
from ..config import Settings
from ..http import JsonHttpClient
from ..models import utc_now
from .errors import BoundaryValidationError, FtwQueryError, LocationPreflightError
from .ftw import FtwRepository
from .geometry import normalize_and_validate
from .location import LocationPreflightClient
from .models import (
    BoundaryConfirmation,
    PolygonRecoveryInput,
    PolygonRecoveryResult,
)
from .scoring import score_candidates


class PolygonRecoveryService:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http: JsonHttpClient | None = None,
        location_client: LocationPreflightClient | None = None,
        ftw_repository: FtwRepository | None = None,
        clock: Callable[[], datetime] = utc_now,
    ):
        self.settings = settings or Settings.from_env()
        self.http = http or JsonHttpClient(self.settings)
        self._owns_http = http is None
        cache = JsonCache(self.settings.cache_dir)
        self.location_client = location_client or LocationPreflightClient(
            self.http, cache, self.settings
        )
        self.ftw_repository = ftw_repository or FtwRepository(self.settings)
        self.clock = clock

    def recover(self, request: PolygonRecoveryInput) -> PolygonRecoveryResult:
        checked_at = self.clock()
        try:
            location = self.location_client.check(request)
        except LocationPreflightError as exc:
            return PolygonRecoveryResult(
                request=request,
                checked_at=checked_at,
                status="preflight_unavailable",
                reason_codes=["LOCATION_PREFLIGHT_UNAVAILABLE"],
                warnings=[str(exc)],
            )

        if location.country_code and location.country_code != request.country_code:
            return PolygonRecoveryResult(
                request=request,
                checked_at=checked_at,
                status="rejected_location",
                location=location,
                reason_codes=["COUNTRY_CODE_MISMATCH"],
                warnings=[
                    f"Requested country {request.country_code}, but reverse location returned "
                    f"{location.country_code}."
                ],
            )
        if location.blocking:
            return PolygonRecoveryResult(
                request=request,
                checked_at=checked_at,
                status="rejected_location",
                location=location,
                reason_codes=[location.reason_code],
                warnings=[
                    "Location preflight blocked automatic polygon recovery. "
                    "Correct the GPS point or provide an official/user-drawn boundary."
                ],
            )

        subdivision = request.subdivision_code or location.subdivision_code
        if not subdivision:
            return PolygonRecoveryResult(
                request=request,
                checked_at=checked_at,
                status="preflight_unavailable",
                location=location,
                reason_codes=["SUBDIVISION_UNRESOLVED"],
                warnings=[
                    "State/subdivision could not be inferred; supply subdivision_code."
                ],
            )
        effective_request = request.model_copy(update={"subdivision_code": subdivision})
        try:
            records = self.ftw_repository.query(effective_request)
            candidates = score_candidates(records, effective_request, self.settings)
        except (FtwQueryError, BoundaryValidationError) as exc:
            return PolygonRecoveryResult(
                request=effective_request,
                checked_at=checked_at,
                status="preflight_unavailable",
                location=location,
                reason_codes=["FTW_QUERY_OR_GEOMETRY_FAILURE"],
                warnings=[str(exc)],
            )

        if not candidates:
            return PolygonRecoveryResult(
                request=effective_request,
                checked_at=checked_at,
                status="no_candidate",
                location=location,
                reason_codes=["NO_FTW_POLYGON_MATCH"],
                warnings=[
                    "No FTW polygon passed GPS containment/tolerance and acreage gates. "
                    "Use official FMB import, manual drawing, or local AI inference."
                ],
            )
        warnings = [
            "The reverse-location gate is a proximity heuristic, not proof of cropland or ownership.",
            "FTW candidates are remote-sensing field units, not legal/cadastral parcels.",
            "A candidate becomes operational only after explicit user confirmation.",
        ]
        if any(item.source_confidence is None for item in candidates):
            warnings.append(
                "FTW source confidence is unavailable for one or more candidates; "
                "the transparent GPS/acreage score is used instead."
            )
        return PolygonRecoveryResult(
            request=effective_request,
            checked_at=checked_at,
            status="candidates_found",
            location=location,
            candidates=candidates,
            selected_candidate_id=candidates[0].candidate_id,
            reason_codes=["FTW_CANDIDATES_FOUND"],
            warnings=warnings,
        )

    def confirm_candidate(
        self, result: PolygonRecoveryResult, candidate_id: str
    ) -> BoundaryConfirmation:
        candidate = next(
            (item for item in result.candidates if item.candidate_id == candidate_id),
            None,
        )
        if candidate is None:
            raise BoundaryValidationError(f"candidate not found: {candidate_id}")
        normalized, validation = normalize_and_validate(
            candidate.geometry_geojson, result.request
        )
        if not validation.valid:
            raise BoundaryValidationError(
                "candidate does not contain the GPS point within tolerance"
            )
        return BoundaryConfirmation(
            field_id=result.request.field_id,
            confirmed_at=self.clock(),
            boundary_source=candidate.source,
            source_candidate_id=candidate.candidate_id,
            boundary_geojson=normalized,
            validation=validation,
            user_confirmed=True,
            legal_boundary=False,
            provenance={
                "model": candidate.model_name,
                "prediction_year": candidate.year,
                "source_confidence": candidate.source_confidence,
                "recovery_score_pct": candidate.score_pct,
                "legal_disclaimer": "Remote-sensing field unit; not a cadastral title boundary.",
            },
        )

    def confirm_uploaded_or_drawn(
        self,
        request: PolygonRecoveryInput,
        geometry_geojson: dict[str, Any],
        *,
        source: Literal["user_drawn", "official_fmb"],
    ) -> BoundaryConfirmation:
        normalized, validation = normalize_and_validate(geometry_geojson, request)
        if not validation.valid:
            raise BoundaryValidationError(
                "boundary does not contain the GPS point within tolerance"
            )
        return BoundaryConfirmation(
            field_id=request.field_id,
            confirmed_at=self.clock(),
            boundary_source=source,
            source_candidate_id=None,
            boundary_geojson=normalized,
            validation=validation,
            user_confirmed=True,
            legal_boundary=False,
            provenance={
                "source": source,
                "user_confirmation_required": True,
                "survey_verification_required": source == "official_fmb",
                "verification_status": (
                    "unverified_document_upload"
                    if source == "official_fmb"
                    else "user_confirmed_operational_boundary"
                ),
                "legal_disclaimer": (
                    "An uploaded FMB becomes legal_boundary=true only after an "
                    "authorized record/survey verification step."
                    if source == "official_fmb"
                    else "User-drawn operational field; not a cadastral title boundary."
                ),
            },
        )

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> "PolygonRecoveryService":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
