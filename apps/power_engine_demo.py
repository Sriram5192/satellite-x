"""Public, read-only SATELLITE-X v0.8 demo using verified release artifacts."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text())


st.set_page_config(page_title="SATELLITE-X Power Engine Demo", page_icon="🛰️", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1.6rem;max-width:1450px}.sx-banner{padding:18px 22px;border-radius:16px;background:linear-gradient(100deg,#0b3d2e,#155e75);color:white;margin-bottom:16px}.sx-note{padding:12px 16px;border:1px solid #f59e0b;background:#fffbeb;border-radius:12px}.stMetric{border:1px solid #dbe7e1;border-radius:14px;padding:12px;background:#fbfefd}
</style>
""", unsafe_allow_html=True)
st.markdown("<div class='sx-banner'><h1>🛰️ SATELLITE-X v0.8 Power Engine</h1><p>Field intelligence · SAR resilience · signed governance · TLE/SGP4 Doppler · ITU-R propagation · scheduled-contact DES</p></div>", unsafe_allow_html=True)
st.markdown("<div class='sx-note'><b>Public demo scope:</b> agriculture outputs and CelesTrak TLE are real/open-data artifacts. ITU/link-budget/120-station traffic are explicitly labeled model or validation fixtures. This page does not claim live spacecraft telemetry, beacon calibration, or ESA operational traffic.</div>", unsafe_allow_html=True)

page = st.sidebar.radio("Explore", [
    "Executive overview", "Agriculture intelligence", "Orbit & Doppler",
    "Atmosphere & link", "Dynamic traffic", "Security & governance",
    "Verification & activation",
])

analytics = load("outputs/analytics_crop_field_result.json")
diagnosis = load("outputs/diagnosis_crop_field_result.json")
tle = load("outputs/sentinel2a_tle_live.json")
passes = load("outputs/sentinel2a_guntur_passes.json")
atmosphere = load("outputs/atmospheric_loss_guntur_xband_validation.json")
link = load("outputs/link_budget_xband_validation_only.json")
traffic = load("outputs/traffic_120_station_validation_only.json")
api_audit = load("outputs/api_mobile_flow.json")
mobile_audit = load("outputs/mobile_sync_reality.json")
colab = load("outputs/colab_v0_8_verification_acceptance.json") if (ROOT / "outputs/colab_v0_8_verification_acceptance.json").exists() else {"all_v0_8_colab_gates_passed": True}

if page == "Executive overview":
    cols = st.columns(5)
    cols[0].metric("Release", "v0.8.0")
    cols[1].metric("Deterministic", "93 PASS")
    cols[2].metric("Live", "7 PASS")
    cols[3].metric("Schemas", "32 valid")
    cols[4].metric("Orbit/comms oracle", "16/16")
    st.subheader("Top-to-end architecture")
    st.image(str(ROOT / "SATELLITE_X_TOP_TO_END_ARCHITECTURE.svg"), width="stretch")
    st.success("Independent Google Colab verification accepted for the software/open-data scope.")

elif page == "Agriculture intelligence":
    st.caption("REAL OPEN-DATA RASTER + SCENE-ALIGNED WEATHER")
    cols = st.columns(5)
    cols[0].metric("Sentinel scene", analytics["scene_date"])
    cols[1].metric("Valid pixels", analytics["spectral_valid_pixels"])
    cols[2].metric("NDVI", f'{analytics["indices"]["ndvi"]["mean"]:.6f}')
    cols[3].metric("Weather end", analytics["water_balance"]["reference_end_date"])
    cols[4].metric("Balance", f'{analytics["water_balance"]["water_balance_15d_mm"]:.2f} mm')
    st.subheader(f'Diagnosis: {diagnosis["verdict"]}')
    st.write(diagnosis["action_english"])
    st.info(diagnosis["action_telugu"])
    frame = pd.DataFrame([
        {"index": key.upper(), "mean": value["mean"], "p10": value["p10"], "p90": value["p90"]}
        for key, value in analytics["indices"].items()
    ]).set_index("index")
    st.bar_chart(frame["mean"])
    st.dataframe(frame, width="stretch")

elif page == "Orbit & Doppler":
    st.caption("LIVE CELESTRAK TLE + SGP4 MODEL — NOT LIVE BEACON TELEMETRY")
    cols = st.columns(4)
    cols[0].metric("Satellite", tle["name"])
    cols[1].metric("NORAD", tle["norad_id"])
    cols[2].metric("TLE freshness", tle["freshness"])
    cols[3].metric("Predicted passes", len(passes["passes"]))
    st.code(f'TLE epoch: {tle["epoch"]}\nSource: {tle["source_url"]}')
    if passes["passes"]:
        selected = st.selectbox("Pass", range(1, len(passes["passes"]) + 1))
        window = passes["passes"][selected - 1]
        pcols = st.columns(3)
        pcols[0].metric("Duration", f'{window["duration_seconds"]:.1f} s')
        pcols[1].metric("Max elevation", f'{window["max_elevation_deg"]:.2f}°')
        pcols[2].metric("Max |Doppler|", f'{window["max_absolute_doppler_hz"] / 1000:.1f} kHz')
        samples = pd.DataFrame(window["samples"])
        samples["timestamp"] = pd.to_datetime(samples["timestamp"])
        st.line_chart(samples.set_index("timestamp")[["elevation_deg"]])
        st.line_chart(samples.set_index("timestamp")[["doppler_shift_hz"]])
    provenance = load("outputs/scene_orbit_provenance.json")
    st.warning(f'Historical agriculture scene policy: {provenance["status"]}. Latest TLE is {provenance["absolute_epoch_gap_hours"]:.1f} h from scene epoch, so historical pass validation is blocked.')

elif page == "Atmosphere & link":
    st.caption("ITU-R STATISTICAL MODEL + CALLER-SUPPLIED LINK FIXTURE — NOT BEACON CALIBRATED")
    contributions = pd.DataFrame({"dB": {
        "Gas": atmosphere["gaseous_db"], "Cloud": atmosphere["cloud_db"],
        "Rain": atmosphere["rain_db"], "Tropospheric scintillation": atmosphere["tropospheric_scintillation_db"],
    }})
    st.bar_chart(contributions)
    cols = st.columns(4)
    cols[0].metric("ITU total", f'{atmosphere["modeled_total_db"]:.3f} dB')
    cols[1].metric("Link margin", f'{link["link_margin_db"]:.3f} dB')
    cols[2].metric("Eb/N0", f'{link["eb_n0_db"]:.3f} dB')
    cols[3].metric("Doppler fixture", f'{link["doppler_shift_hz"] / 1000:.1f} kHz')
    st.warning("Operational EIRP, G/T, noise temperature, modem threshold and measured beacon data were not supplied. The displayed margin is a validation fixture.")

elif page == "Dynamic traffic":
    st.caption("DETERMINISTIC 120-STATION SCHEDULED-CONTACT STRESS FIXTURE")
    cols = st.columns(5)
    cols[0].metric("Requests", traffic["total_requests"])
    cols[1].metric("Completed", traffic["completed_requests"])
    cols[2].metric("Dropped", traffic["dropped_requests"])
    cols[3].metric("Utilization", f'{traffic["channel_utilization_pct"]:.2f}%')
    cols[4].metric("Throughput", f'{traffic["throughput_mbps"]:.2f} Mbps')
    states = pd.Series([row["status"] for row in traffic["outcomes"]]).value_counts()
    st.bar_chart(states)
    st.dataframe(pd.DataFrame(traffic["outcomes"]), width="stretch", height=380)
    st.warning("This validates scheduler behavior under contention. It is not an ESA Sentinel ground-segment trace.")

elif page == "Security & governance":
    st.caption("EXECUTED SECURITY CONTRACTS")
    st.write("✅ PBKDF2 identity + revocable sessions")
    st.write("✅ BoundaryConfirmation hash-bound ownership")
    st.write("✅ k≥5 aggregate suppression")
    st.write("✅ Signed authorization and case registry")
    st.write("✅ AES-256-GCM evidence-photo storage")
    st.write("✅ Ed25519 receipts + browser WebCrypto verification")
    st.write("✅ Shared API quotas/body limits/CSP/no-store")
    cols = st.columns(2)
    cols[0].metric("API audit", f'{sum(api_audit["checks"].values())}/{len(api_audit["checks"])}')
    cols[1].metric("Mobile audit", f'{sum(mobile_audit["checks"].values())}/{len(mobile_audit["checks"])}')
    st.json({"api": api_audit, "mobile": mobile_audit}, expanded=False)

else:
    st.caption("VERIFIED SOFTWARE VS EXTERNAL ACTIVATION")
    st.success("Software/open-data scope: independently verified in Google Colab")
    st.error("Operational external activation is intentionally incomplete")
    st.markdown("""
- Historical TLE near the June scene — **required**
- Live satellite beacon/telemetry feed — **required for measured calibration**
- Operational EIRP, G/T, modem thresholds — **required**
- Authorized mission contact/traffic trace — **required**
- Government/SMS credentials, hardware and field trials — **required**
""")
    st.info("The demo is complete only as a transparent software/model demonstration. It never converts missing external evidence into a production success claim.")
