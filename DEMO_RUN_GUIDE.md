# SATELLITE-X v0.8 Demo Run Guide

## Interactive public tester — recommended main demo

```bash
python -m pip install -r public_demo/requirements.txt
PYTHONPATH=src streamlit run public_demo/app.py \
  --server.address 0.0.0.0 --server.port 8503
```

Open `http://localhost:8503`.

The tester accepts field inputs and GeoJSON/recovery/drawing, then executes the original Set 1–4 and SAR services. Results are ephemeral and downloadable; no project database persistence is enabled.

## Read-only presentation dashboard

```bash
python -m pip install -r apps/requirements.txt
PYTHONPATH=src streamlit run apps/power_engine_demo.py \
  --server.address 0.0.0.0 --server.port 8502
```

Open `http://localhost:8502`.

## Pages

1. Executive overview
2. Agriculture intelligence
3. Orbit & Doppler
4. Atmosphere & link
5. Dynamic traffic
6. Security & governance
7. Verification & activation

## Public-demo safety

- The app is read-only and uses release artifacts.
- It contains no secrets or farmer PII.
- Real/model/fixture/external states are shown on screen.
- Do not relabel link-budget fixture values as operational Sentinel parameters.
- Do not relabel TLE/SGP4 as live telemetry.

## Deployment

For a temporary review, use the live preview. For a public URL, deploy the Streamlit app to a cloud host and set the start command to:

```text
PYTHONPATH=src streamlit run apps/power_engine_demo.py --server.address 0.0.0.0 --server.port $PORT
```

Pin HTTPS, disable usage telemetry if required, and run dependency/security scans before publication.
