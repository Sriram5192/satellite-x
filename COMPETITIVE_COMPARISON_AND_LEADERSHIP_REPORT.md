# SATELLITE-X — Existing Systems Comparison, Algorithm Strategy & Leadership Report

**Research date:** 2026-08-17  
**Current project version:** 0.4.0  
**Assessment rule:** Built functionality, planned functionality, and competitor claims are kept separate.

## 1. Executive conclusion

SATELLITE-X is **not yet ahead of mature commercial platforms**. EOSDA, OneSoil, Cropwise, Cropin, SatSure, and Fasal already have deployed products, mobile workflows, proprietary models, agronomic ground truth, enterprise integrations, and customer operations.

SATELLITE-X can realistically lead a narrower category:

> **Open, auditable, Telugu-first, AP/Telangana-focused field-and-village agricultural decision support with strict source provenance, legal/operational boundary separation, farmer/government policy gating, and independently reproducible outputs.**

That leadership is conditional on completing Set 5 and production validation and passing multi-season field validation. Architecture alone is not market leadership.

---

## 2. Existing system landscape

### EOSDA Crop Monitoring

Publicly described capabilities include multiple vegetation indices, crop-health/risk maps, historical and forecast weather, scouting/task management, variable-rate application maps, yield estimation, mobile/offline workflows, APIs, Sentinel-2, and optional high-resolution PlanetScope imagery.

Source: https://eos.com/products/crop-monitoring/

### OneSoil

OneSoil provides automatic field boundaries, NDVI/moisture layers, field weather, scouting notes, seasonal history, variable-rate application, machinery integrations, web/mobile/API access, and AI agronomic recommendations.

Source: https://onesoil.ai/en/platform

### Syngenta Cropwise

Cropwise combines satellite field monitoring, multiple indices, weather stations, soil data, scouting, farm operations, machinery/sensor integration, farm planning, and predictive/yield workflows. It is backed by a major agronomy and input ecosystem.

Source: https://www.syngenta.com/media/media-releases/2025/data-revolutionizing-agriculture-enabling-better-decisions

### Cropin

Cropin is an India-origin enterprise agriculture cloud with farm digitization, plot-level and regional intelligence, boundary detection, cloud-free imagery frameworks, satellite/weather/IoT/drone integration, advisories, traceability, risk, ERP integrations, multilingual communication, and government/enterprise use cases.

Sources:
- https://www.cropin.com/intelligent-agriculture-cloud-cropin-data-hub/
- https://indiaai.gov.in/startup/cropin

### SatSure

SatSure is especially strong in insurance, lending, village/farm damage assessment, crop and yield risk, SAR-optical fusion, claim validation, role-based dashboards, APIs, and government/insurance deployments. Public material describes village-level and farm-level damage products, before/after analysis, and ground-verification reduction.

Source: https://www.satsure.co/solutions/insurance-and-reinsurance/

### Fasal

Fasal is strong in on-farm IoT, microclimate monitoring, soil moisture, leaf wetness, disease/pest prediction, irrigation/fertigation automation, and crop-stage-specific horticulture advisories.

Source: https://prodwrks.com/how-agritech-startup-fasal-tech-is-turning-indian-farmers-into-data-driven-decision-makers/

### Government ecosystem: FASAL, PMFBY, MNCFC and AgriStack

Government systems already use satellite, weather, drones, mobile capture, crop cutting experiments, crop acreage/yield models, area discrepancy analysis, smart sampling, and ground verification. AgriStack is building Farmer Registry, geo-referenced village maps, Crop Sown Registry and authorized/consent-based service interfaces.

Sources:
- https://agriwelfare.gov.in/en/DigiAgriDiv
- https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf
- https://issca.icrisat.org/scalable-solutions/digital-public-infrastructure-for-agriculture-agristack

### Open technology building blocks

- FarmVibes.AI: open multi-modal geospatial workflows, optical/SAR/weather/drone fusion, cloud removal and microclimate examples.
- Fields of The World / PRUE: global 2024/2025 remote-sensing field polygons at 10 m with confidence products and open model/data.

Sources:
- https://github.com/microsoft/farmvibes-ai
- https://source.coop/ftw/global-data

---

## 3. Capability comparison

Legend:

- **Yes** — publicly available/deployed capability
- **Partial** — available in some products/workflows or limited
- **Built prototype** — working in current SATELLITE-X code
- **Planned** — architecture only; not production code

| Capability | EOSDA | OneSoil | Cropwise | Cropin | SatSure | Fasal | SATELLITE-X current |
|---|---|---|---|---|---|---|---|
| Satellite crop monitoring | Yes | Yes | Yes | Yes | Yes | Partial | Acquisition built; analytics planned |
| Automatic field boundaries | Yes/custom | Yes | Partial | Yes | Yes | No core focus | **Built prototype: FTW + GPS/area gates** |
| Weather integration | Yes | Yes | Yes | Yes | Yes | Yes | **Built** |
| Multiple vegetation indices | Yes | Yes | Yes | Yes | Yes | Limited public detail | **Set 3 built and independently verified** |
| Cloud/quality handling | Yes | Yes | Yes | Yes | Yes | N/A | **Set 2 built: field SCL, spectral retry, urban gate** |
| IoT/sensor integration | Ground stations | Limited | Yes | Yes | Multi-source | **Core strength** | Contract/HMAC built; real devices pending |
| Irrigation automation | No core | Planning/VRA | Operations | Integrations | Risk focus | **Yes** | Advisory only planned; no automation |
| Scouting/mobile/offline | Yes | Yes | Yes | Yes | Officer workflows | Yes | No mobile/offline app yet |
| Yield prediction | Yes | Partial | Yes | Yes | Yes | Crop productivity support | Not built |
| VRA/machinery maps | Yes | **Strong** | **Strong** | Integrations | No core | Irrigation hardware | Not planned in first release |
| Farm operations/ERP | Yes | Partial | **Strong** | **Strong** | Enterprise APIs | Hardware operations | Not built |
| Insurance/damage workflows | Yes/custom | Limited | Limited | Risk products | **Core strength** | Limited | Architecture only |
| Government village dashboard | Custom | Country maps | Enterprise | Yes | **Yes** | No core | Planned |
| Farmer/government dual policy | Team roles | Workspaces | Roles | Enterprise roles | Roles | Farmer-focused | **Distinct architecture; not built yet** |
| Legal vs operational boundary provenance | Not publicly central | Not publicly central | Not publicly central | Land frameworks | Insurance plot provenance | N/A | **Explicit and built for polygon outputs** |
| Formula/source transparency | Proprietary | Proprietary | Proprietary | Proprietary | Proprietary | Proprietary | **Core differentiator** |
| Self-host/open deployment | No | No | No | No | No | No | **Yes** |
| Independent output oracle | Not publicly reproducible | Not publicly reproducible | Not publicly reproducible | Proprietary QA | Proprietary QA | Proprietary QA | **Built for current modules** |
| Commercial maturity | High | High | High | High | High B2B | High in IoT niche | **Prototype** |

---

## 4. Where existing products are clearly ahead

1. **Operational maturity:** deployed mobile/web products, support, uptime and customer onboarding.
2. **Ground truth:** years of labeled crop, disease, yield, insurance and operational data.
3. **Higher-resolution imagery:** commercial 3 m or better imagery improves small-field monitoring.
4. **Agronomic depth:** Cropwise/Cropin/Fasal have stronger crop practice, input and disease knowledge.
5. **Enterprise workflows:** ERP, machinery, VRA, traceability, insurance and banking integrations.
6. **Mobile/offline scouting:** mature apps with photos, notes, routes and synchronization.
7. **Validated models:** production models have field pilots and customer outcome evidence.
8. **Scale:** country/portfolio-scale data infrastructure already exists.

SATELLITE-X should not market itself as globally superior before matching these basics.

---

## 5. Where SATELLITE-X can differentiate

### A. Auditability by design

Every result can carry:

```text
source URL / scene ID
band scale and offset
cloud/SCL evidence
formula inputs
fallback source
confidence penalties
comparison oracle
```

This is stronger than a black-box “AI says stress” experience.

### B. Honest evidence hierarchy

```text
Live exact data
→ exact cache
→ explicit baseline
→ unavailable
```

Baseline soil does not masquerade as live evidence. Unsigned/stale IoT does not become live. Cloud pixels do not produce crop diagnosis.

### C. Legal parcel vs crop field separation

SATELLITE-X explicitly distinguishes:

```text
remote-sensing polygon
user-confirmed operational crop polygon
official legal/cadastral parcel
```

This is valuable for farmer advisories, damage assessment, government access and disputes.

### D. AP/Telangana localization

The system can specialize in:

- Cotton, chilli and paddy phenology
- Telugu advisories
- Andhra Pradesh/Telangana seasons
- Local damage patterns
- Village/mandal/district workflows
- Smallholder UX

A focused regional model can outperform a generic global model within its validated scope.

### E. Farmer + government dual delivery

One evidence core can produce:

```text
Farmer: own-field Telugu action
Government: anonymized village aggregate
Investigation: permission/case-scoped parcel evidence
```

The policy gateway, human verification and audit trail can become a public-sector differentiator.

### F. Open/self-hosted deployment

State departments, universities and cooperatives can inspect, host and modify the algorithms without surrendering all data to a closed SaaS vendor.

### G. Reproducible reality gates

The current code independently re-queries authoritative sources and compares IDs, values, geometry and area instead of only testing internal functions.

---

## 6. Algorithm architecture required to lead

### 6.1 Boundary engine

Current:

```text
Consent GPS
→ Nominatim distance gate
→ FTW GeoParquet
→ point containment
→ acreage similarity
→ topology repair
→ user confirmation
```

Advanced target:

```text
Official cadastral/AgriStack polygon (when authorized)
→ FTW PRUE candidate
→ multi-season stability
→ cropland consensus
→ road/building/water overlap penalties
→ Delineate-Anything/SAM2 refinement
→ user/GPS confirmation
```

### 6.2 Cloud-resilient preprocessing

```text
Sentinel-2 SCL quality
+ Sentinel-1 SAR during monsoon/cloud
+ per-field valid-pixel percentage
+ temporal composite
+ calibration harmonization
```

The current single optical-scene path cannot lead during persistent monsoon clouds.

### 6.3 Feature stack

```text
Optical: NDVI, EVI, SAVI, NDRE, NDMI, NDWI, GNDVI
SAR: VV, VH, VV/VH, temporal coherence/change
Weather: rain, ET0, temperature, humidity, wind
Soil: live/lab/model source quality
Crop: DAS, stage, expected phenology envelope
IoT: signed/fresh/calibrated sensor evidence
```

### 6.4 Differential diagnosis before opaque ML

Use explainable elimination first:

```text
Low NDVI + low NDMI + negative water balance
→ water stress evidence

Low NDVI + high humidity + wet balance
→ disease-risk candidate; ground check required

Low NDVI + low NDRE + verified low nitrogen
→ nitrogen-deficiency evidence

Low NDVI + maturity DAS
→ expected senescence; suppress false alarm
```

ML should rank evidence, not silently replace agronomic logic.

### 6.5 Time-series models

Progression:

1. Robust rolling median and slope baseline
2. Seasonal z-score against crop-stage peers
3. Change-point detection
4. Temporal CNN/U-TAE/Transformer after enough labels
5. Conformal or calibrated uncertainty intervals

Do not start with a large deep model before ground labels exist.

### 6.6 Damage engine

```text
Before-event clear baseline
+ after-event optical/SAR
+ rainfall/flood overlays
+ phenology-normalized difference
→ affected polygon
→ severity and acres
→ geotagged field verification
```

Satellite output remains “estimated/suspected” until human verification.

### 6.7 Confidence engine 2.0

Move beyond a simple weighted score:

```text
Data quality
Data completeness
Source agreement
Temporal stability
Model calibration
Out-of-distribution score
Ground verification status
```

Track Expected Calibration Error, Brier score and confidence-vs-accuracy curves.

### 6.8 Village scale

```text
Official village GeoJSON
→ 1–5 km tiles
→ candidate fields
→ parallel per-field processing
→ PostGIS/H3 aggregation
→ anonymized village statistics
```

Use idempotent jobs, source snapshots and reproducible run IDs.

---

## 7. End-to-end operation

```text
1. User/officer authenticated
2. Policy gateway checks role, consent, jurisdiction and purpose
3. Legal/operational polygon resolved
4. Satellite, weather, soil and IoT acquired with provenance
5. Candidate scenes ranked by field SCL quality
6. Clean calibrated pixels produced
7. Optical/SAR/weather/soil/crop-stage features computed
8. Differential diagnosis generates evidence matrix
9. Confidence and suppression rules applied
10. Output filtered by audience
11. Farmer/official adds ground verification
12. Verified feedback becomes labeled model data
13. Periodic calibration and drift reports decide model promotion
```

The feedback loop—not the dashboard—is what eventually creates a defensible lead.

---

## 8. Validation gates before claiming leadership

### Boundary

- Point/parcel matching accuracy
- Polygon IoU against surveyed/FMB boundaries
- Area error by field-size bucket
- Special reporting for sub-hectare fields

### Crop and stress

- Crop classification precision/recall per crop/district/season
- Stress alert precision and false-alert rate
- Detection lead time before visible damage
- Agronomist-confirmed root cause rate

### Damage

- Affected-area error vs field survey/drone/official assessment
- Severity agreement
- Cloud/SAR failure rate

### Advisory

- Agronomist approval rate
- Farmer comprehension in Telugu
- Action adoption rate
- Outcome/cost/water impact

### Confidence

- Calibration curves
- Brier score
- Error rate at HIGH/MEDIUM/LOW confidence
- Out-of-distribution rejection performance

### Product

- Village run time and cost
- API uptime
- Offline/mobile success
- Security and privacy audits
- Government audit-log completeness

Until these are measured over multiple seasons, “leadership” is only a hypothesis.

---

## 9. Recommended moat strategy

### Moat 1: Verified local data

Partner with agriculture universities, RBKs, FPOs and field officers to create crop-stage, stress, disease, yield and damage labels for AP/Telangana.

### Moat 2: Transparent evidence ledger

Store every source, transformation, formula, model version and human verification event. Make reports reproducible.

### Moat 3: Telugu action layer

Convert evidence into stage-specific, local, simple advisories—not merely maps and index charts.

### Moat 4: Government/farmer trust architecture

Consent-bound farmer access, anonymized village analytics, case-scoped parcel access, and no automated accusation.

### Moat 5: Open public-sector deployment

Self-hosted, inspectable algorithms and open standards can differentiate SATELLITE-X from closed SaaS platforms.

### Moat 6: Optical + SAR monsoon resilience

Sentinel-1/Sentinel-2 fusion can become essential for Andhra monsoon and flood workflows.

---

## 10. Build priorities

### Priority 1 — Finish the trustworthy core

- Set 2 field SCL ranking, masks and urban gate
- Sentinel-1 SAR fallback
- Extend Set 3 with multi-scene time series and local calibration
- Persist source snapshots and run IDs

### Priority 2 — Prove agronomy

- Field survey protocol
- Ground-verification app
- Cotton/chilli/paddy labels
- Accuracy and calibration dashboard

### Priority 3 — Dual delivery

- Farmer Telugu dashboard
- Government authorization/RBAC
- Village aggregation
- Damage verification workflow

### Priority 4 — Product maturity

- Mobile/offline scouting
- Notifications
- Operations/ERP connectors
- Monitoring, backup, security and cost controls

### Priority 5 — Advanced models

- Temporal ML
- SAR-optical fusion
- Yield models
- Calibrated anomaly detection
- Active learning from verified cases

---

## 11. SWOT

### Strengths

- Open and self-hostable
- Formula/source transparency
- Real API execution and independent oracle tests
- Strong provenance and fallback labeling
- Legal vs operational polygon separation
- Regional crop/phenology focus
- Farmer/government policy architecture

### Weaknesses

- Set 5 final multi-role delivery is not complete
- No agronomic ground-truth benchmark yet
- No mobile/offline product
- No high-resolution commercial imagery
- No yield/VRA/machinery workflows
- No production OTP/government connector
- Small-field and cloud limitations

### Opportunities

- AP/Telangana Telugu-first niche
- AgriStack/UFSI integration after authorization
- PMFBY/village damage verification
- FPO/cooperative monitoring
- University and public-sector open deployments
- Monsoon SAR analytics

### Threats

- Strong incumbents with data and distribution
- Government procurement/integration delays
- Incorrect satellite-to-disease inference
- Privacy and land-record risks
- 10 m smallholder boundary limits
- Free/global competitors adding AI copilots rapidly

---

## 12. Final verdict

### Today

```text
SATELLITE-X = promising, auditable technical prototype
Not yet = production agronomy platform
Not yet = competitor leader
```

### Defensible leadership target

```text
The leading open, transparent and Telugu-first AP/Telangana platform
for verified field advisories, village damage intelligence and
permission-controlled government workflows.
```

### Why it can work

The project combines proven open data and models with a trust layer that many products do not make central: explicit boundary provenance, evidence-level fallbacks, field-quality gates, policy-scoped access, independent verification and local-language action.

### What will decide success

Not the number of formulas or dashboard features. Success depends on:

1. Multi-season local ground truth
2. Low false-alarm rates
3. Calibrated confidence
4. Useful Telugu actions
5. Government/FPO workflows
6. Reproducible evidence
7. Fast and affordable village-scale operation

If those seven are proven, SATELLITE-X can lead its chosen regional/public-interest segment. Without them, it remains an architecture demo behind mature competitors.
