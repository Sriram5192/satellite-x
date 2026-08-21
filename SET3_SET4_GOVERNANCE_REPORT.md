# SATELLITE-X v0.4.0 — Set 3, Set 4 & Governance Build Report

**Date:** 2026-08-17

## Delivered

### Set 3 analytics

- Calibrated B02/B03/B04/B05/B08/B11 extraction on the selected SCL grid
- Physical reflectance and index-range validation
- NDVI, EVI, SAVI, NDRE, NDMI, NDWI and GNDVI
- Mean, median, p10, p90, minimum, maximum and valid-pixel counts
- Crop DAS and frozen cotton/chilli/paddy stages
- Expected NDVI position
- 15-day rain minus ET0 balance
- Hydrological deficit flag
- Soil-source warning policy

### Set 4 diagnosis

- Confirmed water-stress evidence rule
- Suspected fungal-risk rule with mandatory inspection
- Nitrogen-deficiency evidence only with trusted soil
- Maturity false-alarm suppression
- Normal/unresolved result when causes do not agree
- Telugu and English actions
- Transparent Q/C/A confidence formula and sowing penalty
- Ground-verification requirement

### Governance

- Farmer own-field-only access
- Government authorization status and validity
- Permission and village/mandal/district jurisdiction checks
- Case ID required for parcel detail/evidence export
- Aggregate-only government access by default
- Personal-data-free village, mandal and district summaries
- Ground-verification photo SHA-256 evidence model
- Idempotent offline evidence queue with tamper detection and server receipts
- Hashed local credentials, revocable sessions and confirmed-field links for individual mode
- SQLite government authorization and access audit tables

## Sentinel-1 RTC fallback

```text
Scene: S1D_IW_GRDH_1SDV_20260805..._rtc
Valid dual-pol pixels: 96
VV mean: -11.662815 dB
VH mean: -22.279663 dB
VV−VH mean: 10.616848 dB
```

The fallback is cloud-independent and terrain-corrected. It is exposed as evidence only; it does not fabricate optical vegetation indices. The independent direct-COG oracle passed 5/5 comparisons.

## Real multi-scene time series

Three independently processed live Sentinel-2 observations were used:

```text
2026-03-20 NDVI 0.640144
2026-04-06 NDVI 0.481902
2026-05-09 NDVI 0.383041
NDVI slope: -0.004850/day
Quality: limited (largest cloud-driven gap was 33 days)
```

All seven index slopes and changes matched an independent OLS oracle: **16/16 checks passed**.

## Experimental VRA/yield safety gates

- Live relative-NDVI zoning produced low/medium/high zones from 26 valid pixels.
- `application_rates` is deliberately `null`; human approval is mandatory.
- Prescription GeoJSON never authorizes machinery execution.
- Yield returns `unavailable_unvalidated_model` without a locally validated model and remains experimental even with an approval fixture.

## Real Set 3 output

```text
Field: AP_GNT_FTW_CROP_TEST
Scene: S2B_44PMC_20260628_0_L2A
Spectral valid: 26/26 (100%)
Crop: chilli
DAS: 13
Stage: Transplant
NDVI mean: 0.324206
NDMI mean: -0.224481
NDRE mean: 0.134915
Rain15d: 50.8 mm
ET0_15d: 86.21 mm
Water balance: -35.41 mm
Deficit flag: true
Soil: live SoilGrids, pH 6.6, N 2.3 g/kg
```

## Real Set 4 output

```text
Verdict: NORMAL_OR_UNRESOLVED
Confidence: 64.0%
Confidence tag: MEDIUM_CONFIDENCE
Ground verification: required
```

Reason: weather and NDMI support dryness, but NDVI is above the expected transplant-stage range, so the frozen three-signal water-stress condition is not met. The engine does not force a diagnosis from partial agreement.

## Independent oracle

`audit/analytics_diagnosis_reality.py` imports no SATELLITE-X code. It independently reopens all six calibrated COG bands and recomputes:

- all seven index means
- spectral pixel count
- water balance
- DAS
- differential verdict
- final confidence

Result:

```text
12/12 checks PASS
```

Machine evidence: `outputs/analytics_diagnosis_reality.json`

## Validation

```text
62/62 deterministic tests PASS
6/6 live integration tests PASS
19/19 JSON schemas structurally valid; representative outputs validate
Streamlit recovery → SAR → Set 2 → Set 3/4 AppTest PASS with no exceptions
```

Live chain now covers:

```text
Set 1 real acquisition
→ FTW polygon recovery
→ Set 2 all-six-band raster quality/scene retry
→ Set 3 real seven-index extraction
→ Set 4 transparent diagnosis (CLI + independent oracle)
→ Sentinel-1 RTC evidence + independent oracle
→ Three-scene crop trend + independent OLS oracle
→ No-rate management zones
```

## Commands

```bash
satellite-x analyze-field \
  --preprocessing outputs/preprocessing_crop_field_result.json \
  --set1 outputs/set1_crop_field_live.json \
  --output outputs/analytics_crop_field_result.json

satellite-x diagnose-field \
  --analytics outputs/analytics_crop_field_result.json \
  --quality MEDIUM \
  --sowing-date-quality known \
  --output outputs/diagnosis_crop_field_result.json

satellite-x sar-fallback \
  --input examples/sar_fallback_crop_field_request.json \
  --output outputs/sar_fallback_crop_field_result.json

satellite-x analyze-timeseries \
  --input examples/timeseries_live_request.json \
  --output outputs/timeseries_live_result.json

satellite-x management-zones \
  --preprocessing outputs/preprocessing_crop_field_result.json \
  --output outputs/management_zones_live.json
```

## Honest limitations still requiring external evidence or authorization

- Sentinel-1 RTC fallback is implemented and live-tested, but its evidence is not yet fused into an optical diagnosis because local SAR labels/thresholds are still required.
- Yield prediction cannot be promoted without multi-season verified yield labels.
- Government BhuNaksha/AgriStack connectors remain disabled until authorized API access.
- Production phone OTP requires provider credentials.
- The offline evidence queue is implemented; mobile deployment still requires device/GPS/photo and secure-backend testing.
- Relative management zones and human-approved GeoJSON export are implemented; machinery execution still requires target equipment specifications and field trials.

These are not safe to fake. The software interfaces and explicit gates are delivered, but production activation still depends on data, credentials, legal approval or hardware.
