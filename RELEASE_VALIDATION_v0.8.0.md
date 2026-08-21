# SATELLITE-X v0.8.0 — Orbit/Communications Rectification Validation

**Date:** 2026-08-20

```text
95/95 deterministic tests PASS
8/8 live tests PASS
32/32 schemas structurally valid
16/16 independent orbit/communications checks PASS
```

Existing agriculture/security gates remain passing from v0.7.

## Added live/model evidence

- live checksum-validated CelesTrak Sentinel-2A and Sentinel-2B TLEs;
- live current-pass SGP4 test;
- two predicted Guntur Sentinel-2A passes in a 24-hour validation window;
- dynamic range-rate Doppler samples;
- ITU-R P.618/P.676/P.837/P.840 contributions;
- thermal-noise link budget with explicitly caller-supplied fixture inputs;
- 120-station scheduled-contact contention fixture;
- fail-closed historical-scene TLE state.

## Important non-claims

- TLE is not live satellite telemetry or beacon measurement.
- ITU-R is a statistical propagation model until calibrated against local measurements.
- The 8.2 GHz carrier, EIRP/noise values and 120-station load are validation inputs, not claimed ESA operational parameters.
- Sentinel-2 mission access is scheduled ground contact, not a public transponder service.
- The latest TLE is rejected for the 2026-06-28 scene; an authorized historical TLE is required.

Independent evidence: `outputs/orbit_communications_reality.json`.
Colab notebook: `SATELLITE_X_v0.8.0_COLAB_VERIFICATION.ipynb`.
