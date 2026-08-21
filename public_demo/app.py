"""One-page public tester that executes the original SATELLITE-X core services."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import folium
import pandas as pd
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium

from satellite_x.acquisition.pipeline import AcquisitionPipeline
from satellite_x.ai.models import DiagnosisInput
from satellite_x.ai.service import DiagnosisService
from satellite_x.analytics.models import AnalyticsInput
from satellite_x.analytics.service import AnalyticsService
from satellite_x.config import Settings
from satellite_x.models import FarmInput
from satellite_x.polygon.models import PolygonRecoveryInput
from satellite_x.polygon.service import PolygonRecoveryService
from satellite_x.preprocessing.models import PreprocessingInput, SarFallbackInput
from satellite_x.preprocessing.sar import SarFallbackService
from satellite_x.preprocessing.service import PreprocessingService
from satellite_x.resilience import ResilienceInput, ResilienceService

def config_value(secret_name: str, env_name: str, default: str) -> str:
    try:
        return str(st.secrets.get(secret_name, os.getenv(env_name, default)))
    except Exception:
        return os.getenv(env_name, default)


IST = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(IST).date()
GITHUB_URL = config_value(
    "github_url",
    "SATELLITE_X_GITHUB_URL",
    "https://github.com/YOUR_USERNAME/satellite-x",
)
SESSION_TTL_MINUTES = max(
    5,
    min(
        240,
        int(
            config_value(
                "session_ttl_minutes",
                "SATELLITE_X_PUBLIC_SESSION_TTL_MINUTES",
                "60",
            )
        ),
    ),
)

st.set_page_config(
    page_title="SATELLITE-X — Test Your Field", page_icon="🛰️", layout="wide"
)
st.markdown(
    """
<style>
.block-container{max-width:1250px;padding-top:1.3rem}.hero{padding:22px 26px;border-radius:18px;color:white;background:linear-gradient(110deg,#064e3b,#075985,#312e81);margin-bottom:14px}.step{display:inline-block;background:#dff7ef;color:#07543d;padding:5px 11px;border-radius:18px;font-weight:800;margin-bottom:6px}.notice{padding:13px 16px;border-radius:12px;background:#fff7ed;border:1px solid #fdba74}.successbox{padding:13px 16px;border-radius:12px;background:#ecfdf5;border:1px solid #6ee7b7}.stMetric{border:1px solid #dbe7e1;border-radius:13px;padding:10px;background:#fbfefd}
</style>
<div class="hero"><h1>🛰️ SATELLITE-X — Test Your Field</h1><p>Enter or upload → confirm boundary → run live original engine → inspect and download output</p></div>
""",
    unsafe_allow_html=True,
)
st.markdown(
    f"""<div class="notice"><b>Real execution only:</b> this tester calls the same polygon, Sentinel-2, Sentinel-1 RTC, Open-Meteo, SoilGrids, analytics and diagnosis services as the core project. It does not inject fake values. Cache/baseline/model/unresolved states stay visible. No name, phone, Aadhaar or password is requested, and the app does not save your result to a project database.<br><b>Session:</b> results stay in memory while active, clear after {SESSION_TTL_MINUTES} minutes of inactivity or when you press Exit. Download the JSON before exiting.</div>""", 
    unsafe_allow_html=True,
)

now_epoch = time.time()
expired_session = False
if (
    "session_last_activity" in st.session_state
    and now_epoch - st.session_state.session_last_activity
    > SESSION_TTL_MINUTES * 60
):
    st.session_state.clear()
    expired_session = True

for key, value in {
    "public_session_id": str(uuid.uuid4()),
    "session_started": now_epoch,
    "session_last_activity": now_epoch,
    "field_request": None,
    "recovery": None,
    "confirmed": None,
    "result_bundle": None,
    "last_run_epoch": 0.0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = value
st.session_state.session_last_activity = now_epoch

if expired_session:
    st.warning(
        f"The previous inactive session expired after {SESSION_TTL_MINUTES} minutes and its in-memory data was cleared."
    )

with st.sidebar:
    st.subheader("Private test session")
    st.caption(f"Session: {st.session_state.public_session_id[:8]}")
    st.caption(
        f"Kept in memory while active; clears after {SESSION_TTL_MINUTES} minutes of inactivity or when you exit."
    )
    if st.button("Exit & clear my session", width="stretch"):
        st.session_state.clear()
        st.rerun()


def reset_after_input():
    st.session_state.recovery = None
    st.session_state.confirmed = None
    st.session_state.result_bundle = None


def extract_geometry(payload):
    if payload.get("type") in {"Polygon", "MultiPolygon"}:
        return payload
    if payload.get("type") == "Feature":
        return payload.get("geometry")
    if payload.get("type") == "FeatureCollection":
        features = payload.get("features") or []
        if len(features) != 1:
            raise ValueError("GeoJSON FeatureCollection must contain exactly one polygon")
        return features[0].get("geometry")
    raise ValueError("Upload a Polygon, MultiPolygon, Feature or one-feature FeatureCollection")


st.markdown("<span class='step'>STEP 1</span>", unsafe_allow_html=True)
st.subheader("Enter field information")
with st.form("field_input"):
    c1, c2, c3 = st.columns(3)
    field_id = c1.text_input("Field ID", value="PUBLIC-TEST-001", max_chars=64)
    latitude = c1.number_input("Latitude", value=16.306700, format="%.8f")
    longitude = c2.number_input("Longitude", value=80.436500, format="%.8f")
    acres = c2.number_input("Reported acres", min_value=0.01, max_value=100.0, value=2.0, step=0.1)
    crop_type = c3.selectbox("Crop", ["chilli", "cotton", "paddy"])
    sowing_date = c3.date_input("Sowing date", value=TODAY - timedelta(days=64), max_value=TODAY)
    analysis_date = st.date_input("Requested analysis date", value=TODAY, max_value=TODAY)
    consent = st.checkbox(
        "I consent to processing this GPS point and boundary for this test. I will not enter another person's private field without permission."
    )
    saved = st.form_submit_button("Validate input", type="primary", width="stretch")
if saved:
    try:
        request = PolygonRecoveryInput(
            field_id=field_id,
            latitude=latitude,
            longitude=longitude,
            acres=acres,
            location_consent=consent,
            country_code="IN",
            subdivision_code="AP",
            search_radius_m=300,
            gps_tolerance_m=30,
        )
        st.session_state.field_request = {
            "polygon": request,
            "crop_type": crop_type,
            "sowing_date": sowing_date,
            "analysis_date": analysis_date,
        }
        reset_after_input()
        st.success("Input contract accepted. Continue to boundary confirmation.")
    except Exception as exc:
        st.error(f"Input rejected: {exc}")

if st.session_state.field_request:
    request = st.session_state.field_request["polygon"]
    st.markdown("<span class='step'>STEP 2</span>", unsafe_allow_html=True)
    st.subheader("Confirm the actual field boundary")
    mode = st.radio(
        "Choose one boundary method",
        ["Recover open FTW candidate", "Upload GeoJSON", "Draw on map"],
        horizontal=True,
    )

    if mode == "Recover open FTW candidate":
        if st.button("Run location check & recover candidates", width="stretch"):
            with st.spinner("Checking road/structure/water proximity and querying FTW…"):
                with PolygonRecoveryService(Settings.from_env()) as service:
                    st.session_state.recovery = service.recover(request)
                    st.session_state.confirmed = None
                    st.session_state.result_bundle = None
        recovery = st.session_state.recovery
        if recovery:
            st.markdown(f"**Recovery status:** `{recovery.status}`")
            for warning in recovery.warnings:
                st.warning(warning)
            if recovery.status == "rejected_location":
                st.error("The point is on/near a blocked location. Move it inside the actual parcel and validate input again.")
            elif recovery.candidates:
                st.dataframe(
                    [
                        {
                            "candidate": item.candidate_id,
                            "area_acres": item.area_acres,
                            "gps_distance_m": item.point_distance_m,
                            "area_difference_pct": item.area_difference_pct,
                            "score_pct": item.score_pct,
                            "quality": item.quality,
                        }
                        for item in recovery.candidates
                    ],
                    width="stretch",
                )
                candidate_id = st.selectbox(
                    "Visually reviewed candidate",
                    [item.candidate_id for item in recovery.candidates],
                )
                st.warning("FTW is an operational remote-sensing field unit, not legal ownership proof.")
                if st.checkbox("I visually checked this candidate and explicitly confirm it"):
                    if st.button("Confirm selected boundary", type="primary", width="stretch"):
                        with PolygonRecoveryService(Settings.from_env()) as service:
                            st.session_state.confirmed = service.confirm_candidate(
                                recovery, candidate_id
                            )
                            st.session_state.result_bundle = None
                        st.rerun()
            else:
                st.info("No usable FTW candidate. Upload or draw the actual boundary.")

    elif mode == "Upload GeoJSON":
        upload = st.file_uploader("Drop one Polygon GeoJSON file", type=["json", "geojson"])
        if upload is not None:
            if upload.size > 1_000_000:
                st.error("GeoJSON must be 1 MB or smaller")
            elif st.button("Validate location & confirm uploaded boundary", type="primary", width="stretch"):
                try:
                    geometry = extract_geometry(json.loads(upload.getvalue().decode("utf-8")))
                    with PolygonRecoveryService(Settings.from_env()) as service:
                        preflight = service.recover(request)
                        if preflight.status == "rejected_location":
                            raise ValueError("GPS point is on/near a blocked location; move it inside the parcel")
                        st.session_state.confirmed = service.confirm_uploaded_or_drawn(
                            request, geometry, "user_drawn"
                        )
                        st.session_state.recovery = preflight
                        st.session_state.result_bundle = None
                    st.rerun()
                except Exception as exc:
                    st.error(f"Boundary rejected: {exc}")

    else:
        field_map = folium.Map(
            location=[request.latitude, request.longitude], zoom_start=17,
            tiles="OpenStreetMap",
        )
        folium.Marker(
            [request.latitude, request.longitude], tooltip="Input GPS point"
        ).add_to(field_map)
        Draw(
            export=False,
            draw_options={
                "polyline": False, "rectangle": False, "circle": False,
                "circlemarker": False, "marker": False,
                "polygon": True,
            },
            edit_options={"edit": True, "remove": True},
        ).add_to(field_map)
        map_state = st_folium(field_map, height=470, width=None, key="public_draw_map")
        drawing = map_state.get("last_active_drawing") if map_state else None
        if drawing and st.button("Validate location & confirm latest drawing", type="primary", width="stretch"):
            try:
                geometry = drawing.get("geometry", drawing)
                with PolygonRecoveryService(Settings.from_env()) as service:
                    preflight = service.recover(request)
                    if preflight.status == "rejected_location":
                        raise ValueError("GPS point is on/near a blocked location; move it inside the parcel")
                    st.session_state.confirmed = service.confirm_uploaded_or_drawn(
                        request, geometry, "user_drawn"
                    )
                    st.session_state.recovery = preflight
                    st.session_state.result_bundle = None
                st.rerun()
            except Exception as exc:
                st.error(f"Drawing rejected: {exc}")

if st.session_state.confirmed:
    confirmed = st.session_state.confirmed
    st.markdown("<span class='step'>STEP 3</span>", unsafe_allow_html=True)
    st.subheader("Run the original live engine")
    cols = st.columns(4)
    cols[0].metric("Field", confirmed.field_id)
    cols[1].metric("Confirmed area", f"{confirmed.validation.area_acres:.3f} ac")
    cols[2].metric("Boundary source", confirmed.boundary_source)
    cols[3].metric("Legal boundary", str(confirmed.legal_boundary).lower())
    st.caption("Nothing is run from a hard-coded result. The services execute after you press the button.")
    cooldown = max(0, 15 - int(time.time() - st.session_state.last_run_epoch))
    if cooldown:
        st.info(f"Please wait {cooldown} seconds before another external run in this session.")
    if st.button(
        "Run Set 1 → Set 2 → SAR → Set 3 → Set 4",
        type="primary",
        width="stretch",
        disabled=bool(cooldown),
    ):
        st.session_state.last_run_epoch = time.time()
        request_data = st.session_state.field_request
        polygon_request = request_data["polygon"]
        set2_request = PreprocessingInput(
            field_id=confirmed.field_id,
            latitude=polygon_request.latitude,
            longitude=polygon_request.longitude,
            boundary_geojson=confirmed.boundary_geojson,
            analysis_date=request_data["analysis_date"],
            scan_range_days=30,
            expansion_days=30,
            location_blocking=False,
            location_reason="PUBLIC_TEST_BOUNDARY_CONFIRMED",
        )
        try:
            with st.status("Executing original services…", expanded=True) as status:
                st.write("Set 2: field SCL, six calibrated bands and urban gate")
                with PreprocessingService(Settings.from_env()) as service:
                    preprocessing = service.run(set2_request)
                st.write("Sentinel-1 RTC: signed VV/VH COG clipping")
                with SarFallbackService(Settings.from_env()) as service:
                    sar = service.run(
                        SarFallbackInput(
                            field_id=confirmed.field_id,
                            boundary_geojson=confirmed.boundary_geojson,
                            analysis_date=request_data["analysis_date"],
                            scan_range_days=30,
                        )
                    )
                resilience = ResilienceService().run(
                    ResilienceInput(
                        field_id=confirmed.field_id,
                        optical=preprocessing,
                        sar=sar,
                    )
                )
                raw = analytics = diagnosis = None
                if preprocessing.status == "accepted":
                    scene_date = preprocessing.selected_scene.acquired_at.date()
                    if request_data["sowing_date"] > scene_date:
                        raise ValueError(
                            f"Sowing date {request_data['sowing_date']} is after selected scene {scene_date}; correct the input"
                        )
                    st.write(f"Set 1: weather reacquired through optical scene date {scene_date}; soil provenance retained")
                    farm = FarmInput(
                        field_id=confirmed.field_id,
                        latitude=polygon_request.latitude,
                        longitude=polygon_request.longitude,
                        crop_type=request_data["crop_type"],
                        sowing_date=request_data["sowing_date"],
                        analysis_date=scene_date,
                        scan_range_days=30,
                        acres=confirmed.validation.area_acres,
                        boundary_geojson=confirmed.boundary_geojson,
                    )
                    with AcquisitionPipeline(Settings.from_env()) as pipeline:
                        raw = pipeline.run(farm)
                    st.write("Set 3: seven indices, crop stage and scene-aligned climatic balance")
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
                    st.write("Set 4: evidence fusion, confidence and verification requirement")
                    diagnosis = DiagnosisService().run(
                        DiagnosisInput(
                            analytics=analytics,
                            quality_tag=preprocessing.selected_quality.quality,
                            sowing_date_quality="known",
                        )
                    )
                bundle = {
                    "scope": "public_ephemeral_test",
                    "persistent_storage": False,
                    "generated_at": datetime.now(IST).isoformat(),
                    "boundary_confirmation": confirmed.model_dump(mode="json"),
                    "preprocessing": preprocessing.model_dump(mode="json"),
                    "sar": sar.model_dump(mode="json"),
                    "resilience": resilience.model_dump(mode="json"),
                    "set1": raw.model_dump(mode="json") if raw else None,
                    "analytics": analytics.model_dump(mode="json") if analytics else None,
                    "diagnosis": diagnosis.model_dump(mode="json") if diagnosis else None,
                }
                st.session_state.result_bundle = bundle
                status.update(label="Execution finished", state="complete")
        except Exception as exc:
            st.session_state.result_bundle = {
                "scope": "public_ephemeral_test",
                "persistent_storage": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            st.error(f"Execution stopped honestly: {type(exc).__name__}: {exc}")

if st.session_state.result_bundle:
    bundle = st.session_state.result_bundle
    st.markdown("<span class='step'>STEP 4</span>", unsafe_allow_html=True)
    st.subheader("Inspect and download your output")
    if bundle.get("error"):
        st.error(bundle["error"])
    else:
        preprocessing = bundle["preprocessing"]
        sar = bundle["sar"]
        resilience = bundle["resilience"]
        cols = st.columns(4)
        cols[0].metric("Set 2", preprocessing["status"])
        cols[1].metric("SAR", sar["status"])
        cols[2].metric("Route", resilience["status"])
        cols[3].metric(
            "Optical scene",
            preprocessing["selected_scene"]["acquired_at"][:10]
            if preprocessing.get("selected_scene") else "none",
        )
        for warning in preprocessing.get("warnings", []):
            st.warning(warning)
        for warning in sar.get("warnings", []):
            st.info(warning)
        if bundle.get("analytics"):
            analytics = bundle["analytics"]
            diagnosis = bundle["diagnosis"]
            st.markdown("<div class='successbox'><b>Original Set 3/4 result produced.</b> Weather reference end equals the selected optical scene date.</div>", unsafe_allow_html=True)
            metrics = st.columns(5)
            metrics[0].metric("NDVI", f'{analytics["indices"]["ndvi"]["mean"]:.4f}')
            metrics[1].metric("NDMI", f'{analytics["indices"]["ndmi"]["mean"]:.4f}')
            metrics[2].metric("Crop stage", analytics["phenology"]["stage_name"])
            metrics[3].metric("Balance", f'{analytics["water_balance"]["water_balance_15d_mm"]:.2f} mm')
            metrics[4].metric("Confidence", f'{diagnosis["confidence"]["final_confidence_pct"]:.1f}%')
            st.subheader(f'Verdict: {diagnosis["verdict"]}')
            st.write(diagnosis["action_english"])
            st.info(diagnosis["action_telugu"])
            index_frame = pd.DataFrame([
                {"index": key.upper(), "mean": value["mean"], "p10": value["p10"], "p90": value["p90"], "pixels": value["valid_pixels"]}
                for key, value in analytics["indices"].items()
            ])
            st.dataframe(index_frame, width="stretch")
            st.caption(
                f'Weather: {analytics["water_balance"]["reference_start_date"]} → {analytics["water_balance"]["reference_end_date"]}; scene alignment = {analytics["water_balance"]["scene_alignment_days"]} days.'
            )
        else:
            st.error("Optical analytics were not generated. SAR-only evidence never becomes fake optical indices or diagnosis.")
        with st.expander("Full machine-readable output"):
            st.json(bundle)
    st.download_button(
        "Download complete result JSON",
        data=json.dumps(bundle, ensure_ascii=False, indent=2, default=str),
        file_name=f'{st.session_state.field_request["polygon"].field_id}_satellite_x_result.json',
        mime="application/json",
        width="stretch",
    )

st.divider()
st.subheader("GitHub, extension and improvement")
st.write("The public tester is a thin workflow over the same core services. Improvements should be made in the core modules with tests and independent oracle evidence—not by hard-coding UI results.")
if "YOUR_USERNAME" in GITHUB_URL:
    st.code("GitHub URL placeholder: https://github.com/YOUR_USERNAME/satellite-x")
    st.caption("Set SATELLITE_X_GITHUB_URL after publishing the repository.")
else:
    st.link_button("Open GitHub repository", GITHUB_URL, width="stretch")
st.markdown("""
**Extend safely:**
- add a source adapter under `src/satellite_x/`;
- preserve live/cache/model/fixture labels;
- add deterministic tests;
- add a live test only when an actual public/authorized source exists;
- add an independent oracle for scientific formulas;
- never commit private coordinates, boundaries, credentials or evidence photos.
""")
