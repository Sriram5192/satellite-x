# SATELLITE-X Power-Engine Gap Register

**Audit date:** 2026-08-18 (Asia/Calcutta)  
**Scope:** v0.5.0 source, UI/PWA, API, persistence, geospatial processing, analytics, diagnosis, governance, yield/VRA/machinery, tests and operations.  
**Rule:** a software path is not called production-ready merely because its contract or deterministic test exists.

## Executive conclusion

SATELLITE-X has a strong transparent Set 1–4 foundation, real optical/SAR execution and explicit activation gates, but it is not yet a production “power engine.” The biggest risks are not missing index formulas; they are **time alignment, authoritative identity/approval binding, small-group privacy, mobile evidence integrity, scientific calibration, repeated remote raster I/O, and production operations**.

### Hardening result executed today

```text
90/90 deterministic tests PASS
6/6 live tests PASS
Set 2 oracle 13/13 PASS
Set 3/4 oracle 12/12 PASS with scene-aligned weather
Multi-scene oracle 16/16 PASS
Mobile security/digest audit 8/8 PASS
Authenticated API/PWA audit 15/15 PASS
Streamlit demo end-to-end PASS, zero exceptions
Authenticated farmer login → confirm → own-field link → Set 2–4 PASS
```

The temporal correction is consequential: the same 2026-06-28 optical pixels now use weather ending 2026-06-28. Climatic balance changed from the invalid `-35.41 mm` (weather ending 2026-08-17) to the aligned `-12.67 mm`; the deficit flag changed from `true` to `false`.

This register separates:

- **P0 — critical correctness/security/privacy loopholes**: must close before production pilots;
- **P1 — high reliability/science/scale gaps**: must close before district-scale operation;
- **P2 — product/operations maturity gaps**: must close before broad rollout;
- **Delay sources**: items directly increasing farmer/officer waiting time or engineering cycle time.

---

## P0 — Critical loopholes

| ID | Loophole | Evidence / impact | Required closure | Status on 2026-08-18 |
|---|---|---|---|---|
| P0-01 | Optical/weather temporal mismatch | Previous real Set 3 fused a 2026-06-28 optical scene with weather ending 2026-08-17. Water balance changed from `-35.41` to `-12.67 mm` after alignment. | Weather must end on the selected scene date; require 15 contiguous days and recompute summary from daily rows. | **Fixed today — tests PASS** |
| P0-02 | Farmer Streamlit could run without authentication | Identity store existed, but the farmer UI did not require it; “own field only” was not enforced by the UI. | Fail closed unless identity DB is configured; allow demo only via explicit environment flag; require farmer session and linked field. | **Fixed today — tests PASS** |
| P0-03 | One-field government aggregate was re-identifiable | A one-field village/mandal summary said `contains_personal_data=false`, but the aggregate effectively described one person/field. | Suppress all metrics below k=5; never reveal exact small-group count/area/categories. | **Fixed today — tests PASS** |
| P0-04 | Stored XSS in PWA queue | `field_id`, observation and event ID were inserted with `innerHTML`; crafted content could execute in the verification app. | Build DOM nodes and assign untrusted content with `textContent`. | **Fixed today — tests PASS** |
| P0-05 | Service worker could cache authenticated API GET responses | Previous worker cached every successful GET, including `/api/v1/me`, and could return HTML fallback for API failures. | Never intercept/cache `/api/`; cache only allowlisted static assets and navigation shell. | **Fixed today — tests PASS** |
| P0-06 | Percentage-only raster acceptance | A tiny field could have one valid pixel and still show 100% valid. | Require an absolute valid-pixel floor in addition to percentage. | **Fixed today — tests PASS** |
| P0-07 | Human approvals are self-declared JSON | Agronomist, yield and operator approvals are Pydantic objects but are not bound to authenticated user role or a signed approval event. | Approval service must accept authenticated principal, role, immutable artifact hash and persisted approval event. | **Mitigated: authenticated roles + Ed25519 artifact signatures; central approval-event registry remains** |
| P0-08 | Government authorization is trusted from request input | Policy validates an authorization object passed by caller; it does not require authoritative DB lookup/signature for every decision. | Resolve authorization by ID from an authoritative store and verify issuer/signature/revocation. | **Fixed in v0.7 hardening — tests PASS** |
| P0-09 | Case ID is only a non-empty string | Any caller can invent a case ID; there is no case registry, purpose scope, owner, expiry or closure state. | Add case registry and require active case authorization before parcel access/export. | **Fixed in v0.7 hardening — tests PASS** |
| P0-10 | Field link is not cryptographically tied to confirmation | `link_confirmed_field` accepts field ID and source text, not a hash of a persisted BoundaryConfirmation. | Link user to confirmation artifact hash, geometry hash, consent event and timestamp. | **Fixed in v0.7 hardening — tests PASS** |
| P0-11 | Photo hash alone cannot prove visual evidence | Server receives a SHA-256 but not an encrypted photo/object reference; an auditor cannot inspect what was hashed. | Add consented encrypted object upload, object digest, retention policy and restricted retrieval. | **Mitigated: encrypted upload/digest/restricted decrypt; retention scheduler remains** |
| P0-12 | Yield “production_verified” is caller-declared | Evidence reference and dataset purpose are strings; no CCE/weighbridge/procurement registry signature is checked. | Authorized label-ingestion gateway with signed evidence and deduplication. | **Fixed in v0.7 hardening — tests PASS** |
| P0-13 | OTP verification and session issuance are not atomic | OTP is consumed in one DB before session creation in another; failure can burn a valid OTP. Rate checks are also race-prone. | Transactional auth store or recoverable consumed-proof workflow; per-user, phone, IP and global limits. | **Mitigated: exclusive OTP claim + rollback + deterministic proof + shared API limits; single-DB atomic commit remains** |
| P0-14 | Admin role bypassed all data policy | Admin received unconditional field access. Operational admin should not automatically see farmer data. | Deny data access for admin role; use scoped investigator/government authorization. | **Fixed today — tests PASS** |
| P0-15 | Generic JSON persistence interpolated column identifiers | Table was allowlisted, but caller-controlled column names were placed into SQL. | Per-table column allowlist before SQL construction. | **Fixed today — tests PASS** |
| P0-16 | API lacks production rate/body/concurrency controls | OTP and sync endpoints have no shared rate limiter, maximum request bytes or overload control. | Reverse-proxy + application quotas, body limit, per-principal limits and 429 telemetry. | **Fixed in v0.7 hardening — tests PASS** |
| P0-17 | Receipt is HMAC, not independently verifiable signature | Only server secret holder can verify it; external auditor cannot. | Ed25519/ECDSA signed receipts with key ID, rotation and public verification. | **Fixed in v0.7 hardening — tests PASS** |

---

## P1 — High-priority science, integrity, scale and reliability gaps

| ID | Gap | Why it matters | Required fix |
|---|---|---|---|
| P1-01 | Water model uses rain−ET0, not crop ETc | Ignores crop coefficient, irrigation, soil storage and rooting depth; “confirmed water stress” can be overstated. | ETc/Kc, irrigation input, root-zone storage and uncertainty; keep current value as climatic deficit only. |
| P1-02 | SoilGrids is coarse and only 0–5 cm | Tiny fields and mature crops need root-zone conditions; total N is not plant-available N. | Multi-depth profile, local soil test ingestion and field-scale confidence. |
| P1-03 | SAR uses one-scene mean backscatter | No speckle filtering, incidence-angle normalization, orbit consistency or temporal anomaly. | Same-orbit baseline/change workflow and local labels before thresholds. |
| P1-04 | Optical/SAR temporal gap is not scored | Ancillary SAR may be weeks newer than optical imagery. | Emit sensor dates/gaps and downgrade or block multimodal interpretation beyond policy threshold. |
| P1-05 | No immutable end-to-end provenance chain | Set 1, Set 2, Set 3 and Set 4 JSON files can be swapped if field IDs match. | Run ID plus SHA-256 parent-artifact chain and scene/weather/geometry hashes. |
| P1-06 | No authoritative workflow orchestrator | CLI/UI call modules separately; retries can create partially related artifacts. | Durable state machine with idempotent stages and resumable run IDs. |
| P1-07 | Scene ranking can favor old quality over recency | Expanded high-quality scenes can be too old for current advisory. | Crop-aware maximum scene age and explicit age penalty. |
| P1-08 | Cloud mask is SCL-only | No cloud-edge dilation, shadow projection or haze score. | Dilated cloud/shadow mask and scene-level uncertainty. |
| P1-09 | SCL class 7 is accepted globally | “Unclassified” can be risky depending on product/scene. | Evaluate class-7 sensitivity and make crop/region policy configurable. |
| P1-10 | Spatial uncertainty is underrepresented | 26 pixels produce a mean but no minimum mapping unit or boundary-edge uncertainty. | Effective sample size, edge-pixel flag, confidence interval and minimum mapping unit. |
| P1-11 | VRA tertiles can create noisy micro-zones | No morphology, minimum zone area or multi-date stability. | Connected-component cleanup, stable multi-date zones and agronomist policy. |
| P1-12 | Yield interval is `1.96 × MAE` | This is not a calibrated prediction interval. | Conformal/quantile interval with held-out coverage report. |
| P1-13 | Yield validation lacks spatial holdout | Season holdout alone can retain geography/field leakage. | Grouped field and geography holdouts plus external district validation. |
| P1-14 | Machinery file is generic GeoJSON | Not an OEM/ISOBUS task file and has no transfer signature. | Target-specific format adapter, signed package, import simulator and field trial. |
| P1-15 | Diagnosis scope is narrow | Only water, fungal suspicion and nitrogen evidence; pests, heat, salinity and other nutrients remain unresolved. | Expand only after verified local labels and differential rules. |
| P1-16 | Confidence is heuristic, not calibrated probability | 64% is a formula score, not observed 64% correctness. | Rename to evidence score or calibrate against ground truth with reliability curves. |
| P1-17 | NDWI and GNDVI are algebraic inverses | They do not provide independent evidence diversity under current definitions. | Preserve frozen outputs but prevent double-counting and document redundancy. |
| P1-18 | Password login has no lockout/reset/rotation | Online guessing and account recovery are incomplete. | Login throttling, password reset, session inventory and credential rotation. |
| P1-19 | Government connector needs SSRF/redirect/size controls | HTTPS URL can still target unsafe hosts or redirect; response size is unbounded. | Host allowlist, DNS/IP checks, redirect off, byte limit and automatic access audit. |
| P1-20 | Sync batch is partially committing | Earlier envelopes commit before a later envelope raises a batch error. | Per-item result or all-or-nothing transaction with explicit semantics. |
| P1-21 | GPS accuracy is not stored in evidence | UI shows accuracy but canonical evidence omits it; no proximity/geofence check. | Add accuracy, altitude/heading optional, field-distance policy and mock-risk flag. |
| P1-22 | Offline evidence is plaintext in IndexedDB | Field ID, GPS and notes are readable to anyone with device/browser access. | Device-bound encryption, remote wipe policy and minimal offline retention. |
| P1-23 | SQLite has no migration/version framework | `CREATE TABLE IF NOT EXISTS` cannot safely evolve existing production schemas. | Schema version table, migrations, rollback and compatibility tests. |
| P1-24 | SQLite concurrency/backup policy is absent | Multiple workers can lock DB; no WAL/busy timeout/backup/restore drill. | WAL, busy timeout, transaction discipline, scheduled backup and restore test. |
| P1-25 | No tenant/data-residency boundary | Department/district/customer isolation is not a database invariant. | Tenant IDs, row-level policy and separate encryption keys where required. |
| P1-26 | No retention/deletion/consent lifecycle | Consent is a boolean, not a versioned purpose record; revocation does not purge/lock data. | Versioned consent, purpose expiry, retention scheduler, export/delete workflow. |

---

## P2 — Product and operational maturity gaps

| ID | Gap | Required improvement |
|---|---|---|
| P2-01 | No government dashboard | Build aggregate-only dashboard with suppression-aware maps and export audit. |
| P2-02 | No investigator case console | Active case registry, evidence timeline, expiry and closure. |
| P2-03 | Farmer UI localization is partial | Telugu UI, low-literacy cards, audio, accessibility and offline-friendly pages. |
| P2-04 | No alert/notification service | Consent-aware SMS/push queue with quiet hours and delivery receipts. |
| P2-05 | No task assignment download to PWA | Assigned field tasks, offline task list and server conflict resolution. |
| P2-06 | No production observability | Structured logs, metrics, traces, provider health, run IDs and SLO dashboard. |
| P2-07 | No circuit breaker | Provider outages repeatedly consume timeout/retry budget. |
| P2-08 | No durable background queue | Raster work blocks Streamlit/API processes. |
| P2-09 | No object/tile cache | Same COG windows are reopened by quality, analytics and zones. |
| P2-10 | Planetary Computer SAS token not cached | Every SAR run performs another token request. |
| P2-11 | FTW/Nominatim query cache strategy is limited | Remote latency and rate limits delay repeated recovery. |
| P2-12 | No provider freshness SLA | Live/cached/baseline states exist but no operational maximum age per product. |
| P2-13 | No cache eviction/quota | Runtime cache can grow without lifecycle controls. |
| P2-14 | No benchmark budget | No p50/p95 stage timing, COG byte count or memory target. |
| P2-15 | No load/concurrency test | District-scale concurrent fields/official users are unmeasured. |
| P2-16 | No browser/device automation | PWA has syntax/API tests but no real IndexedDB, GPS, camera, service-worker upgrade or Android test. |
| P2-17 | No security fuzz/property tests | Geometry, API, OTP and connector edge cases need fuzzing. |
| P2-18 | Tests depend on mutable `outputs/` | Generated artifacts can accidentally become test fixtures and hide provenance drift. |
| P2-19 | No CI quality gates | Add lint, formatting, type checking, coverage, SAST, dependency scan and schema diff. |
| P2-20 | No container/IaC/reproducible deployment | Add pinned lockfile, container, health/readiness probes and secret references. |
| P2-21 | No disaster recovery exercise | Define RPO/RTO and execute restore test. |
| P2-22 | No API compatibility policy | Version endpoints/schemas and publish deprecation rules. |
| P2-23 | App used a fixed analysis date | Use current local date or an explicit user-selected date; record timezone. **Fixed today — tests PASS.** |
| P2-24 | CRS assumption is implicit | State EPSG:4326 in contracts and reject unsupported CRS. |
| P2-25 | Raster area and polygon area can differ | Report edge-pixel area uncertainty and clipped effective area. |
| P2-26 | Legal boundary remains external | FTW/user draw must never become ownership proof; official cadastral verification remains gated. |

---

## Direct delay sources

| ID | Delay source | Current effect | Power-engine remedy |
|---|---|---|---|
| D-01 | Repeated COG opens/reprojection | Set 2, Set 3 and VRA read overlapping bands independently. | Window/tile cache and reusable aligned raster bundle. |
| D-02 | Synchronous Streamlit workflow | Full flow can take 1–2 minutes and is lost on process failure. | Background jobs, progress events and resumable run ID. |
| D-03 | Monsoon optical gaps | Expanded search can select imagery weeks old. | SAR change baseline + freshness policy + unresolved state. |
| D-04 | SoilGrids 503/NoData | Repeated timeout before cache/baseline. | Circuit breaker, coverage precheck and local cache. |
| D-05 | FTW remote GeoParquet query | Recovery depends on remote file/scan latency. | Regional tile index and local bounded cache. |
| D-06 | Nominatim dependency/rate limit | Location preflight waits on public reverse geocoder. | Cached local OSM extracts or authorized geocoder. |
| D-07 | No SAS token cache | Extra network call on every SAR run. | Expiry-aware token cache. |
| D-08 | No batch field orchestrator | Officers must process fields independently. | Jurisdiction queue with bounded concurrency. |
| D-09 | No provider circuit breaker | Retries amplify outages. | Health state and cooldown. |
| D-10 | No persisted stage timing | Slow stages cannot be identified from production evidence. | Per-stage duration/bytes/retries metrics. |
| D-11 | No incremental time-series update | Rebuilding series reopens prior scenes. | Append-only observation store and cached trend update. |
| D-12 | Manual activation/data onboarding | Government, SMS, labels and equipment profiles require ad-hoc setup. | Signed configuration registry and onboarding checklist. |

---

## Today’s Power-Engine hardening sprint

The first sprint intentionally targets high-impact loopholes that can be fixed without fabricating external credentials or scientific labels:

1. enforce optical-scene/weather alignment and daily-summary integrity;
2. make farmer Streamlit fail closed without auth or explicit demo mode;
3. suppress government aggregates below k=5;
4. remove stored XSS from the PWA;
5. prevent service-worker caching of authenticated API responses;
6. require an absolute minimum spectral pixel count;
7. remove unconditional admin data bypass;
8. allowlist SQL identifiers in generic persistence;
9. add API no-store and browser security headers;
10. replace fixed UI analysis date with current date.

### Sprint acceptance criteria

- old mismatched Set 1 weather is rejected;
- scene-aligned Set 1 weather is accepted and changes water-balance evidence transparently;
- fewer than five fields release no aggregate metrics;
- malicious queue text is rendered only as text;
- `/api/*` is never service-worker cached;
- one-pixel/very-small spectral samples cannot pass;
- farmer UI cannot run production analysis without a valid session and linked field;
- all deterministic/live/oracle/Streamlit/PWA tests pass after regenerated schemas and outputs.

## Recommended order after today

1. **Authoritative trust chain:** signed boundary confirmation, authorization/case registry, authenticated approvals.
2. **Evidence-grade mobile:** encrypted photo object, GPS accuracy/geofence, asymmetric receipt.
3. **Scientific upgrade:** ETc/irrigation/root-zone water, SAR change baseline, calibrated confidence.
4. **Performance engine:** aligned raster cache, background queue, run state machine, circuit breakers.
5. **Production platform:** migrations, tenant isolation, observability, CI/CD, backup/restore and device tests.
