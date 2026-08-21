"""Set 2 orchestration: per-field SCL selection and calibrated urban gate."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

from ..config import Settings
from ..http import JsonHttpClient
from ..models import SatelliteScene, utc_now
from .catalog import SentinelCandidateCatalog
from .errors import RasterQualityError, SceneCatalogError
from .models import (
    PreprocessingInput,
    PreprocessingResult,
    SceneFieldQuality,
    UrbanGateResult,
)
from .quality import RasterQualityEvaluator

ScenePair = tuple[SatelliteScene, SceneFieldQuality]
SpectralPass = tuple[SatelliteScene, SceneFieldQuality, UrbanGateResult]


class PreprocessingService:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http: JsonHttpClient | None = None,
        catalog: SentinelCandidateCatalog | None = None,
        evaluator: RasterQualityEvaluator | None = None,
        clock: Callable[[], datetime] = utc_now,
    ):
        self.settings = settings or Settings.from_env()
        self.http = http or JsonHttpClient(self.settings)
        self._owns_http = http is None
        self.catalog = catalog or SentinelCandidateCatalog(self.http, self.settings)
        self.evaluator = evaluator or RasterQualityEvaluator()
        self.clock = clock

    def run(self, request: PreprocessingInput) -> PreprocessingResult:
        processed_at = self.clock()
        if request.location_blocking:
            return PreprocessingResult(
                request=request,
                processed_at=processed_at,
                status="rejected_location",
                warnings=[
                    request.location_reason
                    or "Location preflight blocked satellite preprocessing."
                ],
            )

        original_start = request.analysis_date - timedelta(
            days=request.scan_range_days - 1
        )
        warnings: list[str] = []
        all_pairs: list[ScenePair] = []
        urban_failures: list[SpectralPass] = []
        spectral_attempts = 0

        try:
            original_scenes = self.catalog.list_scenes(
                request, original_start, request.analysis_date
            )
        except SceneCatalogError as exc:
            return PreprocessingResult(
                request=request,
                processed_at=processed_at,
                status="processing_error",
                warnings=[str(exc)],
            )
        original_pairs, original_errors = self._evaluate_many(
            original_scenes, request, original_start
        )
        warnings.extend(original_errors)
        all_pairs.extend(original_pairs)
        selected, failures, attempts, spectral_warnings = self._try_spectral_candidates(
            original_pairs, request
        )
        urban_failures.extend(failures)
        spectral_attempts += attempts
        warnings.extend(spectral_warnings)

        expanded_used = False
        if selected is None:
            expanded_used = True
            expanded_start = original_start - timedelta(days=request.expansion_days)
            expanded_end = original_start - timedelta(days=1)
            try:
                expanded_scenes = self.catalog.list_scenes(
                    request, expanded_start, expanded_end
                )
            except SceneCatalogError as exc:
                expanded_scenes = []
                warnings.append(str(exc))
            expanded_pairs, expanded_errors = self._evaluate_many(
                expanded_scenes, request, original_start
            )
            warnings.extend(expanded_errors)
            all_pairs.extend(expanded_pairs)
            selected, failures, attempts, spectral_warnings = self._try_spectral_candidates(
                expanded_pairs, request
            )
            urban_failures.extend(failures)
            spectral_attempts += attempts
            warnings.extend(spectral_warnings)

        qualities = [quality for _, quality in all_pairs]
        qualities.sort(key=lambda item: item.acquired_at)
        if not all_pairs:
            return PreprocessingResult(
                request=request,
                processed_at=processed_at,
                status="no_satellite_scene",
                candidates=qualities,
                expanded_search_used=expanded_used,
                warnings=warnings or ["No complete Sentinel-2 scenes were found."],
            )
        if not any(quality.quality != "LOW" for _, quality in all_pairs):
            return PreprocessingResult(
                request=request,
                processed_at=processed_at,
                status="no_acceptable_scene",
                candidates=qualities,
                expanded_search_used=expanded_used,
                warnings=[
                    *warnings,
                    "Every candidate is LOW quality under the frozen field-valid/cloud rules.",
                ],
            )
        if selected is None:
            if urban_failures:
                scene, quality, urban = urban_failures[0]
                return PreprocessingResult(
                    request=request,
                    processed_at=processed_at,
                    status="urban_rejected",
                    selected_scene=scene,
                    selected_quality=quality,
                    urban_gate=urban,
                    candidates=qualities,
                    expanded_search_used=expanded_used,
                    warnings=[
                        *warnings,
                        "Every spectrally usable candidate met the frozen urban mean condition.",
                    ],
                )
            return PreprocessingResult(
                request=request,
                processed_at=processed_at,
                status="processing_error",
                candidates=qualities,
                expanded_search_used=expanded_used,
                warnings=[
                    *warnings,
                    f"{spectral_attempts} acceptable SCL candidate(s) were tested, but none "
                    f"reached both {self.settings.spectral_min_valid_pct:.1f}% and "
                    f"{self.settings.spectral_min_valid_pixels} calibrated spectral pixels.",
                ],
            )

        selected_scene, selected_quality, urban = selected
        if expanded_used:
            warnings.append(
                f"Original range had no spectrally usable non-urban scene; search expanded "
                f"by {request.expansion_days} days."
            )
        warnings.append(
            "Scene passed SCL quality, calibrated spectral-validity, and NDBI/NDVI mean gates."
        )
        return PreprocessingResult(
            request=request,
            processed_at=processed_at,
            status="accepted",
            selected_scene=selected_scene,
            selected_quality=selected_quality,
            urban_gate=urban,
            candidates=qualities,
            expanded_search_used=expanded_used,
            warnings=warnings,
        )

    def _evaluate_many(
        self,
        scenes: list[SatelliteScene],
        request: PreprocessingInput,
        original_start: date,
    ) -> tuple[list[ScenePair], list[str]]:
        pairs: list[ScenePair] = []
        errors: list[str] = []
        if not scenes:
            return pairs, errors
        with ThreadPoolExecutor(max_workers=min(6, len(scenes))) as executor:
            futures = {
                executor.submit(
                    self.evaluator.evaluate, scene, request, original_start
                ): scene
                for scene in scenes
            }
            for future in as_completed(futures):
                scene = futures[future]
                try:
                    pairs.append((scene, future.result()))
                except RasterQualityError as exc:
                    errors.append(f"{scene.scene_id}: {exc}")
        pairs.sort(key=lambda pair: pair[0].acquired_at)
        return pairs, errors

    def _try_spectral_candidates(
        self, pairs: list[ScenePair], request: PreprocessingInput
    ) -> tuple[SpectralPass | None, list[SpectralPass], int, list[str]]:
        urban_failures: list[SpectralPass] = []
        attempts = 0
        warnings: list[str] = []
        for scene, quality in self._rank_acceptable(pairs):
            attempts += 1
            try:
                urban = self.evaluator.urban_gate(scene, request)
            except RasterQualityError as exc:
                warnings.append(f"{scene.scene_id}: {exc}")
                continue
            if urban.spectral_valid_pixels < self.settings.spectral_min_valid_pixels:
                warnings.append(
                    f"{scene.scene_id}: {urban.spectral_valid_pixels} calibrated spectral pixels "
                    f"is below the absolute minimum {self.settings.spectral_min_valid_pixels}."
                )
                continue
            if urban.spectral_valid_pct < self.settings.spectral_min_valid_pct:
                warnings.append(
                    f"{scene.scene_id}: calibrated spectral-validity "
                    f"{urban.spectral_valid_pct:.2f}% is below "
                    f"{self.settings.spectral_min_valid_pct:.2f}%."
                )
                continue
            candidate = (scene, quality, urban)
            if urban.urban_rejected:
                urban_failures.append(candidate)
                warnings.append(
                    f"{scene.scene_id}: rejected by calibrated NDBI/NDVI urban mean rule."
                )
                continue
            return candidate, urban_failures, attempts, warnings
        return None, urban_failures, attempts, warnings

    @staticmethod
    def _rank_acceptable(pairs: list[ScenePair]) -> list[ScenePair]:
        rank = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
        acceptable = [pair for pair in pairs if pair[1].quality != "LOW"]
        return sorted(
            acceptable,
            key=lambda pair: (
                -rank[pair[1].quality],
                -pair[1].field_valid_pct,
                pair[1].scene_cloud_pct,
                -pair[1].acquired_at.timestamp(),
            ),
        )

    def close(self) -> None:
        if self._owns_http:
            self.http.close()

    def __enter__(self) -> "PreprocessingService":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
