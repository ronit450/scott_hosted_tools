"""
Daedalus -- AOI Tiling Engine (Streamlit web version)
Upload AOI file or define circle AOI -> run tiling -> download outputs as .zip
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

require_login(tool="daedalus")

user = st.session_state.get("auth_user", {})
sidebar_user_info()

st.markdown(
    '<h2 style="background:linear-gradient(90deg,#f59e0b,#ef4444);'
    '-webkit-background-clip:text;-webkit-text-fill-color:transparent;">'
    'Daedalus</h2>',
    unsafe_allow_html=True,
)
st.caption("AOI Tiling Engine — generate optimised imagery tile grids from an AOI")
st.markdown("---")

# -- AOI Mode Selection --
aoi_mode = st.radio(
    "AOI Input Mode",
    ["Upload AOI file", "Circle AOI (center + radius)"],
    horizontal=True,
)

uploaded = None
center_lat = center_lon = radius_km = None

if aoi_mode == "Upload AOI file":
    uploaded = st.file_uploader(
        "Upload your AOI file",
        type=["kml", "kmz", "geojson", "json", "shp", "gpkg"],
        help="Supported: KML, KMZ, GeoJSON, Shapefile, GeoPackage",
    )
    if not uploaded:
        st.info("Upload a KML, KMZ, GeoJSON, Shapefile, or GeoPackage file to begin.")
else:
    c1, c2, c3 = st.columns(3)
    with c1:
        center_lat = st.number_input("Center Latitude", value=55.61918, format="%.5f")
    with c2:
        center_lon = st.number_input("Center Longitude", value=29.21093, format="%.5f")
    with c3:
        radius_km = st.number_input("Radius (km)", value=10.0, min_value=0.1, step=1.0)

# -- Tiling Configuration --
st.markdown("**Tiling Configuration**")
tc1, tc2 = st.columns(2)
with tc1:
    tile_size_km = st.number_input("Tile Size (km)", value=5.0, min_value=0.1, step=0.5)
with tc2:
    min_inside_frac = st.slider(
        "Min tile inside fraction",
        min_value=0.05, max_value=0.50, value=0.20, step=0.05,
        help="Minimum fraction of a tile that must overlap the AOI to keep it",
    )

# -- Strategy Selection --
st.markdown("**Strategies to include**")
sc1, sc2, sc3, sc4, sc5 = st.columns(5)
show_balanced = sc1.checkbox("Balanced", value=True, help="Best overall score — high coverage, moderated overlap")
show_full = sc2.checkbox("Full", value=True, help="Highest coverage, then fewest tiles")
show_minimal = sc3.checkbox("Minimal", value=True, help="Fewest tiles with acceptable coverage")
show_maxcov = sc4.checkbox("Max Coverage", value=True, help="No pruning — keeps all qualifying tiles")
show_compact = sc5.checkbox("Compact", value=True, help="Core AOI only — high inside-fraction tiles")

# -- Run --
can_run = (aoi_mode == "Circle AOI (center + radius)") or (uploaded is not None)

if st.button("Run Tiling", type="primary", use_container_width=False, disabled=not can_run):
    # Lazy import so geo deps only load when needed
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "image_tiling"))
    from daedalus_core import run_tiling

    with st.spinner("Running tiling engine..."):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out_dir = os.path.join(tmp, "output")

                if aoi_mode == "Upload AOI file":
                    # Write uploaded file to temp dir
                    input_path = os.path.join(tmp, uploaded.name)
                    with open(input_path, "wb") as f:
                        f.write(uploaded.getvalue())

                    result = run_tiling(
                        use_circle_aoi=False,
                        aoi_input=input_path,
                        tile_size_km=tile_size_km,
                        out_dir=out_dir,
                        min_tile_inside_fraction=min_inside_frac,
                    )
                else:
                    result = run_tiling(
                        use_circle_aoi=True,
                        center_lat=center_lat,
                        center_lon=center_lon,
                        radius_km=radius_km,
                        tile_size_km=tile_size_km,
                        out_dir=out_dir,
                        min_tile_inside_fraction=min_inside_frac,
                    )

                # -- Display Results --
                aois = result.get("aois", [])
                if not aois:
                    st.warning("No AOIs returned from tiling.")
                else:
                    # Strategy visibility filter
                    show_flags = {
                        "balanced": show_balanced,
                        "full": show_full,
                        "minimal": show_minimal,
                        "max_coverage": show_maxcov,
                        "compact": show_compact,
                    }
                    strategy_order = ["balanced", "full", "minimal", "max_coverage", "compact"]

                    for aoi_result in aois:
                        aoi_name = aoi_result.get("aoi_name", "unknown")
                        st.subheader(f"AOI: {aoi_name}")

                        strategies = aoi_result.get("strategies", {})
                        recommended = None

                        for strat_name in strategy_order:
                            if strat_name not in strategies or not show_flags.get(strat_name, True):
                                continue

                            strat_data = strategies[strat_name]
                            m = strat_data.get("metrics", {})
                            tiles = m.get("num_tiles", 0)
                            cov = m.get("coverage_fraction", 0.0) * 100.0
                            overlap = m.get("overlap_percent", 0.0)
                            overlap_tiles = m.get("overlap_equiv_tiles", 0.0)

                            pretty = strat_name.replace("_", " ").title()

                            with st.expander(f"{pretty} — {tiles} tiles, {cov:.1f}% coverage", expanded=(strat_name == "balanced")):
                                mc1, mc2, mc3, mc4 = st.columns(4)
                                mc1.metric("Tiles", tiles)
                                mc2.metric("Coverage", f"{cov:.2f}%")
                                mc3.metric("Overlap", f"{overlap:.2f}%")
                                mc4.metric("Overlap Tiles", f"{overlap_tiles:.1f}")

                            if strat_name == "balanced" or recommended is None:
                                recommended = (pretty, tiles, cov, overlap)

                        if recommended:
                            pn, t, c, o = recommended
                            st.success(
                                f"Recommended: **{pn}** — {t} tiles, {c:.1f}% coverage, {o:.1f}% overlap"
                            )

                    # -- Collect all output files into a zip --
                    output_files = {}
                    for root, dirs, files in os.walk(out_dir):
                        for fname in files:
                            fpath = os.path.join(root, fname)
                            rel = os.path.relpath(fpath, out_dir)
                            with open(fpath, "rb") as f:
                                output_files[rel] = f.read()

                    if output_files:
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                            for fname, data in output_files.items():
                                zf.writestr(fname, data)
                        zip_buffer.seek(0)

                        st.download_button(
                            label=f"Download All ({len(output_files)} files)",
                            data=zip_buffer,
                            file_name="daedalus_tiling_output.zip",
                            mime="application/zip",
                            use_container_width=True,
                            type="primary",
                            key="dl_tiling_zip",
                        )

                log_activity(
                    user.get("username", "unknown"), "daedalus", "tiling",
                    f"mode={'circle' if aoi_mode.startswith('Circle') else 'file'}, "
                    f"tile_size={tile_size_km}km, aois={len(aois)}"
                )

        except Exception as exc:
            st.error(f"Tiling failed: {exc}")
            log_activity(user.get("username", "unknown"), "daedalus", "tiling_error", str(exc))
