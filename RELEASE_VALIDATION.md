# SATELLITE-X v0.4.0 Release Validation

Date: 2026-08-17

## Executed gates

- Python compile: PASS
- Deterministic tests: **62/62 PASS**
- Live integration tests: **6/6 PASS**
- JSON schemas: **19/19 structurally valid**; representative real outputs validate
- Streamlit farmer flow: **PASS**, no exceptions
  - FTW recovery and confirmation
  - Sentinel-1 RTC evidence
  - Set 2 all-six-band acceptance
  - Set 3 analytics
  - Set 4 diagnosis
- Independent Set 3/4 oracle: **12/12 PASS**
- Independent Sentinel-1 RTC oracle: **5/5 PASS**
- Independent three-scene OLS oracle: **16/16 PASS**

## Executed real outputs

- Sentinel-1 RTC: 96 valid dual-polarization pixels; VV `-11.662815 dB`, VH `-22.279663 dB`
- Sentinel-2 Set 3: 26 valid pixels; NDVI `0.324206`; all seven indices computed
- Set 4: `NORMAL_OR_UNRESOLVED`, confidence `64.0%`, verification required
- Time series: three real scenes, all seven trends; quality `limited` due a 33-day scene gap
- Management zoning: three relative NDVI zones; application rates remain `null`

## Deliberately not production-activated

- Official government land/AgriStack connectors: authorization and credentials required
- Phone OTP: provider credentials and production secrets management required
- Yield: local multi-season labels and independent validation required
- Machinery execution: equipment specifications, agronomist approval, operator approval, and field trial required
- Mobile deployment: target-device GPS/photo and secure sync-backend testing required

These are machine-readable in `outputs/capability_status.json`. Artifact hashes are recorded in `RELEASE_MANIFEST.json`.
