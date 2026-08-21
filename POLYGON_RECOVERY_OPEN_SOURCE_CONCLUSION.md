# SATELLITE-X — Open-Source Polygon Recovery Research & Conclusion

**Research date:** 2026-08-17

## Conclusion

Yes, an open-source polygon recovery layer can remove most manual work. It cannot safely infer an exact legal farm boundary from only a wrong city coordinate and an acreage value. The production solution should be a **hybrid cascade: official cadastral polygon → global predicted field polygon → local AI delineation → user/GPS confirmation**.

A generated acreage square must be used only as a search area, never as the final field boundary.

## What is available now

### 1. Global Fields of The World (FTW) — best first automatic source

The 2026 Global FTW release provides 2024 and 2025 model-inferred field polygons from Sentinel-2, distributed as open CC-BY-4.0 GeoParquet/PMTiles. It includes per-polygon area, year, method, and confidence. The polygons are remote-sensing field units, not legal/cadastral parcels.

- Dataset: https://source.coop/ftw/global-data
- Vector guide: https://data.source.coop/ftw/global-data/predictions/vectors/llms.txt
- Model/tools: https://github.com/fieldsoftheworld/ftw-baselines
- PRUE: https://github.com/fieldsoftheworld/ftw-prue

Independent test against the current example point (`16.3067, 80.4365`):

```text
FTW polygon containing point: 0
FTW polygons intersecting ±0.003° search box: 0
```

This independently supports the earlier road/non-farm finding. The system must not jump to a distant predicted field just because its area resembles five acres.

### 2. Agribound / FTW PRUE — best local inference fallback

Agribound is an Apache-2.0 Python toolkit that integrates FTW, Delineate-Anything, foundation models, ensembles, cropland filtering, polygonization, and optional SAM2 refinement. FTW also ships pretrained models and inference/polygonize tools.

- Agribound: https://github.com/montimaj/agribound
- FTW baselines: https://github.com/fieldsoftheworld/ftw-baselines
- Delineate Anything: https://github.com/Lavreniuk/Delineate-Anything

Recommended local inference input:

- Two or more cloud-free Sentinel-2 seasonal composites
- RGB + NIR surface reflectance
- Cropland/non-crop mask
- Point/acreage search AOI
- FTW PRUE as primary model
- Delineate-Anything as a second model
- Ensemble agreement + SAM2 only as refinement

### 3. SamGeo / Geo-SAM — interactive refinement, not primary truth

SamGeo can segment GeoTIFF imagery from point/box prompts and export GeoJSON/GeoPackage. Geo-SAM provides a QGIS workflow. It is useful for refining a proposed field, but generic SAM may segment roads, tree blocks, water, or texture changes unless constrained by cropland masks and model candidates.

- SamGeo: https://github.com/opengeos/segment-geospatial
- Geo-SAM: https://github.com/coolzhao/Geo-SAM

### 4. AP BhuNaksha/FMB — best legal/cadastral source

BhuNaksha is NIC's open-source cadastral mapping platform. The Andhra Pradesh portal provides village/parcel/FMB operations using district, mandal, village, and survey number.

- Official AP portal: https://bhunaksha.ap.gov.in/bhunakshalpm/28/index.jsp
- NIC platform overview: https://bhunaksha.nic.in/bhunaksha/resources/10_Cadastral%20Mapping_%20BhunakshaBhunaksha-small.pdf

This should have priority when a survey number is available. Access to official data does not imply that a stable public bulk/API endpoint exists; use documented access/import, not unauthorized scraping. A cadastral plot may also differ from the currently cultivated field unit.

### 5. Terra Draw / QField — open confirmation layer

- Terra Draw is MIT-licensed and supports MapLibre, Leaflet, OpenLayers, and other map libraries: https://github.com/JamesLMilner/terra-draw
- QField is open-source mobile GIS for field data collection: https://qfield.org

Terra Draw should be embedded in the dashboard for final edit/confirm. QField or a custom GPS walk can collect a boundary when imagery/model confidence is insufficient.

## Hard limitation: resolution

Sentinel-2's freely accessible optical bands are 10 m. This is useful for many fields, but small/irregular Indian parcels and low-contrast neighboring fields may merge or disappear. Published smallholder research found higher-resolution imagery and India-specific labels were required for operational accuracy. Therefore AI should propose polygons, not silently certify them.

## Recommended Polygon Recovery Engine

### Inputs

```json
{
  "latitude": 0.0,
  "longitude": 0.0,
  "acres": 5.0,
  "survey_number": null,
  "district": null,
  "mandal": null,
  "village": null,
  "user_drawn_geojson": null
}
```

### Cascade

```text
1. USER-DRAWN POLYGON PRESENT?
   └─ Validate topology/area → use after confirmation

2. SURVEY NUMBER PRESENT?
   └─ Import official BhuNaksha/FMB parcel → user verifies cultivated sub-field

3. POINT LOCATION PREFLIGHT
   ├─ road/building/water/urban → STOP, ask user to correct point
   └─ plausible cropland → continue

4. QUERY FTW 2025 + 2024
   ├─ polygon contains click
   ├─ area agrees with farmer acreage
   ├─ temporal overlap is stable
   └─ confidence/quality acceptable

5. NO GOOD FTW POLYGON?
   └─ Run local FTW PRUE + DelAny ensemble on seasonal Sentinel-2
      └─ crop mask → watershed/vectorize → SAM2 refinement

6. SCORE ALL CANDIDATES
   └─ containment + area + crop probability + temporal stability
      + model agreement − road/building/water overlap

7. USER CONFIRM/EDIT
   └─ Terra Draw in web UI or GPS walk with QField

8. SAVE PROVENANCE
   └─ source, model/version/year, score, edits, confirmation timestamp
```

## Proposed deterministic candidate score

This is a SATELLITE-X design recommendation, not a published standard:

```text
score = 0.25 × point_containment
      + 0.20 × acreage_similarity
      + 0.20 × cropland_probability
      + 0.15 × temporal_stability
      + 0.10 × model_agreement
      + 0.10 × source_confidence
      − urban/road/water/building penalties
```

Hard gates override the score:

- Point is road/building/water: reject
- Polygon does not contain click beyond GPS tolerance: reject
- Area mismatch > configured maximum: reject
- Invalid/self-intersecting geometry: reject
- No valid Sentinel pixels: reject

## Confidence policy

| Result | Action |
|---|---|
| Official survey parcel + user confirmation | Accept as cadastral source |
| FTW/local AI, high score, user confirmed | Accept as operational crop field |
| Medium score | Show 2–3 candidates for selection/edit |
| Low score | Require manual draw/GPS walk |
| Urban/no candidate | Stop; never move to a guessed nearby field |

Every AI polygon must carry:

```json
{
  "boundary_source": "ftw_global_2025",
  "legal_boundary": false,
  "model_confidence": null,
  "user_confirmed": false,
  "generated_at": "...",
  "model_version": "..."
}
```

## Final recommendation

Build a new **Polygon Recovery & Confirmation Engine** before Set 2:

1. FTW GeoParquet point/bbox query
2. AP BhuNaksha/FMB import path
3. FTW PRUE/Agribound local inference fallback
4. Terra Draw editor
5. Optional QField/GPS walk
6. Provenance and hard-stop rules

This can overcome missing polygons in normal cases. It cannot convert a city-road point into a trustworthy farm boundary without user correction, nor can it make a 10 m AI polygon legally authoritative.
