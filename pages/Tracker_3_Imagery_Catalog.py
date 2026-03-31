import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from auth.auth_ui import require_login
from db.database import query, execute, get_connection
from utils.helpers import sidebar_quick_stats

require_login(tool="tracker")
st.set_page_config(page_title="Imagery Catalog", page_icon="🛰️", layout="wide")
sidebar_quick_stats()

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

st.title("Imagery Pricing Catalog")

# Load catalog data
catalog = query("SELECT * FROM imagery_catalog ORDER BY provider, description")
df = pd.DataFrame(catalog)

if df.empty:
    st.warning("No imagery catalog data found. Run seed_data.py first.")
    st.stop()

# --- Filters ---
col1, col2, col3 = st.columns(3)

with col1:
    providers = sorted(df["provider"].unique())
    selected_providers = st.multiselect("Provider", providers, default=providers)

with col2:
    search = st.text_input("Search Description", placeholder="e.g. Dwell, Spotlight, Archive...")

with col3:
    price_range = st.slider(
        "List Price Range ($)",
        min_value=0,
        max_value=int(df["list_price"].max()) + 100,
        value=(0, int(df["list_price"].max()) + 100),
    )

# Apply filters
filtered = df[df["provider"].isin(selected_providers)]
if search:
    filtered = filtered[filtered["description"].str.contains(search, case=False, na=False)]
filtered = filtered[
    (filtered["list_price"] >= price_range[0]) & (filtered["list_price"] <= price_range[1])
]

# Display
st.markdown(f"**Showing {len(filtered)} of {len(df)} products**")

display_df = filtered[["provider", "description", "min_area_km2", "resolution", "pricing_guidance", "list_price", "sh_price"]].copy()
display_df.columns = ["Provider", "Description", "Min Area (km²)", "Resolution", "Pricing Guidance", "List Price ($)", "SH Price ($)"]

st.dataframe(
    display_df.style.format({
        "List Price ($)": "${:,.2f}",
        "SH Price ($)": "${:,.2f}",
        "Min Area (km²)": lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A",
    }),
    use_container_width=True,
    hide_index=True,
    height=600,
)

# --- Edit Catalog Entry ---
st.markdown("---")
st.subheader("Edit Catalog Entry")

# Build a lookup for selecting an entry to edit
catalog_list = filtered.to_dict("records")
if catalog_list:
    edit_options = [f"{r['provider']} - {r['description']}" for r in catalog_list]
    selected_edit = st.selectbox("Select product to edit", ["-- Select --"] + edit_options, key="edit_select")

    if selected_edit != "-- Select --":
        idx = edit_options.index(selected_edit)
        entry = catalog_list[idx]

        with st.form("edit_catalog_form"):
            st.markdown(f"**Editing:** {entry['provider']} - {entry['description']}")
            ec1, ec2 = st.columns(2)
            with ec1:
                edit_provider = st.text_input("Provider", value=entry["provider"])
                edit_desc = st.text_input("Description", value=entry["description"])
                edit_resolution = st.text_input("Resolution", value=entry["resolution"] or "")
            with ec2:
                edit_min_area = st.number_input("Min Area (km²)", value=float(entry["min_area_km2"] or 0), step=1.0)
                edit_list_price = st.number_input("List Price ($)", value=float(entry["list_price"]), step=10.0)
                edit_sh_price = st.number_input("SH Price ($)", value=float(entry["sh_price"]), step=10.0)
            edit_guidance = st.text_input("Pricing Guidance", value=entry["pricing_guidance"] or "")

            submitted = st.form_submit_button("Save Changes", type="primary")
            if submitted:
                execute(
                    """UPDATE imagery_catalog
                       SET provider=?, description=?, min_area_km2=?, resolution=?,
                           pricing_guidance=?, list_price=?, sh_price=?
                       WHERE id=?""",
                    (edit_provider, edit_desc,
                     edit_min_area if edit_min_area > 0 else None,
                     edit_resolution or None, edit_guidance or None,
                     edit_list_price, edit_sh_price, entry["id"]),
                )
                st.success(f"Updated: {edit_provider} - {edit_desc}")
                st.rerun()

# Provider summary
st.markdown("---")
st.subheader("Products by Provider")
provider_counts = filtered.groupby("provider").agg(
    Products=("description", "count"),
    Min_Price=("list_price", "min"),
    Max_Price=("list_price", "max"),
    Avg_Price=("list_price", "mean"),
).reset_index()
provider_counts.rename(columns={"provider": "Provider"}, inplace=True)

st.dataframe(
    provider_counts.style.format({
        "Min_Price": "${:,.2f}",
        "Max_Price": "${:,.2f}",
        "Avg_Price": "${:,.2f}",
    }),
    use_container_width=True,
    hide_index=True,
)

# Export
csv = display_df.to_csv(index=False)
st.download_button("Export Catalog (CSV)", csv, file_name="imagery_catalog_export.csv", mime="text/csv")
