# SATELLITE-X Polygon Recovery & Confirmation — Build Report

**Version:** 0.2.0  
**Build date:** 2026-08-17  
**Scope:** GPS preflight, open FTW recovery, scoring, GeoJSON validation, confirmation website  
**Not in scope yet:** authorized government legal-record API, phone OTP accounts, OCR of FMB PDFs

## Delivered architecture

```text
Consent-bound GPS + reported acres
              │
              ▼
Nominatim reverse feature + geodesic distance
              │
      road/structure/water hard gate
              │
              ▼
FTW 2024/2025 AP GeoParquet range query
              │
              ▼
Shapely topology repair + UTM metrics
              │
              ▼
GPS containment + acreage + recency score
              │
              ▼
Candidate comparison / Folium Draw / GeoJSON upload
              │
              ▼
Explicit confirmation + provenance JSON
```

## Negative reality test

Input:

```text
16.3067, 80.4365; reported area 5 acres
```

Independent reverse feature:

```text
SH288, primary highway
feature distance = 11.321 m
```

Output:

```text
status = rejected_location
reason = POINT_ON_OR_NEXT_TO_ROAD
FTW query calls = 0 in deterministic orchestration test
```

This prevents the old acreage-square behavior from silently converting a city road into a farm.

## Positive open-data reality test

Input is the point-on-surface of a real open FTW 2025 field prediction:

```text
16.1895796725143, 80.3434336669471
reported area = 1.746115 acres
nearest mapped road = 122.971 m away
```

Recovery output:

| Candidate | Year | Area | Difference | Score | Quality |
|---|---:|---:|---:|---:|---|
| `ftw-IN-AP-1537149-2025-545a8a4ecb` | 2025 | 1.744931 ac | 0.068% | 99.952% | HIGH |
| `ftw-1537148-2024` | 2024 | 1.084688 ac | 37.880% | 70.484% | MEDIUM |

The 2025 candidate was selected and explicitly confirmed:

```text
user_confirmed = true
legal_boundary = false
area = 7061.486 m²
GPS point distance = 0 m
geometry valid = true
```

## Independent oracle comparison

`audit/polygon_recovery_reality.py` imports none of the SATELLITE-X code. It independently:

1. Re-queries Nominatim for the road point
2. Recomputes geodesic feature distance
3. Re-queries the 2.58 GB Andhra Pradesh FTW GeoParquet with DuckDB range reads
4. Applies direct point-in-polygon filtering
5. Compares the independently selected FTW ID
6. Re-measures the confirmed polygon in UTM
7. Checks legal-boundary provenance

Result: **9/9 checks PASS**.

```text
direct candidate = ftw-IN-AP-1537149-2025-545a8a4ecb
system candidate = ftw-IN-AP-1537149-2025-545a8a4ecb
independent area = 7061.486 m²
system area = 7061.486 m²
legal claim = false
```

Machine evidence: `outputs/polygon_recovery_reality.json`.

## Website validation

App: `apps/polygon_app.py`

Implemented UI:

- GPS latitude/longitude and acreage input
- Explicit location-consent checkbox
- Open rural integration-test loader
- Recovery status/reason display
- Location evidence display
- FTW candidate overlay and comparison table
- Polygon drawing/editing through Folium Draw
- Candidate confirmation
- User-drawn GeoJSON confirmation
- Official/user GeoJSON upload
- Saved provenance JSON

Validation:

```text
Streamlit initial AppTest render = PASS
Streamlit live recovery interaction = PASS
HTTP /_stcore/health = 200 ok
HTTP / = 200
```

## Automated tests

```text
37/37 deterministic tests PASS
2/2 live API integration tests PASS
```

Polygon tests cover:

- Mandatory GPS consent
- Road distance blocking
- Distant-road non-blocking
- Self-intersection repair
- UTM area/perimeter calculation
- GPS containment
- Acreage mismatch filtering
- Transparent candidate ranking
- Stop-before-FTW behavior on blocked points
- Exact golden JSON regression
- Candidate confirmation
- Uploaded FMB remaining legally unverified
- Initial Streamlit render
- Live Nominatim + FTW recovery

## Provenance rules

| Source | Operational use | `legal_boundary` |
|---|---|---|
| FTW 2024/2025 | After user confirmation | `false` |
| User drawn | After validation/confirmation | `false` |
| Uploaded FMB | After shape validation; legal verification pending | `false` |
| Authorized government record/survey | Future connector only | May become `true` after verification |

## Files

- Core package: `src/satellite_x/polygon/`
- Website: `apps/polygon_app.py`
- CLI examples: `examples/polygon_*_request.json`
- Road result: `outputs/polygon_road_result.json`
- Positive result: `outputs/polygon_open_field_result.json`
- Confirmed result: `outputs/polygon_open_field_confirmed.json`
- Independent audit: `outputs/polygon_recovery_reality.json`
- JSON Schemas: `schemas/polygon_*.schema.json`, `schemas/boundary_confirmation.schema.json`

## Honest final status

**Polygon Recovery Core: PASS. Map Confirmation Engine: PASS.**

The build can safely propose and confirm an operational remote-sensing field polygon. It does not yet prove land ownership or a legal cadastral boundary. That requires the next authorized FMB/BhuNaksha/physical-survey verification connector.
