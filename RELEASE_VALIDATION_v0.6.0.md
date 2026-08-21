# SATELLITE-X v0.6.0 Power-Engine Hardening Validation

**Date:** 2026-08-18 (Asia/Calcutta)

## Executed validation

```text
83/83 deterministic tests PASS
6/6 live tests PASS
26/26 JSON schemas structurally valid
13/13 Set 2 direct-raster checks PASS
12/12 Set 3/4 direct-raster/formula checks PASS
16/16 multi-scene OLS checks PASS
7/7 mobile digest/static-security checks PASS
12/12 OTP/PWA/API-flow checks PASS
Demo Streamlit full flow PASS, no exceptions
Authenticated farmer login → confirm → link → Set 2–4 PASS
```

## Material correctness correction

The selected optical scene is dated **2026-06-28**. v0.5 had combined those pixels with weather ending **2026-08-17**, producing `-35.41 mm` and `deficit_flag=true`.

v0.6 requires 15 contiguous weather days ending on the scene date. The aligned period is **2026-06-14 through 2026-06-28**:

```text
Rain15d: 67.30 mm
ET0_15d: 79.97 mm
Climatic balance: -12.67 mm
Deficit flag: false
Scene/weather gap: 0 days
```

Old mismatched weather and tampered weather summaries are rejected by deterministic tests.

## Security/privacy closures

- Farmer Streamlit fails closed without identity configuration or explicit demo mode.
- Authenticated farmer flow requires the confirmed field to be linked to that user.
- Admin role no longer bypasses data policy.
- Aggregates below five fields release no count, area, crop, verdict or confidence metrics.
- PWA queue rendering uses DOM `textContent`, not `innerHTML`.
- Service worker never intercepts/caches `/api/`.
- API responses include no-store, CSP, anti-frame, no-referrer and browser permission headers.
- Generic JSON persistence uses per-table identifier allowlists.
- Set 2 requires at least nine calibrated spectral pixels and the existing percentage threshold.

## Remaining work

All known open gaps, delays, impacts, priorities and acceptance criteria are maintained in:

`POWER_ENGINE_GAP_REGISTER_2026-08-18.md`

The remaining P0 items primarily require an authoritative approval/case/authorization chain, evidence photo storage, transactional OTP/session issuance, API quotas and asymmetric receipts. They are not hidden by the v0.6 hardening release.
