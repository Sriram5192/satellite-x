# SATELLITE-X — Complete Failure Study, Root Causes, Fixes, and Re-check

**Study date:** 2026-08-17  
**Core output:** `outputs/set1_guntur_live.json`  
**Input point:** `16.3067, 80.4365`  
**Current full-reality verdict:** **FAIL (correctly blocked)**  
**Set 1 API acquisition verdict:** **PASS**

---

## 1. Executive conclusion

The code correctly copied the selected AWS scene and Open-Meteo data. The full reality gate failed because the example input is not a farm location, the selected scene has no valid field pixels, live soil is unavailable at that point, and the ESP32 JSON is unsigned and stale.

This is not one single formula error. It is a combination of:

1. **Invalid production input** — a city road coordinate instead of a field polygon.
2. **Field-level quality not yet applied** — Set 1 used scene-wide cloud percentage; Set 2 SCL filtering has not yet selected/rejected candidates in the main pipeline.
3. **No exact soil coverage** — ISRIC returns NoData at the point and REST is unavailable.
4. **No trustworthy live IoT provenance** — the example payload was unsigned and about 43.6 hours old.
5. **One real code omission discovered** — the first build did not retain STAC radiometric scale/offset. This has now been fixed and regression-tested.

The software now refuses to call unsigned/stale IoT data live and the independent audit exits non-zero when field reality fails.

---

## 2. Failure matrix

| ID | Failure | Root cause | Type | Impact | Current state |
|---|---|---|---|---|---|
| F-01 | Input is not a farm | Coordinate reverse-resolves to SH288 in Guntur Urban | Input | Entire crop interpretation invalid | **Needs actual field** |
| F-02 | Exact boundary absent | `boundary_geojson=null`; acreage square was synthesized around the road | Input/design | Pixels contain road/buildings/mixed land | **Needs polygon** |
| F-03 | Selected scene field validity is 0% | Scene-wide cloud is 31.02%, but field SCL is 47×class 8 and 2×class 9 | Quality | No valid pixel enters analytics | **Set 2 must reject** |
| F-04 | Better candidates were not selected by Set 1 | Set 1 ranks scene-wide cloud; field SCL ranking belongs to Set 2 | Stage integration | Current selected scene is LOW quality | **Set 2 handshake needed** |
| F-05 | Exact soil point is NoData | SoilGrids WCS gives zero/no-soil mask at urban point | Data/input | Baseline is not measured soil | **Needs real field/ground data** |
| F-06 | Soil nitrogen baseline is not locally verified | Baseline is 0.25 g/kg; nearest mapped cell is 2.12 g/kg | Fallback | Large possible nutrient error | **Must not be treated as live** |
| F-07 | IoT payload not authentic | JSON self-declared `live_hardware`; no signature | Security | Anyone could forge a payload | **Fixed: HMAC gate added** |
| F-08 | IoT payload stale | Timestamp is about 43.6h old; allowed maximum is 24h | Freshness | Not a current ground observation | **Fixed: stale gate added** |
| F-09 | Calibration metadata omitted in v0.1.1 | Scale/offset were present in STAC but not in `BandAsset` | Code | Later indices could use wrong reflectance | **Fixed in v0.1.2** |

---

## 3. Location reality check

A fresh OpenStreetMap Nominatim reverse query returned:

```text
category     = highway
type         = primary
name         = SH288
display_name = SH288, Guntur Urban, Arundelpet, Brodipet, Guntur,
               Andhra Pradesh, 522001, India
```

Therefore the point is a road in an urban area, not a verified agricultural field. Machine evidence is stored in `outputs/location_reality.json`.

### Why acres cannot repair a wrong centroid

For `5 acres`, Set 1 creates an approximate square of about 142 m × 142 m around the centroid. If the centroid is on SH288, this square still covers urban/mixed pixels. Acreage is only an area; it cannot infer the real field shape or move the location to a farm.

### Required solution

Production execution must require one of:

- A real GeoJSON `Polygon`/`MultiPolygon`, preferably drawn on the map; or
- A verified centroid physically inside the farm plus an explicit acknowledgement that an acreage square is approximate.

For a final reality pass, `boundary_geojson` should not be null.

---

## 4. Satellite scene-quality study

### Current selected scene

```text
Scene ID          S2C_44QMD_20260802_0_L2A
Scene cloud       31.020102%
Field pixels      49
Valid SCL pixels  0
Field valid       0.00%
SCL counts        class 8 = 47, class 9 = 2
Frozen quality    LOW
```

The Set 1 scene selection itself matches AWS exactly. The problem is that scene-wide cloud does not guarantee a clear field.

### All candidates studied over original + 30-day expansion

Fifteen scenes were independently sampled. The result was:

```text
HIGH quality    0 scenes
MEDIUM quality  2 scenes
LOW quality    13 scenes
```

Potential SCL alternatives:

| Date | Scene | Scene cloud | Field valid | SCL | Frozen quality |
|---|---|---:|---:|---|---|
| 2026-06-28 | `S2B_44QMD_20260628_0_L2A` | 32.511455% | 100% | 49 bare-soil pixels | MEDIUM |
| 2026-07-15 | `S2A_44QMD_20260715_0_L2A` | 33.927912% | 100% | 47 bare soil, 2 vegetation | MEDIUM |
| 2026-08-02 | selected scene | 31.020102% | **0%** | cloud classes 8/9 | **LOW** |

Machine evidence is in `outputs/scene_candidate_study.json`.

### Important warning

The two MEDIUM alternatives do not turn this location into a farm. They only prove that field-level SCL ranking can find clearer observations. Reverse geocoding still identifies the input as an urban road.

### Correct solution for Set 2 integration

1. Set 1 returns/searches candidate scenes.
2. Set 2 clips every candidate SCL to the actual polygon.
3. Compute `FieldValid%` using SCL `{4,5,6,7}`.
4. Rank scenes: HIGH first, then newest MEDIUM.
5. Reject all LOW scenes; never calculate crop health from them.
6. If all original-range scenes are LOW, trigger the 30-day expansion and repeat.
7. Only after a scene passes quality should NDBI/NDVI be calculated.

For the current selected scene, the correct action is **reject and do not diagnose**.

---

## 5. Radiometric calibration study and fix

AWS STAC supplies this metadata for the reflectance bands:

```text
scale  = 0.0001
offset = -0.1
nodata = 0
```

Correct conversion:

```text
surface_reflectance = DN × scale + offset
```

For the selected point:

| Band | DN | Corrected reflectance |
|---|---:|---:|
| B04 | 1630 | 0.0630 |
| B08 | 1720 | 0.0720 |
| B11 | 1996 | 0.0996 |

Corrected ratios are approximately:

```text
NDVI = 0.066667
NDBI = 0.160839
```

They are **not valid crop evidence** because SCL is 8. The values are listed only to verify calibration.

### Code fix completed

`BandAsset` now retains:

```json
{
  "scale": 0.0001,
  "offset": -0.1,
  "nodata": 0.0
}
```

Unit, golden, and live tests now check these fields. This prevents Set 3 from silently calculating indices from uncalibrated DN values.

---

## 6. Soil failure study

### REST result

The SoilGrids REST service did not return a live result. The code correctly marked the fallback:

```text
source        = regional_ag_zone_baseline
fallback_used = true
status        = degraded
```

### Independent WCS result

At the exact point:

```text
phh2o raw     = 0
nitrogen raw  = 0
interpretation = NoData / non-soil mask
```

Nearest mapped cell, about 1.275 km away:

```text
pH raw 68       => pH 6.8
N raw 212       => 2.12 g/kg
```

Current blueprint baseline:

```text
pH = 6.8
N  = 0.25 g/kg
```

The pH happens to equal the nearest mapped value, but nitrogen does not. The nearest value must also not be copied to the field—it is 1.275 km away and may represent different land.

### Safe solution

Recommended source order:

1. Exact live IoT/lab soil result
2. Exact SoilGrids REST value
3. Exact SoilGrids WCS value
4. Exact cached value with timestamp
5. Regional baseline only as a visibly labelled prior

A regional baseline must not cast a “live soil” vote and must reduce confidence. At an exact SoilGrids NoData point, the output should remain `degraded` until real ground data is supplied.

---

## 7. IoT authenticity and freshness study

The original contract validates structure and physical ranges, but a JSON field saying `"source":"live_hardware"` is not proof that hardware sent it.

The example reading is also about 43.6 hours old, beyond the new 24-hour freshness window.

### Security fix completed

The build now supports HMAC-SHA256 over the exact payload bytes:

```bash
SATELLITE_X_IOT_HMAC_SECRET='device-secret' \
python -m satellite_x acquire \
  --input examples/guntur_field.json \
  --iot live_payload.json \
  --iot-signature '<64-hex-hmac>' \
  --output outputs/result.json
```

IoT stream states are now:

- `live`: signature valid and timestamp fresh
- `unverified`: no valid signature
- `stale`: signature valid but timestamp outside the freshness window
- `not_supplied`: no IoT data

Executed signed test result:

```text
signature verified = true
fresh              = false
stream state        = stale
```

Thus even a genuine old packet is not incorrectly presented as live.

---

## 8. Weather verification

Weather is not a failure. A fresh direct Open-Meteo query matched all 30 daily rows exactly.

| Metric | Core output | Independent calculation | Result |
|---|---:|---:|---|
| Rain 15d | 33.3 mm | 33.3 mm | PASS |
| ET0 15d | 87.62 mm | 87.62 mm | PASS |
| Rain 30d | 76.1 mm | 76.1 mm | PASS |
| ET0 30d | 168.56 mm | 168.56 mm | PASS |
| RH mean 5d | 62.017% | 62.017% | PASS |

No weather calculation change is required.

---

## 9. Fixes completed in code

| Fix | Status |
|---|---|
| Preserve STAC scale/offset/nodata | DONE |
| Use calibrated reflectance in reality audit | DONE |
| Reject self-declared IoT “live” provenance | DONE |
| HMAC-SHA256 verification | DONE |
| 24-hour IoT freshness gate | DONE |
| `unverified` and `stale` stream states | DONE |
| Independent field-reality audit | DONE |
| Expanded scene SCL candidate study | DONE |
| Machine-readable location/scene/reality evidence | DONE |
| Regression suite after fixes | **27 deterministic tests PASS** |
| Live API integration after fixes | **1 live test PASS** |

---

## 10. Items that cannot be repaired by code alone

The following evidence must come from the user/field:

1. Actual farm polygon or a centroid inside the farm
2. Real sowing date confirmation
3. Current signed ESP32 packet, if IoT is used
4. Soil sensor/lab result when SoilGrids has NoData

Using another guessed coordinate would only create another demo; it would not verify the user's farm.

---

## 11. Exact final-pass checklist

The full reality gate may return PASS only when all are true:

- [ ] Input reverse/visual check is consistent with agricultural land
- [ ] Actual polygon supplied
- [ ] Satellite scene has HIGH or MEDIUM frozen quality
- [ ] `FieldValid% ≥ 60%` and `SceneCloud% ≤ 40%`
- [ ] Selected field pixels are SCL `{4,5,6,7}`
- [ ] NDBI urban gate passes on calibrated reflectance
- [ ] Weather rows and aggregates match source
- [ ] Soil source is exact live/cached field data, or fallback is excluded from live voting
- [ ] IoT, if supplied, is signed and fresh
- [ ] Full independent audit exits code `0`

## Final answer

**We succeeded at Set 1 API acquisition and fixed two provenance/calibration defects. We have not passed field reality for this example. The current output is correctly blocked because the input is SH288 in Guntur Urban, the selected scene has 0% valid field pixels, soil is NoData/baseline, and IoT is unsigned/stale.**
