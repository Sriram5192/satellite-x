"""Streamlit UI for GPS/FTW polygon recovery and explicit confirmation."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import folium
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium

from satellite_x.acquisition.pipeline import AcquisitionPipeline
from satellite_x.ai.models import DiagnosisInput
from satellite_x.ai.service import DiagnosisService
from satellite_x.analytics.models import AnalyticsInput
from satellite_x.analytics.service import AnalyticsService
from satellite_x.config import Settings
from satellite_x.identity import IdentityStore
from satellite_x.models import FarmInput
from satellite_x.polygon.errors import BoundaryValidationError
from satellite_x.polygon.models import PolygonRecoveryInput, PolygonRecoveryResult
from satellite_x.polygon.service import PolygonRecoveryService
from satellite_x.preprocessing.models import PreprocessingInput, SarFallbackInput
from satellite_x.preprocessing.sar import SarFallbackService
from satellite_x.preprocessing.service import PreprocessingService
from satellite_x.resilience import ResilienceInput, ResilienceService

LOCAL_TODAY = datetime.now(ZoneInfo("Asia/Kolkata")).date()

st.set_page_config(page_title="SATELLITE-X Polygon Recovery", page_icon="🛰️", layout="wide")
st.title("🛰️ SATELLITE-X — Polygon Recovery & Confirmation")
st.caption(
    "No phone number, Aadhaar, or owner name is collected. GPS is processed only after consent. "
    "FTW polygons are operational predictions, not legal cadastral boundaries."
)

if "recovery" not in st.session_state:
    st.session_state.recovery = None
if "confirmed" not in st.session_state:
    st.session_state.confirmed = None
if "preprocessing" not in st.session_state:
    st.session_state.preprocessing = None
if "sar_fallback" not in st.session_state:
    st.session_state.sar_fallback = None
if "analytics" not in st.session_state:
    st.session_state.analytics = None
if "diagnosis" not in st.session_state:
    st.session_state.diagnosis = None
if "identity_token" not in st.session_state:
    st.session_state.identity_token = None

identity_path = os.getenv("SATELLITE_X_IDENTITY_DB")
demo_mode = os.getenv("SATELLITE_X_DEMO_MODE") == "1"
principal = None
identity_store = None
if identity_path:
    identity_store = IdentityStore(identity_path)
    identity_store.initialize()
    with st.sidebar:
        st.header("Authenticated Farmer")
        if st.session_state.identity_token:
            try:
                principal = identity_store.authenticate(st.session_state.identity_token)
            except PermissionError:
                st.session_state.identity_token = None
        if principal is None:
            login_user = st.text_input("Account ID")
            login_password = st.text_input("Password", type="password")
            if st.button("Sign in", width="stretch"):
                try:
                    st.session_state.identity_token = identity_store.login(
                        login_user, login_password
                    )
                    st.rerun()
                except PermissionError:
                    st.error("Invalid credentials")
            st.info("Sign in is required before field analysis.")
            st.stop()
        if principal.role != "farmer":
            st.error("This portal permits farmer accounts only.")
            st.stop()
        st.success(f"Signed in: {principal.user_id}")
        if st.button("Sign out", width="stretch"):
            identity_store.revoke(st.session_state.identity_token)
            st.session_state.identity_token = None
            st.rerun()
elif not demo_mode:
    st.error(
        "Authentication is not configured. Set SATELLITE_X_IDENTITY_DB, or explicitly set "
        "SATELLITE_X_DEMO_MODE=1 for non-production integration testing."
    )
    st.stop()
else:
    st.warning("DEMO MODE: authentication and own-field enforcement are disabled.")

with st.sidebar:
    st.header("Field Search")
    if st.button("Load accepted crop integration test"):
        st.session_state.demo_lat = 16.064444813421694
        st.session_state.demo_lon = 80.6059204280875
        st.session_state.demo_acres = 2.4791228671574923
    latitude = st.number_input(
        "Latitude",
        value=float(st.session_state.get("demo_lat", 16.3067)),
        format="%.8f",
    )
    longitude = st.number_input(
        "Longitude",
        value=float(st.session_state.get("demo_lon", 80.4365)),
        format="%.8f",
    )
    acres = st.number_input(
        "Reported acres",
        min_value=0.01,
        value=float(st.session_state.get("demo_acres", 5.0)),
        step=0.1,
    )
    field_id = st.text_input("Field ID", value="AP_FIELD_001")
    subdivision = st.text_input("State code", value="AP", max_chars=3).upper()
    consent = st.checkbox(
        "I consent to using this GPS point only for field-boundary recovery."
    )
    recover_clicked = st.button("Recover Polygon", type="primary", width="stretch")

request = None
try:
    request = PolygonRecoveryInput(
        field_id=field_id,
        latitude=latitude,
        longitude=longitude,
        acres=acres,
        location_consent=consent,
        country_code="IN",
        subdivision_code=subdivision,
        search_radius_m=300,
        gps_tolerance_m=30,
    )
except Exception as exc:
    if recover_clicked:
        st.error(f"Input validation failed: {exc}")

if recover_clicked and request is not None:
    with st.spinner("Checking location and querying open FTW field polygons..."):
        with PolygonRecoveryService(Settings.from_env()) as service:
            st.session_state.recovery = service.recover(request)
            st.session_state.confirmed = None
            st.session_state.preprocessing = None
            st.session_state.sar_fallback = None
            st.session_state.analytics = None
            st.session_state.diagnosis = None

result: PolygonRecoveryResult | None = st.session_state.recovery
if result is None:
    st.info("Enter a GPS point, grant consent, and run polygon recovery.")
    st.stop()

status_colors = {
    "candidates_found": "green",
    "no_candidate": "orange",
    "rejected_location": "red",
    "preflight_unavailable": "red",
}
st.markdown(
    f"### Recovery status: :{status_colors[result.status]}[{result.status.upper()}]"
)

left, right = st.columns([1, 2])
with left:
    if result.location:
        st.subheader("Location preflight")
        st.json(result.location.model_dump(mode="json"))
    if result.reason_codes:
        st.write("**Reason codes:**", ", ".join(result.reason_codes))
    for warning in result.warnings:
        st.warning(warning)

with right:
    map_view = folium.Map(
        location=[result.request.latitude, result.request.longitude],
        zoom_start=16,
        control_scale=True,
        tiles="OpenStreetMap",
    )
    folium.CircleMarker(
        [result.request.latitude, result.request.longitude],
        radius=7,
        color="#d62728",
        fill=True,
        tooltip="Consent-bound GPS point",
    ).add_to(map_view)
    candidate_colors = {"HIGH": "#16a34a", "MEDIUM": "#f59e0b", "LOW": "#dc2626"}
    for candidate in result.candidates:
        folium.GeoJson(
            candidate.geometry_geojson,
            name=candidate.candidate_id,
            style_function=lambda _feature, color=candidate_colors[candidate.quality]: {
                "color": color,
                "weight": 3,
                "fillOpacity": 0.18,
            },
            tooltip=(
                f"{candidate.candidate_id} | {candidate.area_acres:.3f} ac | "
                f"score {candidate.score_pct:.1f}% | {candidate.quality}"
            ),
        ).add_to(map_view)
    Draw(
        export=False,
        draw_options={
            "polyline": False,
            "rectangle": False,
            "circle": False,
            "circlemarker": False,
            "marker": False,
            "polygon": {"allowIntersection": False, "showArea": True},
        },
        edit_options={"edit": True, "remove": True},
    ).add_to(map_view)
    folium.LayerControl().add_to(map_view)
    map_state = st_folium(
        map_view,
        height=610,
        use_container_width=True,
        returned_objects=["all_drawings", "last_active_drawing"],
        key=f"polygon-map-{result.checked_at.isoformat()}",
    )

st.subheader("Candidate comparison")
if result.candidates:
    st.dataframe(
        [
            {
                "candidate": item.candidate_id,
                "year": item.year,
                "area_acres": item.area_acres,
                "area_diff_pct": item.area_difference_pct,
                "score_pct": item.score_pct,
                "quality": item.quality,
                "contains_gps": item.contains_input_point,
                "legal_boundary": item.legal_boundary,
            }
            for item in result.candidates
        ],
        width="stretch",
    )


def save_confirmation(confirmation) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", confirmation.field_id)
    path = Path("outputs") / f"confirmed_boundary_{safe_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(confirmation.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


candidate_col, drawn_col, upload_col = st.columns(3)
with candidate_col:
    st.markdown("#### Confirm an FTW candidate")
    if result.candidates:
        selected_id = st.selectbox(
            "Candidate",
            [item.candidate_id for item in result.candidates],
            index=0,
        )
        if st.button("Confirm selected candidate", width="stretch"):
            with PolygonRecoveryService(Settings.from_env()) as service:
                confirmation = service.confirm_candidate(result, selected_id)
            path = save_confirmation(confirmation)
            st.session_state.confirmed = confirmation
            st.success(f"Confirmed and saved: {path}")
    else:
        st.caption("No FTW candidate is available.")

with drawn_col:
    st.markdown("#### Confirm a drawn polygon")
    drawings = (map_state or {}).get("all_drawings") or []
    st.caption(f"Map drawings available: {len(drawings)}")
    if st.button("Validate latest drawing", width="stretch", disabled=not drawings):
        geometry = drawings[-1].get("geometry", drawings[-1])
        try:
            with PolygonRecoveryService(Settings.from_env()) as service:
                confirmation = service.confirm_uploaded_or_drawn(
                    result.request, geometry, source="user_drawn"
                )
            path = save_confirmation(confirmation)
            st.session_state.confirmed = confirmation
            st.success(f"Drawn polygon confirmed and saved: {path}")
        except BoundaryValidationError as exc:
            st.error(str(exc))

with upload_col:
    st.markdown("#### Import official/user GeoJSON")
    uploaded = st.file_uploader("GeoJSON", type=["json", "geojson"])
    source = st.selectbox("Source", ["official_fmb", "user_drawn"])
    if st.button("Validate uploaded polygon", width="stretch", disabled=uploaded is None):
        try:
            payload = json.loads(uploaded.getvalue().decode("utf-8"))
            geometry = payload.get("geometry") if payload.get("type") == "Feature" else payload
            with PolygonRecoveryService(Settings.from_env()) as service:
                confirmation = service.confirm_uploaded_or_drawn(
                    result.request, geometry, source=source
                )
            path = save_confirmation(confirmation)
            st.session_state.confirmed = confirmation
            st.success(f"Uploaded polygon confirmed and saved: {path}")
        except Exception as exc:
            st.error(f"Upload validation failed: {exc}")

if st.session_state.confirmed:
    confirmation = st.session_state.confirmed
    st.subheader("Confirmed boundary output")
    st.json(confirmation.model_dump(mode="json"))

    if principal is not None and confirmation.field_id not in principal.owned_field_ids:
        st.warning("This confirmed field is not yet linked to the authenticated farmer.")
        if st.button("Link confirmed field to my account", type="primary", width="stretch"):
            identity_store.link_confirmed_boundary(
                principal.user_id, confirmation
            )
            st.rerun()
        st.stop()

    st.subheader("Set 2 — Field Quality & Urban Gate")
    analysis_date = st.date_input("Analysis date", value=LOCAL_TODAY)
    scan_days = st.number_input(
        "Original scene range (days)", min_value=1, max_value=180, value=30
    )
    if st.button("Run Set 2 preprocessing", type="primary", width="stretch"):
        preprocess_request = PreprocessingInput(
            field_id=confirmation.field_id,
            latitude=result.request.latitude,
            longitude=result.request.longitude,
            boundary_geojson=confirmation.boundary_geojson,
            analysis_date=analysis_date,
            scan_range_days=int(scan_days),
            expansion_days=30,
            location_blocking=bool(result.location and result.location.blocking),
            location_reason=(
                result.location.reason_code if result.location else None
            ),
        )
        with st.spinner("Evaluating field SCL, calibrated bands, and scene fallbacks..."):
            with PreprocessingService(Settings.from_env()) as service:
                st.session_state.preprocessing = service.run(preprocess_request)

    if st.button("Run Sentinel-1 RTC cloud fallback", width="stretch"):
        sar_request = SarFallbackInput(
            field_id=confirmation.field_id,
            boundary_geojson=confirmation.boundary_geojson,
            analysis_date=analysis_date,
            scan_range_days=int(scan_days),
        )
        with st.spinner("Clipping terrain-corrected VV/VH radar evidence..."):
            with SarFallbackService(Settings.from_env()) as service:
                st.session_state.sar_fallback = service.run(sar_request)

if st.session_state.sar_fallback:
    sar = st.session_state.sar_fallback
    st.markdown(f"### Sentinel-1 RTC status: `{sar.status}`")
    if sar.status == "accepted":
        cols = st.columns(4)
        cols[0].metric("SAR scene", sar.scene_id)
        cols[1].metric("Valid pixels", sar.valid_pixels)
        cols[2].metric("VV mean", f"{sar.vv_db_mean:.3f} dB")
        cols[3].metric("VH mean", f"{sar.vh_db_mean:.3f} dB")
    for warning in sar.warnings:
        st.warning(warning)

if st.session_state.preprocessing:
    preprocessing = st.session_state.preprocessing
    st.markdown(f"### Set 2 status: `{preprocessing.status}`")
    cols = st.columns(4)
    cols[0].metric(
        "Selected scene",
        preprocessing.selected_scene.scene_id if preprocessing.selected_scene else "None",
    )
    cols[1].metric(
        "Quality",
        preprocessing.selected_quality.quality if preprocessing.selected_quality else "None",
    )
    cols[2].metric(
        "Field valid %",
        (
            f"{preprocessing.selected_quality.field_valid_pct:.2f}%"
            if preprocessing.selected_quality
            else "—"
        ),
    )
    cols[3].metric(
        "Spectral valid %",
        (
            f"{preprocessing.urban_gate.spectral_valid_pct:.2f}%"
            if preprocessing.urban_gate
            else "—"
        ),
    )
    if preprocessing.urban_gate:
        st.json(preprocessing.urban_gate.model_dump(mode="json"))
    st.dataframe(
        [candidate.model_dump(mode="json") for candidate in preprocessing.candidates],
        width="stretch",
    )
    for warning in preprocessing.warnings:
        st.warning(warning)

    resilience = ResilienceService().run(
        ResilienceInput(
            field_id=preprocessing.request.field_id,
            optical=preprocessing,
            sar=st.session_state.sar_fallback,
        )
    )
    st.markdown(f"### Multimodal route: `{resilience.status}`")
    for warning in resilience.warnings:
        st.info(warning)

    if preprocessing.status == "accepted":
        st.subheader("Set 3 & Set 4 — Analytics and Advisory")
        crop_col, sowing_col = st.columns(2)
        crop_type = crop_col.selectbox("Crop", ["chilli", "cotton", "paddy"])
        sowing_date = sowing_col.date_input(
            "Sowing date", value=LOCAL_TODAY - timedelta(days=64)
        )
        if st.button("Run Set 3 analytics + Set 4 diagnosis", type="primary", width="stretch"):
            confirmation = st.session_state.confirmed
            farm = FarmInput(
                field_id=confirmation.field_id,
                latitude=result.request.latitude,
                longitude=result.request.longitude,
                crop_type=crop_type,
                sowing_date=sowing_date,
                analysis_date=preprocessing.selected_scene.acquired_at.date(),
                scan_range_days=preprocessing.request.scan_range_days,
                acres=confirmation.validation.area_acres,
                boundary_geojson=confirmation.boundary_geojson,
            )
            with st.spinner("Acquiring weather/soil and computing seven indices..."):
                with AcquisitionPipeline(Settings.from_env()) as acquisition:
                    raw = acquisition.run(farm)
                analytics = AnalyticsService().run(
                    AnalyticsInput(
                        field_id=farm.field_id,
                        crop_type=farm.crop_type,
                        sowing_date=farm.sowing_date,
                        preprocessing=preprocessing,
                        weather=raw.weather,
                        soil=raw.soil,
                    )
                )
                diagnosis = DiagnosisService().run(
                    DiagnosisInput(
                        analytics=analytics,
                        quality_tag=preprocessing.selected_quality.quality,
                        sowing_date_quality="known",
                    )
                )
                st.session_state.analytics = analytics
                st.session_state.diagnosis = diagnosis

if st.session_state.analytics:
    analytics = st.session_state.analytics
    diagnosis = st.session_state.diagnosis
    st.markdown("### Set 3 index means")
    st.dataframe(
        [
            {"index": name.upper(), "mean": stats.mean, "median": stats.median,
             "p10": stats.p10, "p90": stats.p90, "pixels": stats.valid_pixels}
            for name, stats in analytics.indices.items()
        ],
        width="stretch",
    )
    cards = st.columns(4)
    cards[0].metric("Crop stage", analytics.phenology.stage_name)
    cards[1].metric("DAS", analytics.phenology.das)
    cards[2].metric("Water balance 15d", f"{analytics.water_balance.water_balance_15d_mm:.2f} mm")
    cards[3].metric("Confidence", f"{diagnosis.confidence.final_confidence_pct:.1f}%")
    st.markdown(f"### Verdict: `{diagnosis.verdict}`")
    st.success(diagnosis.action_telugu)
    st.info(diagnosis.action_english)
    st.json(diagnosis.model_dump(mode="json"))
