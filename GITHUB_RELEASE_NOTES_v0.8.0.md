# SATELLITE-X v0.8.0 — Demo Release

## Highlights

- real Sentinel-2 field analytics and scene-aligned weather;
- Sentinel-1 RTC resilience evidence;
- signed privacy/governance and encrypted verification evidence;
- live checksum-validated CelesTrak TLE;
- SGP4 pass prediction and dynamic Doppler;
- ITU-R atmospheric contributions;
- thermal-noise link calculations with explicit calibration status;
- scheduled-contact dynamic channel simulation;
- read-only public demo dashboard;
- Google Colab verification notebook.

## Validation

```text
95 deterministic tests PASS
8 live tests PASS
32 schemas valid
16/16 orbit/communications oracle PASS
```

## Important scope

This release does not claim live beacon telemetry, historical-scene TLE validation, operational Sentinel EIRP/G/T/modem data or ESA traffic traces. Fixture/model/external states remain explicit.

## Interactive public tester

```bash
PYTHONPATH=src streamlit run public_demo/app.py \
  --server.address 0.0.0.0 --server.port 8503
```

The one-page tester accepts typed/uploaded/drawn field inputs and executes the original live Set 1–4 + SAR workflow. It is ephemeral, has no project database persistence, supports JSON download and clears on Exit/60-minute inactivity.

## Read-only presentation dashboard

```bash
PYTHONPATH=src streamlit run apps/power_engine_demo.py --server.port 8502
```

## Colab

Upload `SATELLITE_X_v0.8.0_COLAB_VERIFICATION.ipynb`, then upload the release ZIP in the first cell.
