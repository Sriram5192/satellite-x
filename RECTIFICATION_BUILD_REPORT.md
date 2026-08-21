# SATELLITE-X v0.3.0 — Drawback Rectification Build Report

**Date:** 2026-08-17  
**Scope implemented:** Highest-priority P0 fixes before diagnosis

## What changed

### 1. Scene-wide cloud selection replaced with field-level quality

Old behavior:

```text
Pick lowest scene cloud under threshold
```

New behavior:

```text
Query every scene in original range
→ clip SCL to exact crop polygon
→ calculate field-valid percentage and SCL counts
→ apply HIGH/MEDIUM/LOW matrix
→ test calibrated spectral usability
→ test urban gate
→ retry next candidate
→ expand 30 days if original range has no usable candidate
```

### 2. SCL-only acceptance prevented

A real original-range scene passed SCL MEDIUM quality but only `7.69%` of polygon pixels had physically usable calibrated B04/B08/B11 reflectance. It is now rejected automatically.

```text
S2C_44PMC_20260723_0_L2A
SCL field-valid: 100% on the crop test used by final run
Calibrated spectral-valid: 7.69%
Action: reject and continue
```

### 3. Expanded candidate selected

```text
Scene: S2B_44PMC_20260628_0_L2A
Field-valid: 100%
SCL: 26 bare-soil pixels
Scene cloud: 25.91446%
Quality: MEDIUM
Calibrated spectral-valid: 100%
Mean NDVI: 0.324206
Mean NDBI: 0.224481
Built pixel percentage: 0%
Urban mean condition: not met
Final status: accepted
```

The NDBI mean is high, but the frozen urban rule requires both `NDBI > 0.08` and `NDVI < 0.20`; NDVI is `0.324206`, so the field is not rejected by that rule. This remains explicit evidence rather than a hidden decision.

### 4. Road input remains blocked

```text
status = rejected_location
reason = POINT_ON_OR_NEXT_TO_ROAD
```

No satellite preprocessing is performed for a consent-bound GPS point already classified as blocked.

### 5. Non-unique FTW ID bug fixed

Live investigation found that raw FTW numeric IDs can repeat within a large partition. Persistent candidate IDs now include:

```text
country + subdivision + raw ID + year + geometry SHA-256 prefix
```

Example:

```text
ftw-IN-AP-1537149-2025-545a8a4ecb
```

This prevents a candidate from being confused with another geometry sharing the same upstream numeric ID.

## New source modules

```text
src/satellite_x/preprocessing/
├── catalog.py
├── quality.py
├── models.py
├── errors.py
└── service.py
```

## New CLI

```bash
satellite-x preprocess-field --input REQUEST.json --output RESULT.json
```

## New safeguards

- Exact polygon SCL clip
- SCL `{4,5,6,7}` mask
- Field-valid percentage
- Scene-cloud matrix
- Multi-scene retry
- 30-day expanded search
- STAC scale/offset enforcement
- Physical reflectance range checks
- Minimum 60% calibrated spectral-valid pixels
- Reprojection to the SCL 20 m grid
- Calibrated NDVI/NDBI means
- Built-pixel percentage
- Frozen urban mean condition
- Explicit rejected/error statuses

## Independent oracle

`audit/preprocessing_reality.py` does not import SATELLITE-X. It directly opens the selected public COGs and independently recomputes the raster outputs.

Result:

```text
13/13 comparisons PASS
```

Compared fields include:

- total polygon pixels
- SCL-valid pixels
- valid percentage
- SCL class counts
- calibrated spectral pixels
- spectral-valid percentage
- mean NDVI
- mean NDBI
- built-pixel percentage
- expanded-range evidence
- final accepted status

Machine report: `outputs/preprocessing_reality.json`

## Automated validation

```text
42/42 deterministic tests PASS
3/3 live integration tests PASS
Streamlit polygon → confirmation → Set 2 interaction PASS
```

The UI integration test also exposed and fixed a tuple-coordinate compatibility bug between Shapely mappings and the STAC boundary-bbox walker.

Live tests now cover:

1. Set 1 external APIs
2. Road rejection + FTW polygon recovery
3. Set 2 real COG quality, spectral retry and expanded scene selection

## What remains

Not yet implemented in v0.3.0:

- Sentinel-1 SAR monsoon fallback
- Set 3 seven-index/time-series/phenology engine
- Set 4 differential diagnosis and calibrated confidence
- Local ground-truth mobile workflow
- Village parallel processing
- Government authorization/RBAC
- Yield/VRA/machinery modules

## Honest verdict

The highest-risk early flaw—accepting a scene based on scene cloud/SCL alone—has been rectified. The engine now requires exact field quality and calibrated spectral usability before forwarding data to analytics.

This is a real Set 2 preprocessing pass, not yet an agronomic diagnosis pass.
