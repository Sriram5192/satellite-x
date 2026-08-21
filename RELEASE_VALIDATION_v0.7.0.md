# SATELLITE-X v0.7.0 Colab-Ready Validation

**Date:** 2026-08-18

## Executed locally before packaging

```text
90/90 deterministic tests PASS
6/6 live tests PASS
26/26 JSON schemas structurally valid
13/13 Set 2 oracle PASS
12/12 Set 3/4 oracle PASS with scene-aligned weather
16/16 three-scene trend oracle PASS
8/8 mobile digest/static/Ed25519 checks PASS
15/15 OTP/encrypted-photo/API/signed-receipt checks PASS
Authenticated farmer Streamlit flow PASS
```

## v0.7 trust-chain closures

- Ed25519 signed artifacts and parent-digest chains.
- Signed authoritative government authorization and active case registry.
- Unsigned government authorization denied by default.
- Farmer field links bound to BoundaryConfirmation SHA-256.
- Authenticated agronomist and machinery-operator role sessions.
- Signed prescription, operator and yield model artifacts.
- Trusted issuer signatures required for production yield labels.
- Held-out absolute-residual q95 interval replaces `1.96 × MAE`.
- AES-256-GCM encrypted photo upload required before evidence sync.
- Ed25519 receipts verified in Python and JavaScript WebCrypto.
- SQLite-shared API quotas and request-size limits.
- Recoverable exclusive OTP claim with rollback if session issuance fails.

## Honest remaining limitations

No notebook or software can manufacture official API credentials, real SMS delivery, verified multi-season labels, equipment field trials, physical device acceptance or scientifically calibrated local SAR/agronomic labels. Those paths remain fail-closed until the real inputs are supplied.

Use `SATELLITE_X_v0.7.0_COLAB_VERIFICATION.ipynb` to independently repeat the software, live-data and oracle checks in Google Colab.
