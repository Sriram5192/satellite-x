# SATELLITE-X Set 1 — Execution and Comparison Report

**Execution date:** 2026-08-17  
**Location used:** Guntur, Andhra Pradesh (`16.3067, 80.4365`)  
**Python:** 3.13.14

## 1. Static/import gate

Command:

```bash
PYTHONPATH=src python -m compileall -q src
```

Result: **PASS** — every source module compiled and imported.

## 2. Deterministic regression gate

Command:

```bash
PYTHONPATH=src pytest -q
```

Current result after Set 1–4, resilience, authenticated API/PWA, government adapters, yield gates, and machinery controls: **PASS — 95/95 deterministic tests**.

Coverage of behavior includes:

- Strict farm and ESP32 contracts
- Physical range and timezone rejection
- Acreage and polygon bounding boxes
- Required seven-band STAC normalization
- Lowest-cloud deterministic scene selection
- AWS empty-result 30-day expansion
- AWS error → CDSE provider fallback
- 15/30-day weather arithmetic
- Exact weather cache fallback; no-cache hard failure
- SoilGrids unit conversion
- Soil cache and visibly tagged regional baseline
- IoT field mismatch rejection before network calls
- STAC scale/offset/nodata preservation
- HMAC-SHA256 success, tamper rejection, CLI wiring, and stale/unverified states
- Full end-to-end JSON equality against the golden reference

### Golden comparison

| Check | Expected | Actual | Result |
|---|---:|---:|---|
| Full JSON object | `tests/golden/set1_expected.json` | Pipeline result | **EXACT MATCH** |
| Selected scene | `S2A_GOLDEN_20240125_L2A` | same | **PASS** |
| Rain, last 15 rows | `345.0 mm` | `345.0 mm` | **PASS** |
| ET0, last 15 rows | `60.0 mm` | `60.0 mm` | **PASS** |
| Rain, all 30 rows | `465.0 mm` | `465.0 mm` | **PASS** |
| Soil pH conversion | `68 / 10 = 6.8` | `6.8` | **PASS** |
| Soil N conversion | `25 / 100 = 0.25 g/kg` | `0.25 g/kg` | **PASS** |

## 3. Live API integration gate

Command:

```bash
PYTHONPATH=src pytest -m live -o addopts='' -q -vv
```

Current result: **PASS — 8/8 live integration tests** (95 deterministic tests deselected): Set 1 APIs, road/FTW polygon recovery, Set 2 real COG selection, Set 3 seven-index extraction, Sentinel-1 RTC fallback, and no-rate experimental management zones.

Live assertions:

- AWS Earth Search returned expected Guntur scene `S2C_44QMD_20260802_0_L2A`.
- Normalized asset set exactly equals `B02, B03, B04, B05, B08, B11, SCL`.
- Open-Meteo returned 30 historical/current rows.
- Reported 15-day rainfall exactly equals an independent sum of the final 15 rows.
- Soil source is restricted to declared provenance values only.

## 4. Full CLI execution

Command:

```bash
SATELLITE_X_READ_TIMEOUT_S=8 SATELLITE_X_RETRIES=0 \
PYTHONPATH=src python -m satellite_x acquire \
  --input examples/guntur_field.json \
  --iot examples/iot_payload.json \
  --output outputs/set1_guntur_live.json
```

Result: **PASS** — output validates against `RawDataContainer` schema.

| Live value | Result |
|---|---|
| Pipeline status | `degraded` |
| Satellite source | `aws_earth_search` |
| Scene ID | `S2C_44QMD_20260802_0_L2A` |
| Scene cloud | `31.020102%` |
| Weather source | `open_meteo_forecast` |
| History / forecast rows | `30 / 7` |
| Rain 15d / ET0 15d | `33.3 / 87.62 mm` |
| Rain 30d / ET0 30d | `76.1 / 168.56 mm` |
| 5-day mean RH | `62.017%` |
| Soil source | `regional_ag_zone_baseline` |

`degraded` is intentional and correct: the ISRIC REST request timed out and no earlier exact cache existed. The code did not invent a live SoilGrids result; it used the blueprint's baseline and emitted a full warning with provenance.

## 5. Satellite asset accessibility

A 16-byte HTTP range request was executed against every selected AWS COG.

| Asset | HTTP | Bytes checked | Result |
|---|---:|---:|---|
| B02 | 206 | 16 | PASS |
| B03 | 206 | 16 | PASS |
| B04 | 206 | 16 | PASS |
| B05 | 206 | 16 | PASS |
| B08 | 206 | 16 | PASS |
| B11 | 206 | 16 | PASS |
| SCL | 206 | 16 | PASS |

## Software/API gate

**SET 1 SOFTWARE AND API ACQUISITION: PASSED deterministic regression, live integration, schema validation, CLI execution, and asset accessibility checks.**

This is not a field-level agronomic certification. The later independent audit sampled the exact COG pixel and queried SoilGrids WCS. That stricter gate returned `NOT_FULL_REALITY_PASS` because SCL was 8, the exact soil point was NoData, and the IoT payload was not independently verified hardware telemetry. See `REALITY_CHECK_REPORT.md` and `outputs/reality_check.json`.

This report certifies Set 1 software and Polygon Recovery v0.2.0. Sets 2–5 and authorized legal-record verification are not claimed as implemented. See `POLYGON_BUILD_REPORT.md` for the polygon-specific evidence.
