import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from auth.auth_ui import require_login
from db.database import query, execute
from utils.helpers import sidebar_quick_stats

require_login(tool="tracker")
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
sidebar_quick_stats()

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

CHART_TEMPLATE = "plotly_dark"
CHART_BG = "rgba(0,0,0,0)"
CHART_PAPER = "rgba(0,0,0,0)"
CHART_FONT_COLOR = "#94a3b8"

st.markdown("""
<div style="margin-bottom:20px;">
    <h1 style="margin:0; font-size:1.8rem;">Dashboard</h1>
    <p style="color:#64748b; margin:4px 0 0 0; font-size:0.95rem;">Real-time overview of your contract performance</p>
</div>
""", unsafe_allow_html=True)


@st.dialog("All Personnel Utilization", width="large")
def all_personnel_dialog(person_summary):
    """Show full personnel utilization table + chart."""
    st.markdown(f"**{len(person_summary)} personnel** across all projects")

    # Chart
    fig = px.bar(
        person_summary.sort_values("total_hours", ascending=True),
        x="total_hours", y="display_name", orientation="h",
        color="total_hours", color_continuous_scale=["#60a5fa", "#3b82f6", "#1d4ed8"],
        labels={"total_hours": "Hours", "display_name": ""},
    )
    fig.update_layout(
        showlegend=False, coloraxis_showscale=False,
        height=max(300, len(person_summary) * 30 + 60),
        template=CHART_TEMPLATE, paper_bgcolor=CHART_PAPER,
        plot_bgcolor=CHART_BG, font_color=CHART_FONT_COLOR,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Table
    disp = person_summary[["display_name", "total_hours", "total_cost", "total_charge", "project_count"]].copy()
    disp.columns = ["Name", "Hours", "Cost", "Charge", "Projects"]
    st.dataframe(
        disp.style.format({"Hours": "{:.1f}", "Cost": "${:,.2f}", "Charge": "${:,.2f}"}),
        use_container_width=True, hide_index=True, height=min(600, len(disp) * 38 + 40),
    )

    if st.button("Close", use_container_width=True, key="close_personnel_dlg"):
        st.rerun()


@st.dialog("PWS Profit Breakdown", width="large")
def pws_drill_dialog(pws_number, pws_df):
    """Drill-down popup showing projects under a specific PWS."""
    st.markdown(f"### PWS: {pws_number}")

    total_charge = pws_df["grand_total_charge"].sum()
    total_cost = pws_df["grand_total_cost"].sum()
    total_profit = pws_df["total_profit"].sum()
    margin = ((total_charge - total_cost) / total_charge * 100) if total_charge > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Revenue", f"${total_charge:,.2f}")
    k2.metric("Cost", f"${total_cost:,.2f}")
    k3.metric("Profit", f"${total_profit:,.2f}")
    k4.metric("Margin", f"{margin:.1f}%")

    # Profit by project bar chart
    fig = px.bar(
        pws_df.sort_values("total_profit", ascending=True),
        x="total_profit", y="report_title", orientation="h",
        color="total_profit",
        color_continuous_scale=["#ef4444", "#fbbf24", "#22c55e"],
        labels={"total_profit": "Profit ($)", "report_title": ""},
    )
    fig.update_layout(
        showlegend=False, coloraxis_showscale=False, height=max(200, len(pws_df) * 40 + 60),
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font_color="#94a3b8",
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Projects table
    tbl = pws_df[["report_title", "status", "days", "grand_total_charge",
                   "grand_total_cost", "total_profit"]].copy()
    tbl.columns = ["Project", "Status", "Days", "Charge", "Cost", "Profit"]
    st.dataframe(
        tbl.style.format({"Charge": "${:,.2f}", "Cost": "${:,.2f}", "Profit": "${:,.2f}"}),
        use_container_width=True, hide_index=True,
    )

    if st.button("Close", use_container_width=True):
        st.rerun()

# --- Filters ---
with st.container(border=True):
    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 2])
    with filter_col1:
        date_from = st.date_input("From", value=date.today() - timedelta(days=365), key="dash_from")
    with filter_col2:
        date_to = st.date_input("To", value=date.today(), key="dash_to")
    with filter_col3:
        status_filter = st.multiselect("Status", ["Ongoing", "Complete"], default=["Ongoing", "Complete"])

# --- Load data ---
project_profit = query("SELECT * FROM v_project_profit")
imagery_by_provider = query("SELECT * FROM v_imagery_profit_by_provider")
day_rate = query("SELECT * FROM day_rate_options LIMIT 1", fetchone=True)
revenue = query("SELECT * FROM revenue_streams LIMIT 1", fetchone=True)

if not project_profit:
    st.info("No projects yet. Go to the Projects page to create one.")
    st.stop()

df = pd.DataFrame(project_profit)

# Apply filters
df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
mask = df["status"].isin(status_filter)
if date_from:
    mask = mask & ((df["start_date"] >= pd.Timestamp(date_from)) | df["start_date"].isna())
if date_to:
    mask = mask & ((df["start_date"] <= pd.Timestamp(date_to)) | df["start_date"].isna())
df = df[mask]

if df.empty:
    st.warning("No projects match your filters.")
    st.stop()

# --- KPI Cards ---
total_charge = df["grand_total_charge"].sum()
total_cost = df["grand_total_cost"].sum()
total_profit = df["total_profit"].sum()
margin = ((total_charge - total_cost) / total_charge * 100) if total_charge > 0 else 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Total Revenue", f"${total_charge:,.2f}")
kpi2.metric("Total Cost", f"${total_cost:,.2f}")
kpi3.metric("Running Profit", f"${total_profit:,.2f}")
kpi4.metric("Profit Margin", f"{margin:.1f}%")

# --- PWS Breakdown (dynamic, multi-card) ---
st.markdown("")
all_dash_pws = sorted(df["pws_number"].unique())

# Session state for tracked PWS cards
if "_dash_pws_list" not in st.session_state:
    st.session_state["_dash_pws_list"] = [all_dash_pws[0]] if all_dash_pws else []

pws_header_col, pws_btn_col = st.columns([4, 1])
with pws_header_col:
    st.markdown("""
    <div style="margin-bottom:8px;">
        <span style="color:#7c8fa6; font-size:0.78rem; font-weight:600; text-transform:uppercase; letter-spacing:0.8px;">
            PWS Breakdown
        </span>
    </div>
    """, unsafe_allow_html=True)
with pws_btn_col:
    if st.button("+ Add PWS", key="add_pws_card", use_container_width=True):
        # Add the next PWS not already in the list, or first one if all are added
        existing = set(st.session_state["_dash_pws_list"])
        available = [p for p in all_dash_pws if p not in existing]
        if available:
            st.session_state["_dash_pws_list"].append(available[0])
        else:
            st.toast("All PWS numbers already added", icon="ℹ️")
        st.rerun()

# Render each PWS card
for card_idx, card_pws in enumerate(st.session_state["_dash_pws_list"]):
    with st.container(border=True):
        sel_col, remove_col = st.columns([5, 1])
        with sel_col:
            new_pws = st.selectbox(
                "Select PWS", all_dash_pws,
                index=all_dash_pws.index(card_pws) if card_pws in all_dash_pws else 0,
                key=f"dash_pws_{card_idx}",
            )
            if new_pws != card_pws:
                st.session_state["_dash_pws_list"][card_idx] = new_pws
                st.rerun()
        with remove_col:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if len(st.session_state["_dash_pws_list"]) > 1:
                if st.button("✕", key=f"remove_pws_{card_idx}", help="Remove this PWS card"):
                    st.session_state["_dash_pws_list"].pop(card_idx)
                    st.rerun()

        pws_mask = df["pws_number"] == new_pws
        pws_charge = df.loc[pws_mask, "grand_total_charge"].sum()
        pws_cost = df.loc[pws_mask, "grand_total_cost"].sum()
        pws_profit = df.loc[pws_mask, "total_profit"].sum()
        pws_active = int((df.loc[pws_mask, "status"] == "Ongoing").sum())
        pws_total = int(pws_mask.sum())
        pws_margin = ((pws_charge - pws_cost) / pws_charge * 100) if pws_charge > 0 else 0

        dp1, dp2, dp3, dp4 = st.columns(4)
        dp1.metric("Revenue", f"${pws_charge:,.2f}")
        dp2.metric("Cost", f"${pws_cost:,.2f}")
        dp3.metric("Profit", f"${pws_profit:,.2f}")
        dp4.metric("Margin", f"{pws_margin:.1f}%",
                   delta=f"{pws_active} active / {pws_total} projects")

        # Day rate tracking per PWS
        pws_dr = query("SELECT * FROM pws_day_rate WHERE pws_number = ?", (new_pws,), fetchone=True)
        total_exercised = pws_dr["total_exercised"] if pws_dr else 0
        pws_days_used = int(df.loc[pws_mask, "days"].fillna(0).sum())
        days_remaining = total_exercised - pws_days_used

        editing_key = f"_editing_days_dash_{card_idx}"
        editing_days = st.session_state.get(editing_key, False)

        if not editing_days:
            if days_remaining >= 0:
                remaining_delta = f"{days_remaining} remaining"
                remaining_delta_color = "normal"
            else:
                remaining_delta = f"{abs(days_remaining)} exceeded"
                remaining_delta_color = "inverse"

            dd1, dd2, dd3, dd4 = st.columns([1, 1, 1, 0.2])
            dd1.metric("Days Exercised", total_exercised)
            dd2.metric("Days Used", pws_days_used)
            dd3.metric("Days Remaining", days_remaining,
                       delta=remaining_delta,
                       delta_color=remaining_delta_color)
            with dd4:
                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                if st.button("✏️", key=f"edit_days_dash_{card_idx}", help="Edit Days Exercised"):
                    st.session_state[editing_key] = True
                    st.rerun()
        else:
            dd1, dd2, dd3, dd4 = st.columns([1, 1, 1, 0.5])
            with dd1:
                new_ex = st.number_input("Days Exercised", value=int(total_exercised),
                                          min_value=0, step=1, key=f"days_ex_input_{card_idx}")
            with dd2:
                st.metric("Days Used", pws_days_used)
            with dd3:
                new_rem = new_ex - pws_days_used
                if new_rem >= 0:
                    nr_d = f"{int(new_rem)} remaining"
                    nr_c = "normal"
                else:
                    nr_d = f"{int(abs(new_rem))} exceeded"
                    nr_c = "inverse"
                st.metric("Days Remaining", int(new_rem), delta=nr_d, delta_color=nr_c)
            with dd4:
                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                sb1, sb2 = st.columns(2)
                if sb1.button("✓", key=f"save_days_dash_{card_idx}", type="primary", help="Save"):
                    if pws_dr:
                        execute("UPDATE pws_day_rate SET total_exercised = ?, updated_at = datetime('now') WHERE pws_number = ?",
                                (new_ex, new_pws))
                    else:
                        execute("INSERT INTO pws_day_rate (pws_number, total_exercised) VALUES (?, ?)",
                                (new_pws, new_ex))
                    st.session_state.pop(editing_key, None)
                    st.toast(f"Days Exercised updated for PWS {new_pws}!", icon="✅")
                    st.rerun()
                if sb2.button("✕", key=f"cancel_days_dash_{card_idx}", help="Cancel"):
                    st.session_state.pop(editing_key, None)
                    st.rerun()

st.markdown("---")

# --- Charts Row 1 ---
chart1, chart2 = st.columns(2)

with chart1:
    st.subheader("Profit by PWS")
    st.caption("Click any bar to drill down into that PWS")

    # Aggregate by PWS
    pws_profit = df.groupby("pws_number").agg(
        total_profit=("total_profit", "sum"),
        total_charge=("grand_total_charge", "sum"),
        total_cost=("grand_total_cost", "sum"),
        project_count=("report_title", "count"),
    ).reset_index().sort_values("total_profit", ascending=True)

    fig = px.bar(
        pws_profit,
        x="total_profit", y="pws_number", orientation="h",
        color="total_profit",
        color_continuous_scale=["#ef4444", "#fbbf24", "#22c55e"],
        labels={"total_profit": "Profit ($)", "pws_number": "PWS"},
        hover_data={"project_count": True, "total_charge": ":$,.0f", "total_cost": ":$,.0f"},
    )
    fig.update_layout(
        showlegend=False, coloraxis_showscale=False,
        height=max(250, len(pws_profit) * 40 + 60),
        template=CHART_TEMPLATE, paper_bgcolor=CHART_PAPER,
        plot_bgcolor=CHART_BG, font_color=CHART_FONT_COLOR,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="pws_chart")

    # Handle bar click → open drill-down dialog
    if event and event.selection and event.selection.points:
        clicked_pws = event.selection.points[0]["y"]
        pws_df = df[df["pws_number"] == clicked_pws]
        if not pws_df.empty:
            pws_drill_dialog(clicked_pws, pws_df)

with chart2:
    st.subheader("Imagery Profit by Provider")
    if imagery_by_provider:
        prov_df = pd.DataFrame(imagery_by_provider)
        prov_df = prov_df[prov_df["total_charge"] > 0]
        if not prov_df.empty:
            fig = px.pie(
                prov_df, values="profit", names="provider", hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_layout(
                height=350, template=CHART_TEMPLATE,
                paper_bgcolor=CHART_PAPER, font_color=CHART_FONT_COLOR,
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No imagery orders with charges yet.")
    else:
        st.info("No imagery orders yet.")

# --- Charts Row 2 ---
chart3, chart4 = st.columns(2)

with chart3:
    st.subheader("Labor vs Imagery Profit")
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Labor", x=df["report_title"], y=df["labor_profit"], marker_color="#3b82f6"))
    fig.add_trace(go.Bar(name="Imagery", x=df["report_title"], y=df["imagery_profit"], marker_color="#8b5cf6"))
    fig.update_layout(
        barmode="stack", height=350,
        yaxis_title="Profit ($)", xaxis_title="",
        template=CHART_TEMPLATE, paper_bgcolor=CHART_PAPER,
        plot_bgcolor=CHART_BG, font_color=CHART_FONT_COLOR,
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

with chart4:
    st.subheader("Cost vs Charge")
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Cost", x=df["report_title"], y=df["grand_total_cost"], marker_color="#ef4444"))
    fig.add_trace(go.Bar(name="Charge", x=df["report_title"], y=df["grand_total_charge"], marker_color="#22c55e"))
    fig.update_layout(
        barmode="group", height=350,
        yaxis_title="Amount ($)", xaxis_title="",
        template=CHART_TEMPLATE, paper_bgcolor=CHART_PAPER,
        plot_bgcolor=CHART_BG, font_color=CHART_FONT_COLOR,
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Charts Row 3: Profit Trend ---
st.markdown("---")
st.subheader("Profit Trend Over Time")

trend_df = df.dropna(subset=["start_date"]).copy()
if not trend_df.empty:
    trend_df["month"] = trend_df["start_date"].dt.to_period("M").astype(str)
    monthly = trend_df.groupby("month").agg(
        revenue=("grand_total_charge", "sum"),
        cost=("grand_total_cost", "sum"),
        profit=("total_profit", "sum"),
    ).reset_index()
    monthly["cumulative_profit"] = monthly["profit"].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Monthly Profit", x=monthly["month"], y=monthly["profit"],
                         marker_color="#3b82f6", opacity=0.6))
    fig.add_trace(go.Scatter(name="Cumulative Profit", x=monthly["month"], y=monthly["cumulative_profit"],
                             mode="lines+markers", line=dict(color="#22c55e", width=3),
                             marker=dict(size=8)))
    fig.update_layout(
        height=350, template=CHART_TEMPLATE, paper_bgcolor=CHART_PAPER,
        plot_bgcolor=CHART_BG, font_color=CHART_FONT_COLOR,
        legend=dict(orientation="h", y=1.1),
        yaxis_title="Profit ($)", xaxis_title="",
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No projects with start dates to show trend.")

# --- Per-Person Utilization ---
st.markdown("---")
st.subheader("Personnel Utilization")

labor_summary = query("""
    SELECT
        CASE WHEN le.person_name IS NOT NULL AND le.person_name != ''
             THEN le.person_name
             ELSE '(' || jc.title || ')'
        END AS display_name,
        SUM(le.hours)                       AS total_hours,
        SUM(le.employee_rate * le.hours)    AS total_cost,
        SUM(le.bid_rate * le.hours)         AS total_charge,
        COUNT(DISTINCT p.report_title)      AS project_count
    FROM labor_entries le
    JOIN job_codes jc ON le.job_code_id = jc.id
    JOIN projects p ON le.project_id = p.id
    GROUP BY display_name
    ORDER BY total_hours DESC
""")

if labor_summary:
    person_summary = pd.DataFrame(labor_summary)

    top10 = person_summary.head(10)

    util1, util2 = st.columns(2)
    with util1:
        fig = px.bar(
            top10.sort_values("total_hours", ascending=True),
            x="total_hours", y="display_name", orientation="h",
            color="total_hours", color_continuous_scale=["#60a5fa", "#3b82f6", "#1d4ed8"],
            labels={"total_hours": "Hours", "display_name": ""},
        )
        fig.update_layout(
            showlegend=False, coloraxis_showscale=False,
            height=max(250, len(top10) * 35 + 60),
            template=CHART_TEMPLATE, paper_bgcolor=CHART_PAPER,
            plot_bgcolor=CHART_BG, font_color=CHART_FONT_COLOR,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    with util2:
        disp_util = top10[["display_name", "total_hours", "total_cost", "total_charge", "project_count"]].copy()
        disp_util.columns = ["Name", "Hours", "Cost", "Charge", "Projects"]
        st.dataframe(
            disp_util.style.format({"Hours": "{:.1f}", "Cost": "${:,.2f}", "Charge": "${:,.2f}"}),
            use_container_width=True, hide_index=True,
        )

    if len(person_summary) > 10:
        st.caption(f"Showing top 10 of {len(person_summary)} personnel")
        if st.button("View All Personnel", key="view_all_personnel"):
            all_personnel_dialog(person_summary)
    else:
        st.caption(f"{len(person_summary)} personnel total")
else:
    st.info("No labor entries yet.")

# --- Projects Table with Margin Flags ---
st.markdown("---")
st.subheader("All Projects")

display_df = df[["pws_number", "report_title", "status", "days",
                  "labor_charge", "imagery_charge", "grand_total_charge",
                  "grand_total_cost", "total_profit"]].copy()
display_df["Margin %"] = display_df.apply(
    lambda r: (r["total_profit"] / r["grand_total_charge"] * 100) if r["grand_total_charge"] > 0 else 0, axis=1
)
display_df.columns = ["PWS", "Report Title", "Status", "Days",
                       "Labor Charge", "Imagery Charge", "Total Charge",
                       "Total Cost", "Profit", "Margin %"]


def _margin_color(val):
    if val >= 20:
        return "background-color: rgba(34,197,94,0.2); color: #22c55e"
    elif val >= 10:
        return "background-color: rgba(251,191,36,0.2); color: #fbbf24"
    else:
        return "background-color: rgba(239,68,68,0.2); color: #ef4444"


st.dataframe(
    display_df.style.format({
        "Labor Charge": "${:,.2f}", "Imagery Charge": "${:,.2f}",
        "Total Charge": "${:,.2f}", "Total Cost": "${:,.2f}", "Profit": "${:,.2f}",
        "Margin %": "{:.1f}%",
    }).map(_margin_color, subset=["Margin %"]),
    use_container_width=True, hide_index=True,
)

# Export
csv = display_df.to_csv(index=False)
st.download_button("Export Dashboard Data (CSV)", csv, file_name="dashboard_export.csv", mime="text/csv")

# --- Day Rate Options ---
if day_rate:
    st.markdown("---")
    st.subheader("Day Rate Options")
    dr1, dr2, dr3, dr4 = st.columns(4)
    dr1.metric("Total Exercised", day_rate["total_exercised"])
    dr2.metric("Total Used", day_rate["total_used"])
    remaining = day_rate["total_exercised"] - day_rate["total_used"]
    dr3.metric("Remaining", remaining)
    dr4.metric("Additional Options", day_rate["additional_options"])
