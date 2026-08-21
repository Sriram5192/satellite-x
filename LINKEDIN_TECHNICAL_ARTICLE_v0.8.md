# Building SATELLITE-X: From Field Pixels to Fail-Closed Orbit & Communications Models

## Why I built it

Agriculture platforms often combine satellite imagery, weather, soil and AI into a single score. The difficult part is not calculating NDVI; it is preserving time alignment, provenance, privacy, authorization and uncertainty while external providers fail and ground truth remains incomplete.

SATELLITE-X began as a field-intelligence pipeline and evolved into a transparent verification engine spanning remote sensing, governance, offline evidence and—starting in v0.8—TLE/Doppler and communications models.

## Field intelligence without silent substitution

The agriculture workflow performs:

1. consent-bound field recovery or upload;
2. exact field raster clipping;
3. all-six-band physical validation;
4. cloud/quality and calibrated urban rejection;
5. seven vegetation/moisture/water indices;
6. crop stage and expected-NDVI context;
7. weather ending exactly on the optical scene date;
8. evidence-based diagnosis and explicit unresolved outcomes.

A material bug discovered during validation showed why alignment matters. A June 28 optical scene had initially been combined with August 17 weather. After enforcing a zero-day scene/weather gap, climatic balance changed from -35.41 mm to -12.67 mm and the deficit flag changed from true to false.

## Security and governance as computation inputs

The platform now treats trust state as part of the result:

- PBKDF2 identities and revocable sessions;
- BoundaryConfirmation-hash field ownership;
- signed authorization and case records;
- k≥5 small-group suppression;
- encrypted evidence photos;
- Ed25519 server receipts verified in browser WebCrypto;
- signed agronomist/operator/yield artifacts;
- fail-closed official connectors.

## Why TLE is not telemetry

A Two-Line Element set enables SGP4 orbital prediction. It does not prove current beacon strength, spacecraft health or RF link quality.

The v0.8 orbit module therefore:

- validates both TLE checksums and NORAD ID;
- records epoch freshness;
- calculates ground-station pass windows;
- samples elevation, range and range rate;
- calculates dynamic Doppler;
- rejects prediction when TLE epoch is too far from the requested window.

For the historical June Sentinel-2B scene, the latest TLE was roughly 1,265 hours away. The system returned `historical_tle_required` instead of back-propagating it as if it were valid.

## Atmospheric and link modeling without inventing calibration

The communications module uses ITU-R P.618 with gas, rain, cloud and tropospheric scintillation contributions. It calculates thermal noise, C/N0, Eb/N0 and link margin only when EIRP, antenna efficiency, receiver noise and modem threshold are supplied.

The included 8.2 GHz and link values are validation fixtures. They are not represented as operational Sentinel parameters. A modeled result remains `live_beacon_calibrated=false` until measurement data is supplied.

## Dynamic traffic: choosing the right abstraction

Sentinel payload data uses planned ground contacts, not a public transponder where arbitrary users request channels. I therefore selected a scheduled-contact resource model with priority and earliest-deadline ordering.

A deliberately overloaded 120-station fixture validates:

- arrivals and deadlines;
- dynamic channel assignment;
- request and data drops;
- throughput;
- capacity utilization;
- conservation of requested = transmitted + dropped data.

The fixture produced 46 completed and 74 dropped requests at 67.88% channel utilization. That is a scheduler stress result—not an ESA operational traffic claim.

## Verification

The v0.8 demo is backed by:

- 95 deterministic tests;
- 8 live integration tests;
- 32 schemas;
- direct raster/formula oracles;
- independent Google Colab verification;
- 16/16 independent orbit/communications checks.

## What is still external

The software cannot manufacture:

- live beacon or telemetry data;
- historical TLE close to an old scene;
- operational EIRP/G/T/modem thresholds;
- authorized contact/traffic traces;
- official government/SMS credentials;
- physical device and machinery field validation.

Those remain activation requirements, not hidden successes.

## Demo and source

Demo: `[DEMO_URL]`  
GitHub: `[GITHUB_URL]`

I welcome technical review from agronomists, remote-sensing specialists, satellite operators, RF engineers, geospatial developers, security reviewers and public-sector data teams.
