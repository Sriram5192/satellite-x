# SATELLITE-X — Independent Final Reality Check

**Checked:** 2026-08-17  
**Output checked:** `outputs/set1_guntur_live.json`  
**Independent evidence:** AWS STAC, public Sentinel COG pixels, Open-Meteo raw response, ISRIC SoilGrids WCS

## Honest verdict

| Gate | Verdict |
|---|---|
| Set 1 API acquisition correctness | **PASS** |
| Full field-level reality | **NOT PASSED** |

The Set 1 code correctly acquired and represented the external API responses. However, this example cannot yet be certified as a real agricultural field diagnosis.

## Independent comparisons

### 1. Satellite catalogue — PASS

The audit queried AWS STAC independently, without importing SATELLITE-X.

| Property | SATELLITE-X | Independent AWS result | Match |
|---|---|---|---|
| Scene ID | `S2C_44QMD_20260802_0_L2A` | same | Yes |
| Cloud cover | `31.020102%` | same | Yes |
| B02/B03/B04/B05/B08/B11/SCL URLs | 7 URLs | all 7 same | Yes |

### 2. Weather — PASS

All 30 daily rows matched a fresh direct Open-Meteo response exactly.

| Metric | SATELLITE-X | Independent calculation | Match |
|---|---:|---:|---|
| Rain 15d | 33.3 mm | 33.3 mm | Yes |
| ET0 15d | 87.62 mm | 87.62 mm | Yes |
| Rain 30d | 76.1 mm | 76.1 mm | Yes |
| ET0 30d | 168.56 mm | 168.56 mm | Yes |
| Humidity mean 5d | 62.017% | 62.017% | Yes |

### 3. Actual selected field pixel — FAIL for analytics readiness

The audit opened the selected public COGs and sampled the exact input coordinate.

| Band | Raw value |
|---|---:|
| B04 | 1630 |
| B08 | 1720 |
| B11 | 1996 |
| SCL | **8** |

`SCL=8` is medium-probability cloud and is rejected by the frozen Set 2 rule. Therefore this scene exists and was acquired correctly, but its exact field pixel is not a valid clean pixel for downstream diagnosis. After applying STAC `scale=0.0001` and `offset=-0.1`, the sampled reflectances are B04=`0.063`, B08=`0.072`, and B11=`0.0996`; NDVI=`0.066667` and NDBI=`0.160839`. These indices must not be treated as crop evidence because the SCL gate fails.

### 4. Soil reality — NOT VERIFIED

The REST service timed out, and the Set 1 output correctly disclosed `source=regional_ag_zone_baseline` rather than claiming a live measurement.

An independent ISRIC WCS point query returned no mapped value at the exact coordinate:

```text
phh2o raw = 0
nitrogen raw = 0
exact point = SoilGrids NoData/non-soil mask
```

The nearest mapped SoilGrids cell was approximately `1.275 km` away:

```text
pH raw 68       => 6.8
N raw 212       => 2.12 g/kg
```

The output baseline (`pH=6.8`, `N=0.25 g/kg`) is therefore a declared fallback, not a verified measurement. It must not be presented as actual field soil data.

### 5. IoT reality — NOT VERIFIED

The ESP32 payload passed schema and physical-range validation, but it came from the example JSON. It is unsigned and approximately 43.6 hours old, beyond the configured 24-hour limit. The updated system marks it `unverified` (or `stale` when a valid signature is supplied), never `live`.

## Why the full gate failed

A fresh reverse-location check identifies the coordinate as the primary road `SH288` in Guntur Urban, not an agricultural field. See `outputs/location_reality.json`.

1. The chosen pixel has `SCL=8`, so Set 2 would mask/reject it.
2. SoilGrids has no mapped soil value at the exact example coordinate.
3. The soil values are explicit baseline values, not live field values.
4. The IoT payload is an example contract, not independently verified hardware telemetry.
5. The supplied coordinate is only an example point; no actual farm polygon was supplied.

## Required path to a real PASS

1. Supply the actual farm centroid or GeoJSON boundary—not a general Guntur location.
2. Run Set 2 SCL/field-valid-pixel filtering and reject/reselect scenes until the quality rule passes.
3. Use a live soil measurement, a valid SoilGrids pixel for the exact field, or a lab result.
4. Send a fresh signed/traceable ESP32 payload if IoT verification is required.
5. Re-run `audit/reality_check.py`; it exits `0` only when the full reality gate passes.

## Machine-readable evidence

Full comparison data is stored in `outputs/reality_check.json`.

**Final conclusion: the Set 1 acquisition implementation succeeded, but the current example output did not pass the complete field-reality gate.**
