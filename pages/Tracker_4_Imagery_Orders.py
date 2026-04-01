import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from auth.auth_ui import require_login
from db.database import query
from utils.helpers import sidebar_quick_stats

require_login(tool="tracker")
sidebar_quick_stats()

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

CHART_TEMPLATE = "plotly_dark"
CHART_BG = "rgba(0,0,0,0)"
CHART_PAPER = "rgba(0,0,0,0)"

st.title("Imagery Orders Tracker")

orders = query("""
    SELECT io.*, p.report_title, p.pws_number
    FROM imagery_orders io
    JOIN projects p ON io.project_id = p.id
    ORDER BY io.order_date DESC
""")

if not orders:
    st.info("No imagery orders yet. Create orders from the Projects page.")
    st.stop()

df = pd.DataFrame(orders)

# --- Filters ---
f1, f2, f3, f4 = st.columns(4)
with f1:
    providers = sorted(df["provider"].unique())
    selected_providers = st.multiselect("Provider", providers, default=providers)
with f2:
    projects = sorted(df["report_title"].unique())
    selected_projects = st.multiselect("Project", projects, default=projects)
with f3:
    statuses = ["All"] + sorted(df["order_status"].unique().tolist())
    status_filter = st.selectbox("Order Status", statuses)
with f4:
    date_col1, date_col2 = st.columns(2)
    with date_col1:
        date_from = st.date_input("From", value=date.today() - timedelta(days=365), key="ord_from")
    with date_col2:
        date_to = st.date_input("To", value=date.today(), key="ord_to")

# Apply filters
filtered = df[df["provider"].isin(selected_providers) & df["report_title"].isin(selected_projects)]
if status_filter != "All":
    filtered = filtered[filtered["order_status"] == status_filter]

# Date filter
filtered["order_date_dt"] = pd.to_datetime(filtered["order_date"], errors="coerce")
if date_from:
    filtered = filtered[(filtered["order_date_dt"] >= pd.Timestamp(date_from)) | filtered["order_date_dt"].isna()]
if date_to:
    filtered = filtered[(filtered["order_date_dt"] <= pd.Timestamp(date_to)) | filtered["order_date_dt"].isna()]

# --- KPI Cards ---
total_orders = len(filtered)
total_cost = filtered["cost"].sum()
total_charge = filtered["charge"].sum()
total_profit = total_charge - total_cost

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Orders", total_orders)
k2.metric("Total Cost", f"${total_cost:,.2f}")
k3.metric("Total Charge", f"${total_charge:,.2f}")
k4.metric("Profit", f"${total_profit:,.2f}")

# Status breakdown
status_counts = filtered["order_status"].value_counts()
status_colors = {"Requested": "#f59e0b", "Approved": "#06b6d4", "Ordered": "#3b82f6", "Collected": "#8b5cf6", "Delivered": "#22c55e"}
status_html = " ".join(
    f'<span style="background:{status_colors.get(s, "#94a3b8")}; color:white; padding:4px 12px; border-radius:6px; font-size:0.85rem; margin-right:8px;">{s}: {c}</span>'
    for s, c in status_counts.items()
)
st.markdown(status_html, unsafe_allow_html=True)

st.markdown("---")

# --- Chart ---
chart1, chart2 = st.columns(2)

with chart1:
    st.subheader("Cost vs Charge by Provider")
    if not filtered.empty:
        prov_summary = filtered.groupby("provider").agg(
            Cost=("cost", "sum"), Charge=("charge", "sum"),
        ).reset_index()
        fig = px.bar(
            prov_summary.melt(id_vars="provider", var_name="Type", value_name="Amount"),
            x="provider", y="Amount", color="Type", barmode="group",
            color_discrete_map={"Cost": "#ef4444", "Charge": "#22c55e"},
        )
        fig.update_layout(
            height=350, template=CHART_TEMPLATE,
            paper_bgcolor=CHART_PAPER, plot_bgcolor=CHART_BG,
            font_color="#94a3b8", margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig, use_container_width=True)

with chart2:
    st.subheader("Orders by Status")
    if not filtered.empty:
        fig = px.pie(
            filtered, names="order_status", hole=0.4,
            color="order_status", color_discrete_map=status_colors,
        )
        fig.update_layout(
            height=350, template=CHART_TEMPLATE,
            paper_bgcolor=CHART_PAPER, font_color="#94a3b8",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

# --- Orders Table ---
st.markdown("---")
st.subheader("All Orders")

display = filtered[["pws_number", "report_title", "provider", "product", "order_date",
                      "order_status", "aoi", "shots_delivered", "cost", "charge"]].copy()
display.columns = ["PWS", "Project", "Provider", "Product", "Date", "Status", "AOI", "Shots", "Cost", "Charge"]
display["Margin"] = display["Charge"] - display["Cost"]

st.dataframe(
    display.style.format({
        "Cost": "${:,.2f}", "Charge": "${:,.2f}", "Margin": "${:,.2f}",
    }),
    use_container_width=True, hide_index=True, height=500,
)

# Export
csv = display.to_csv(index=False)
st.download_button("Export Orders (CSV)", csv, file_name="imagery_orders_export.csv", mime="text/csv")
