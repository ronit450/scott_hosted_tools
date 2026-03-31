"""
Hermes — Geospatial Data Converter (Streamlit web version)
Upload CSV/Excel → convert → download all outputs as a single .zip
"""
import io
import os
import sys
import tempfile
import zipfile

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auth.auth_db import log_activity
from auth.auth_ui import require_login, sidebar_user_info
from hermes_core.converter import convert_to_geojson
from hermes_core.exporters import export_kml, export_shp

require_login(tool="hermes")
st.set_page_config(
    page_title="Hermes — Stone Harp Analytics",
    page_icon="🌍",
    layout="wide",
)

user = st.session_state.get("auth_user", {})
sidebar_user_info()

st.markdown(
    '<h2 style="background:linear-gradient(90deg,#60a5fa,#a78bfa);'
    '-webkit-background-clip:text;-webkit-text-fill-color:transparent;">🌍 Hermes</h2>',
    unsafe_allow_html=True,
)
st.caption("Convert CSV / Excel intelligence data to GeoJSON, KML, or Shapefile")
st.markdown("---")

# ── Upload ─────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload your data file",
    type=["csv", "xlsx", "xls"],
    help="Must contain lat/lon columns OR an MGRS column",
)

if not uploaded:
    st.info("Upload a CSV or Excel file to begin. The file must have `lat`/`lon` columns or an `mgrs` column.")
    st.stop()

# ── Format selection ───────────────────────────────────────────
st.markdown("**Export formats**")
fc1, fc2, fc3 = st.columns(3)
want_geojson = fc1.checkbox("GeoJSON", value=True)
want_kml     = fc2.checkbox("KML", value=True)
want_shp     = fc3.checkbox("Shapefile (.zip)", value=True)

if not any([want_geojson, want_kml, want_shp]):
    st.warning("Select at least one export format.")
    st.stop()

# ── Convert ────────────────────────────────────────────────────
if st.button("Convert", type="primary", use_container_width=False):
    log_lines = []

    def logger(msg):
        log_lines.append(msg)

    with st.spinner("Converting..."):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                # Write uploaded file to temp dir
                input_path = os.path.join(tmp, uploaded.name)
                with open(input_path, "wb") as f:
                    f.write(uploaded.getvalue())

                output_dir = os.path.join(tmp, "output")
                stem = os.path.splitext(uploaded.name)[0]

                # Convert to GeoJSON (always needed as intermediate)
                geojson_path = convert_to_geojson(input_path, output_dir, logger=logger)

                # Collect all output files
                output_files = {}  # filename → bytes

                if want_geojson:
                    with open(geojson_path, "rb") as f:
                        output_files[os.path.basename(geojson_path)] = f.read()

                if want_kml:
                    kml_path = export_kml(geojson_path, output_dir, logger=logger)
                    with open(kml_path, "rb") as f:
                        output_files[os.path.basename(kml_path)] = f.read()

                if want_shp:
                    shp_path = export_shp(geojson_path, output_dir, logger=logger)
                    with open(shp_path, "rb") as f:
                        output_files[os.path.basename(shp_path)] = f.read()

            # Build a single zip with all outputs
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname, data in output_files.items():
                    zf.writestr(fname, data)
            zip_buffer.seek(0)

            st.success(f"Conversion complete — {len(output_files)} file(s) ready")

            log_activity(
                user.get("username", "unknown"), "hermes", "convert",
                f"{uploaded.name} → {', '.join(output_files.keys())}"
            )

            # Single download button — zip of all outputs
            st.download_button(
                label=f"⬇ Download All ({len(output_files)} files)",
                data=zip_buffer,
                file_name=f"{stem}_hermes_output.zip",
                mime="application/zip",
                use_container_width=True,
                type="primary",
                key="dl_all_zip",
            )

        except Exception as exc:
            st.error(f"Conversion failed: {exc}")
            log_activity(user.get("username", "unknown"), "hermes", "convert_error", str(exc))

    # ── Conversion log ─────────────────────────────────────────
    if log_lines:
        with st.expander("Conversion log", expanded=False):
            st.code("\n".join(log_lines), language=None)
