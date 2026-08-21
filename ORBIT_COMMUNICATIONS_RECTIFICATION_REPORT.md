# SATELLITE-X v0.8.0 — Orbit & Communications Rectification

**Date:** 2026-08-20

## Scope correction

SATELLITE-X agriculture consumes processed Earth-observation products; it does not operate the Sentinel transponder or ESA ground segment. Therefore:

- live TLE/pass provenance is integrated as an optional agriculture acquisition/provenance layer;
- ITU/link-budget/contact contention is a separate simulator;
- generic 100+ station traffic is never represented as real Sentinel operations;
- TLE/SGP4 is not called live telemetry or beacon calibration.

## Implemented rectifications

### Live orbit and Doppler

- CelesTrak live TLE by NORAD ID;
- strict TLE two-line checksum and NORAD validation;
- epoch freshness state;
- Skyfield/SGP4 pass windows;
- elevation, azimuth, slant range and finite-difference range rate;
- per-sample downlink Doppler;
- fail-closed seven-day TLE epoch policy.

Live Sentinel-2A result:

```text
NORAD: 40697
TLE epoch: 2026-08-19T18:44:47.804657Z
Guntur passes in next 24h: 2
First-pass maximum elevation: ~58.79°
First-pass maximum |Doppler| at 8.2 GHz: ~177.6 kHz
```

The selected agriculture scene is Sentinel-2B (`S2B`, NORAD 42063) from 2026-06-28. The current Sentinel-2B TLE is about 1,265 hours away, so the software returns `historical_tle_required` and produces no historical pass claim.

### Atmospheric attenuation

Integrated ITU-Rpy implementation of:

- ITU-R P.618 slant-path total attenuation;
- P.676 gaseous attenuation;
- P.837 rain climatology when local R0.01 is omitted;
- P.840 cloud attenuation;
- tropospheric scintillation contribution.

Guntur 8.2 GHz, 30° elevation, 0.01% exceedance, 3 m validation antenna:

```text
Modeled combined attenuation: 7.569104 dB
Calibration status: modeled_not_beacon_calibrated
```

At X-band, no ionospheric fade value is invented. A measured/calibrated ionospheric value can be supplied; otherwise the output states that none was applied.

### Thermal noise and link margin

- free-space path loss;
- receive antenna gain;
- received carrier power;
- Boltzmann thermal noise density;
- C/N0, Eb/N0 and margin;
- dynamic Doppler from range rate.

The included 38.636895 dB margin is explicitly a caller-supplied validation fixture because operational Sentinel EIRP, station G/T/noise and required Eb/N0 were not supplied.

### Dynamic contact scheduling / DES

Selected policy: `priority_earliest_deadline`, because Sentinel uses planned ground contacts rather than public on-demand transponder access.

The deterministic 120-station contention fixture includes:

- two 280 Mbit/s reference channels;
- arrivals, deadlines, priorities and requested data;
- dynamic channel assignment each time step;
- completed/dropped requests;
- transmitted/dropped data;
- throughput and utilization.

Fixture output:

```text
Requests: 120
Completed: 46
Dropped: 74
Channel utilization: 67.880952%
```

This output is a software stress fixture, not an ESA operational traffic claim.

## Independent validation

`audit/orbit_communications_reality.py` imports no SATELLITE-X modules and independently checks:

- both TLE checksums and NORAD ID;
- historical-TLE rejection;
- Skyfield elevation/range/Doppler;
- ITU gas/rain/total attenuation;
- manual FSPL/link margin/Doppler;
- DES request/data conservation and fixture label.

Result: **16/16 PASS**.

Overall suite: **95 deterministic + 7 live PASS**.

## External evidence still required

1. historical TLE near a historical scene epoch (Space-Track credentials or authorized archive);
2. measured satellite beacon and local meteorology for calibration;
3. operational EIRP, antenna G/T/noise and modem threshold;
4. authorized Sentinel contact/traffic traces;
5. real-time telemetry feed if the objective is telemetry validation rather than orbital prediction.

Without these, outputs remain model/fixture states and are not promoted to operational truth.

## Public technical references

- ESA Sentinel-2 mission publication: https://esamultimedia.esa.int/multimedia/publications/SP-1322_2/offline/download.pdf
- ESA Sentinel-2 operations: https://www.esa.int/Enabling_Support/Operations/Sentinel-2_operations
- Sentinel-2 User Handbook: https://sentinels.copernicus.eu/documents/247904/685211/Sentinel-2_User_Handbook
- CelesTrak GP data: https://celestrak.org/NORAD/elements/gp.php
- ITU-R P.618: https://www.itu.int/rec/R-REC-P.618/en
- ITU-R P.676: https://www.itu.int/rec/R-REC-P.676/en
- ITU-R P.531: https://www.itu.int/rec/R-REC-P.531/en
