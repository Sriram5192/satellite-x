# Changelog

## 0.8.0 — 2026-08-20

- Added checksum-validated live CelesTrak TLE acquisition for Sentinel NORAD IDs.
- Added Skyfield/SGP4 ground-station pass prediction with sampled elevation, range, range rate and dynamic Doppler.
- Added fail-closed TLE epoch policy; latest TLE is not back-propagated to a historical scene beyond seven days.
- Added Sentinel scene spacecraft/NORAD provenance matching.
- Added ITU-R P.618 atmospheric attenuation with P.676 gas, P.837 rain, P.840 cloud and tropospheric scintillation contributions.
- Added explicit measured-ionospheric input; X-band does not invent an ionospheric fade value when none is measured.
- Added thermal-noise link budget with caller-supplied EIRP, antenna, noise temperature, required Eb/N0 and Doppler inputs.
- Added scheduled-contact dynamic channel allocator with priority/earliest-deadline policy and data/drop/utilization metrics.
- Added a labeled 120-station deterministic contention fixture; it is not represented as Sentinel operational traffic.
- Added a 16/16 independent TLE/SGP4/ITU/link-budget/traffic oracle.
- Expanded suite to 95 deterministic and 8 live tests.

## 0.7.0 — 2026-08-18

- Added Ed25519 artifact signatures, trusted-key verification and parent-digest chains.
- Added signed authoritative government authorization and investigation-case registry.
- Government connectors now reject unsigned caller-supplied authorization by default.
- Bound farmer ownership links to the SHA-256 of a validated BoundaryConfirmation artifact.
- Bound prescription, machinery operator and yield-model approvals to authenticated role sessions.
- Added trusted-signer enforcement for yield model candidates and production yield labels.
- Replaced `1.96 × MAE` with a held-out absolute-residual q95 interval input.
- Added encrypted-at-rest AES-256-GCM evidence-photo upload, digest validation and owner-restricted decryption.
- Evidence synchronization now rejects events until the matching encrypted photo exists.
- Replaced HMAC receipts with publicly verifiable Ed25519 receipts and PWA-side WebCrypto verification.
- Added SQLite-shared API rate limiting and request body limits.
- Added recoverable exclusive OTP claims with deterministic proof IDs and rollback on session failure.
- Added signed governance CLI ingestion paths and fail-closed trusted issuer configuration.
- Expanded suite to 90 deterministic and 6 live tests.

## 0.6.0 — 2026-08-18

- Closed the optical/weather temporal-fusion loophole: weather must end on the selected scene date and contain 15 contiguous days.
- Recomputed weather summaries from daily records and reject tampered summaries.
- Corrected the real 2026-06-28 run from an invalid `-35.41 mm` deficit to aligned `-12.67 mm`; deficit flag changed to false.
- Added k≥5 suppression for village, mandal and district aggregates; one-field metrics are no longer released.
- Made the farmer Streamlit portal fail closed unless identity is configured or explicit demo mode is enabled.
- Enforced linked-field ownership in authenticated farmer mode and removed unconditional admin data access.
- Removed stored-XSS rendering from the offline PWA and stopped service-worker interception/caching of `/api/`.
- Added API no-store, CSP, anti-framing, referrer and browser-permission security headers.
- Added an absolute nine-pixel floor in addition to field-valid percentage.
- Added per-table SQL identifier allowlists for generic JSON persistence.
- Replaced the fixed app date with the Asia/Kolkata local date.
- Advanced AnalyticsResult schema to `1.1.0` with explicit weather reference dates and zero-day alignment.
- Expanded suite to 83 deterministic and 6 live tests.

## 0.5.0 — 2026-08-17

- Added safe optical/SAR resilience routing; SAR-only paths remain unresolved and cannot fabricate optical indices or diagnosis.
- Added official-government JSON API adapter with permission, validity, jurisdiction, HTTPS, credential and activation gates.
- Added provider-backed OTP with E.164 validation, HMAC-hashed challenges, expiry, rate limits, attempt limits and single-use sessions.
- Added authenticated FastAPI ground-evidence synchronization with deterministic idempotent receipts and tamper rejection.
- Added installable offline PWA with IndexedDB queue, GPS capture, photo hashing, service worker and OTP login.
- Added cross-language JavaScript/Python evidence canonicalization and digest audit.
- Added verified-label yield candidate training with leave-one-season-out validation and fixture/production separation.
- Added equipment-profiled, operator-approved machinery transfer packages that never authorize automatic execution.
- Added administrator CLI workflows for identity registration and confirmed-field linking.
- Added `government-fetch`, `resilience-route`, `train-yield-candidate`, `machinery-transfer`, and `serve-api` commands.
- Expanded suite to 74 deterministic and 6 live integration tests.

## 0.4.0 — 2026-08-17

- Added cloud-independent Sentinel-1 RTC dual-polarization fallback with signed Planetary Computer assets and a 5/5 independent raster oracle.
- Added real three-scene crop time-series trends and a 16/16 independent OLS oracle.
- Corrected Set 2 to validate all six Set 3 bands before accepting a scene.
- Added authenticated local person/confirmed-field links with hashed credentials and revocable sessions.
- Added privacy-safe mandal/district aggregation with separate jurisdiction authorization.
- Added tamper-evident, idempotent offline ground-evidence queue and receipt workflow.
- Added experimental relative-NDVI management zones with no automatic rates.
- Added human-approved prescription and yield interfaces that remain explicitly non-production.
- Added Set 3 calibrated extraction of all seven frozen spectral indices.
- Added crop DAS/phenology stage and expected-NDVI interpretation.
- Added 15-day rain minus ET0 water balance and deficit flag.
- Added Set 4 differential diagnosis, Telugu/English actions and false-alarm suppression.
- Prevented baseline/untrusted soil from casting a nitrogen-deficiency vote.
- Added transparent confidence components and sowing-date penalties.
- Added farmer/government/investigator RBAC with jurisdiction, validity and case-ID gates.
- Added privacy-safe village aggregation and ground-verification evidence hashes.
- Added SQLite governance/access-audit persistence.
- Added independent Set 3/4 raster/formula/diagnosis oracle; 12/12 checks pass.
- Added `analyze-field` and `diagnose-field` CLI commands and schemas.
- Expanded suite to 62 deterministic and 6 live integration tests.

## 0.3.0 — 2026-08-17

- Added Set 2 field-level Sentinel-2 candidate catalog and raster quality engine.
- Added original-range then 30-day expanded scene search.
- Added exact polygon SCL clipping, class counts and frozen HIGH/MEDIUM/LOW rules.
- Added calibrated B04/B08/B11 reprojection and physical reflectance validity gate.
- Added multi-candidate spectral retry instead of accepting an SCL-only scene.
- Added calibrated NDVI/NDBI urban mean gate and built-pixel evidence.
- Added independent Set 2 raster oracle; all 13 comparisons pass.
- Fixed non-unique FTW source IDs by appending country, subdivision and geometry hash.
- Added `preprocess-field` CLI, schemas, real accepted and blocked examples.
- Expanded suite to 42 deterministic and 3 live integration tests.

## 0.2.0 — 2026-08-17

- Added consent-required Polygon Recovery input/output contracts.
- Added distance-based Nominatim road/structure/water preflight with exact cache fallback.
- Added live cloud-native FTW 2024/2025 GeoParquet queries through DuckDB.
- Added transparent GPS-containment, acreage-similarity, and recency scoring.
- Added Shapely topology repair and UTM area/perimeter/distance validation.
- Added candidate, user-drawn, and uploaded-FMB confirmation paths with provenance.
- Predicted and uploaded-but-unverified boundaries are never marked legal.
- Added Streamlit/Folium Draw recovery and confirmation website.
- Added independent polygon reality audit; all nine oracle checks pass.
- Added road-negative and real open-field positive live tests.
- Expanded deterministic suite to 37 tests; 2 live integration tests pass.

## 0.1.2 — 2026-08-17

- Added independent full failure study and expanded SCL candidate audit.
- Preserved STAC `scale`, `offset`, and `nodata` in every band asset.
- Updated reality audit to calculate indices from calibrated surface reflectance.
- Added HMAC-SHA256 verification for exact IoT payload bytes.
- Added 24-hour IoT freshness gate and `unverified`/`stale` stream states.
- Prevented self-declared `source=live_hardware` from being trusted without proof.
- Added location, scene-candidate, signed-stale, and machine-readable reality evidence.
- Expanded deterministic suite to 27 tests; live API test also passes.

## 0.1.1 — 2026-08-17

- Added independent satellite/weather/soil/raster reality audit.
- Separated API acquisition pass from full field-reality pass.

## 0.1.0 — 2026-08-17

- Initial Set 1 acquisition engine.
