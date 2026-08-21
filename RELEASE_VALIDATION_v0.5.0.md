# SATELLITE-X v0.5.0 Release Validation

Date: 2026-08-17

## Executed gates

- Python compile: **PASS**
- JavaScript and service-worker syntax: **PASS**
- Deterministic tests: **74/74 PASS**
- Live integration tests: **6/6 PASS**
- JSON schemas: **26/26 structurally valid**; representative outputs validate
- Streamlit recovery → SAR → multimodal routing → Set 2 → Set 3/4: **PASS**, no exceptions
- Uvicorn startup and PWA/API health: **PASS**
- OTP → session → authenticated evidence sync → idempotent replay flow: **9/9 PASS** using an explicitly deterministic test SMS adapter
- JavaScript/Python evidence digest parity: **5/5 PASS**

## Independent data oracles

- Set 2 direct-raster oracle: **13/13 PASS**
- Set 3/4 direct-raster/formula oracle: **12/12 PASS**
- Sentinel-1 RTC direct-COG oracle: **5/5 PASS**
- Three-real-scene OLS oracle: **16/16 PASS**

## Safe activation states

- Latest real SAR is accepted but remains ancillary to optical diagnosis.
- SAR-only routing is unresolved and cannot emit optical indices or diagnosis.
- Official government connector is implemented but returns `activation_required` without official enablement/credentials.
- Real OTP is implemented but returns an explicit unconfigured state until an SMS provider is configured.
- Deterministic yield data is permanently tagged `validation_fixture_only` and cannot be approved.
- Machinery transfer remains non-automatic after agronomist, equipment-profile and operator gates.

Release archive integrity is recorded in the adjacent `.sha256` file.

See `V0.5_COMPLETION_REPORT.md`, `outputs/capability_status.json`, and `RELEASE_MANIFEST.json`.
