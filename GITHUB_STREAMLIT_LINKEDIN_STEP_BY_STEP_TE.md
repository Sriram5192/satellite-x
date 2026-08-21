# SATELLITE-X v0.8 — GitHub, Streamlit Demo & LinkedIn Publishing

## ముందుగా status తెలుసుకోండి

### Public v0.8 software demo

Ready:

- 95 deterministic tests
- 8 live tests
- 32 schemas
- 16/16 orbit/communications oracle
- 7/7 demo pages
- no farmer PII or production secrets

### Vadlamudi five-field private demo

Not ready for Set 2–4:

- all five boundary GeoJSON files are missing;
- three GPS points are on/next to roads;
- one field has no FTW candidate;
- one field has two candidates awaiting visual confirmation.

Do not publish the exact CSV, coordinates or boundaries.

---

# Part A — Complete the five private field boundaries

Use the **Field boundary confirmation** app.

For each field:

1. Open satellite view.
2. Move the GPS point inside the actual cultivated parcel—not the village/road point.
3. Enter the field ID and reported acres.
4. Click `Recover Polygon`.
5. If candidates appear, compare shape, GPS distance and area.
6. Explicitly confirm the correct candidate.
7. If no candidate is correct, use Draw to trace the actual parcel.
8. Save the BoundaryConfirmation/GeoJSON privately.

Required filenames:

```text
FIELD-VDM-001.geojson
FIELD-SJM-002.geojson
FIELD-VJD-003.geojson
FIELD-EDP-004.geojson
FIELD-CHB-005.geojson
```

Update `boundary_geojson_file` in the private CSV and re-upload the corrected CSV plus five files. Do not put these in GitHub.

---

# Part B — Download the public GitHub package

Use:

```text
SATELLITE-X_v0.8.0_DEMO_GITHUB_READY.zip
```

Verify the ZIP with the adjacent file:

```text
SATELLITE-X_v0.8.0_DEMO_GITHUB_READY.zip.sha256
```

Always use that file rather than an old copied hash.

Extract the ZIP on your computer. The top folder is:

```text
SATELLITE-X_v0.8.0
```

The package intentionally excludes private field CSV files, exact private recovery results and databases.

---

# Part C — Create the GitHub repository

## Recommended repository settings

```text
Repository name: satellite-x
Visibility: Public
License: Apache-2.0 (already included)
Default branch: main
```

On GitHub:

1. Sign in at https://github.com/.
2. Click the `+` icon.
3. Select `New repository`.
4. Repository name: `satellite-x`.
5. Add description:

```text
Explainable agriculture intelligence, signed governance, TLE/SGP4 Doppler and ITU-R scheduled-contact simulation.
```

6. Select `Public`.
7. Do **not** initialize README, `.gitignore`, or license—the package already contains them.
8. Click `Create repository`.

---

# Part D — Upload with GitHub Desktop (easiest)

1. Install GitHub Desktop: https://desktop.github.com/.
2. Sign in to your GitHub account.
3. Open GitHub Desktop.
4. Choose `File → New repository`.
5. Name: `satellite-x`.
6. Local path: select the extracted project parent folder.
7. If GitHub Desktop creates an extra empty folder, copy the extracted project contents into that repository folder.
8. Confirm that `private/`, `.env`, `*.db`, keys and raw photos are not listed.
9. Summary:

```text
Release SATELLITE-X v0.8.0 verified demo
```

10. Click `Commit to main`.
11. Click `Publish repository`.
12. Select `Public` and publish.

---

# Part E — Command-line method

Inside the extracted project folder:

```bash
git init
git branch -M main
git config user.name "YOUR NAME"
git config user.email "YOUR_GITHUB_EMAIL"
git add .
git status
```

Carefully inspect `git status`. It must not contain:

```text
private/
.env
*.db
private keys
farmer CSV
exact private boundaries
raw evidence photos
```

Commit:

```bash
git commit -m "Release SATELLITE-X v0.8.0 verified demo"
```

Connect the GitHub repository:

```bash
git remote add origin https://github.com/YOUR_USERNAME/satellite-x.git
git push -u origin main
```

Do not put a token in the URL. Use browser/GitHub CLI authentication.

---

# Part F — Check GitHub Actions

After push:

1. Open the repository.
2. Click `Actions`.
3. Open the `CI` workflow.
4. Wait for the green check.

CI runs:

- dependency installation;
- Python compile;
- JavaScript syntax;
- deterministic tests;
- schema export.

Do not publish the LinkedIn launch until CI is green.

---

# Part G — Create GitHub v0.8.0 release

1. Repository → `Releases`.
2. Click `Draft a new release`.
3. Tag: `v0.8.0`.
4. Title: `SATELLITE-X v0.8.0`.
5. Copy release text from:

```text
GITHUB_RELEASE_NOTES_v0.8.0.md
```

6. Attach:

```text
SATELLITE-X_v0.8.0_DEMO_GITHUB_READY.zip
SATELLITE-X_v0.8.0_DEMO_GITHUB_READY.zip.sha256
```

7. Publish release.

---

# Part H — Deploy the Streamlit public demo

## Streamlit Community Cloud

1. Open https://share.streamlit.io/.
2. Sign in with GitHub.
3. Click `Create app` / `New app`.
4. Repository: `YOUR_USERNAME/satellite-x`.
5. Branch: `main`.
6. Main file path for the interactive original-engine tester:

```text
public_demo/app.py
```

Use `apps/power_engine_demo.py` only when you want the read-only presentation dashboard.

7. In Advanced settings → Secrets, optionally add the non-secret configuration:

```toml
github_url = "https://github.com/YOUR_USERNAME/satellite-x"
session_ttl_minutes = 60
```

8. Deploy.
9. No credential secrets are required for the ephemeral public tester; it stores results only in the tester's Streamlit session.
10. Wait until the app health check passes.
10. Open every page:

```text
Executive overview
Agriculture intelligence
Orbit & Doppler
Atmosphere & link
Dynamic traffic
Security & governance
Verification & activation
```

11. Copy the final public URL, for example:

```text
https://YOUR-APP.streamlit.app
```

The demo uses `apps/requirements.txt`, which contains only Streamlit and pandas.

---

# Part I — Update public links

Replace placeholders in:

```text
LINKEDIN_LAUNCH_POST_v0.8.md
LINKEDIN_TECHNICAL_ARTICLE_v0.8.md
```

Replace:

```text
[GITHUB_URL]
[DEMO_URL]
```

with the real URLs.

---

# Part J — Publish LinkedIn launch post

1. Open LinkedIn.
2. Click `Start a post`.
3. Copy content from `LINKEDIN_LAUNCH_POST_v0.8.md`.
4. Attach:

```text
media/satellite_x_v0_8_launch_card.png
```

5. Confirm the GitHub and demo links work.
6. Do not delete the statement that demo/model/fixture states are different from live telemetry.
7. Publish.

---

# Part K — Publish LinkedIn technical article

1. LinkedIn → `Write article`.
2. Use title:

```text
Building SATELLITE-X: From Field Pixels to Fail-Closed Orbit & Communications Models
```

3. Copy `LINKEDIN_TECHNICAL_ARTICLE_v0.8.md`.
4. Use the launch card or architecture diagram as cover.
5. Add the real GitHub/demo URLs.
6. Publish after the shorter launch post.

---

# Final public-release checklist

- [ ] GitHub repository is public
- [ ] Apache-2.0 license visible
- [ ] CI workflow green
- [ ] GitHub release ZIP and checksum uploaded
- [ ] Streamlit demo opens
- [ ] All seven demo pages work
- [ ] No private CSV/coordinates/boundaries in repository
- [ ] No passwords/tokens/private keys/databases
- [ ] LinkedIn links tested
- [ ] Launch card attached
- [ ] External limitations remain visible

## What not to claim

Do not claim:

- live satellite telemetry or beacon calibration;
- historical TLE validation for the June scene;
- ESA operational EIRP/G/T/traffic;
- legal ownership from FTW/user-drawn geometry;
- five-field real analysis before all boundaries are explicitly confirmed;
- production agronomic validation before ground observations.
