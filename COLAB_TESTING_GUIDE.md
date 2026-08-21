# SATELLITE-X v0.8.0 — Google Colab Testing Guide

## Required files

1. `SATELLITE-X_v0.8.0_COLAB_READY.zip`
2. `SATELLITE_X_v0.8.0_COLAB_VERIFICATION.ipynb`

## Steps

1. Open https://colab.research.google.com/.
2. Choose **File → Upload notebook** and upload the `.ipynb` file.
3. Run the first cell and upload the release ZIP when prompted.
4. Run every cell in order using **Runtime → Run all**.
5. Do not mark verification complete if any assertion or command fails.
6. At the end Colab downloads `colab_verification_summary.json`.

## Expected gates

```text
95/95 deterministic tests PASS
8/8 live tests PASS
32 schemas valid
Set 2 oracle PASS
Set 3/4 scene-aligned oracle PASS
Time-series oracle PASS
SAR oracle PASS
Orbit/communications oracle 16/16 PASS
Mobile/API security audits PASS
Demo Streamlit flow PASS
Authenticated own-field Streamlit flow PASS
```

## Honest interpretation

A temporary live API outage may cause the live gate to fail. Re-run only after checking the upstream provider; never edit the test to force a pass.

Colab verification does not activate official government APIs, real SMS delivery, hardware, machinery, cadastral ownership, verified yield labels or physical field validation. Those require genuine external credentials/evidence and must remain fail-closed until supplied.
