# SATELLITE-X — Farmer-only Cloud Pilot: Next Steps

Selections recorded:

- Mode: farmer-only
- Hosting: cloud
- Authentication for first pilot: password sessions
- Confirmed fields: not yet available

## Immediate blocker

A real pilot cannot start until at least one consented field exists. Target **five fields** for the first controlled pilot so field onboarding, repeated analysis and later privacy-safe aggregate behavior can all be exercised.

## Information to collect for each field

Use `templates/farmer_pilot_intake.csv`.

Required:

1. anonymous farmer user ID — do not use name, phone or Aadhaar;
2. unique field ID;
3. latitude and longitude captured at/inside the field;
4. reported acres;
5. crop type: chilli, cotton or paddy;
6. sowing date;
7. explicit GPS/boundary-processing consent and timestamp;
8. boundary source: confirmed FTW, user-drawn polygon or authorized FMB;
9. GeoJSON boundary file after confirmation.

Do not mark an FTW or user-drawn polygon as legal ownership proof.

## Recommended pilot infrastructure

- Ubuntu cloud VM in an Indian region
- minimum pilot size: 2 vCPU, 4 GB RAM, 40 GB persistent disk
- HTTPS domain/subdomain
- persistent encrypted volume
- daily encrypted database backup
- firewall: expose only 80/443; SSH restricted to administrator IP/key
- separate staging and production secrets

Google Colab must not be used as the production server.

## Password-pilot requirements

- one account per farmer;
- temporary password delivered outside the analytics application;
- minimum 12 characters;
- force replacement before broad rollout;
- never place passwords in CSV, source code, notebook, ZIP or chat;
- revocable 12-hour sessions;
- account-to-field link only from a hashed BoundaryConfirmation artifact.

## Deployment order

1. Choose cloud provider, region and domain.
2. Provision VM, persistent disk, firewall and DNS.
3. Add container/reproducible deployment, HTTPS and health checks.
4. Put Ed25519 receipt key and AES evidence key in a secret manager.
5. Initialize identity, evidence, governance and analysis databases.
6. Create farmer accounts without storing plaintext passwords.
7. Recover/draw/upload and explicitly confirm each field boundary.
8. Link the confirmation hash to the authenticated farmer.
9. Run Set 1 → Set 2 → scene-aligned Set 3 → Set 4 for each field.
10. Run authenticated PWA photo/GPS verification.
11. Verify backup restore, session revocation and audit logs.
12. Start a controlled 7–14 day pilot; do not call it agronomically validated until field observations agree.

## Pilot acceptance criteria

- every farmer can see only linked fields;
- no analysis with mismatched optical/weather dates;
- no field with fewer than nine valid spectral pixels is accepted;
- no raw API response or session token is cached by the service worker;
- evidence photo is encrypted before sync completion;
- server receipt verifies with the pinned Ed25519 public key;
- no owner name/Aadhaar in analytics records;
- every failed provider call remains explicit;
- daily backup and one restore test pass;
- farmer observation is recorded for every advisory requiring verification.

## Inputs required from the project owner before deployment

1. cloud provider choice and Indian region;
2. domain/subdomain;
3. five completed rows in `farmer_pilot_intake.csv`;
4. five boundary GeoJSON files or consent to recover/draw them;
5. secure administrator access method;
6. backup destination;
7. password delivery method for pilot users.
