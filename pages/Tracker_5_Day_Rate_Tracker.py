import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from auth.auth_ui import require_login
from db.database import query, execute
from utils.helpers import sidebar_quick_stats

require_login(tool="tracker")
sidebar_quick_stats()

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

st.title("Day Rate Options Tracker")

# Load current values
day_rate = query("SELECT * FROM day_rate_options LIMIT 1", fetchone=True)

if not day_rate:
    execute("INSERT INTO day_rate_options (total_exercised, total_used, additional_options) VALUES (0, 0, 0)")
    day_rate = query("SELECT * FROM day_rate_options LIMIT 1", fetchone=True)

remaining = day_rate["total_exercised"] - day_rate["total_used"]

# --- KPI Cards ---
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Exercised", day_rate["total_exercised"])
k2.metric("Total Used", day_rate["total_used"])
k3.metric("Remaining", remaining,
           delta=f"{remaining} days left",
           delta_color="normal" if remaining > 0 else "inverse")
k4.metric("Additional Options", day_rate["additional_options"])

# --- Gauge Chart ---
st.markdown("---")
gauge_col, form_col = st.columns(2)

with gauge_col:
    st.subheader("Utilization")
    total = day_rate["total_exercised"] if day_rate["total_exercised"] > 0 else 1
    pct = (day_rate["total_used"] / total) * 100

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=day_rate["total_used"],
        delta={"reference": day_rate["total_exercised"], "relative": False,
               "increasing": {"color": "#ef4444"}, "decreasing": {"color": "#22c55e"}},
        gauge={
            "axis": {"range": [0, day_rate["total_exercised"] + day_rate["additional_options"]]},
            "bar": {"color": "#3b82f6"},
            "steps": [
                {"range": [0, day_rate["total_exercised"]], "color": "#e5e7eb"},
                {"range": [day_rate["total_exercised"], day_rate["total_exercised"] + day_rate["additional_options"]], "color": "#fef3c7"},
            ],
            "threshold": {
                "line": {"color": "#ef4444", "width": 4},
                "thickness": 0.75,
                "value": day_rate["total_exercised"],
            },
        },
        title={"text": f"Days Used ({pct:.0f}%)"},
        number={"suffix": f" / {day_rate['total_exercised']}"},
    ))
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)

with form_col:
    st.subheader("Update Day Rate Options")
    with st.form("day_rate_form"):
        new_exercised = st.number_input("Total Exercised", min_value=0, value=day_rate["total_exercised"])
        new_used = st.number_input("Total Used", min_value=0, value=day_rate["total_used"])
        new_additional = st.number_input("Additional Options", min_value=0, value=day_rate["additional_options"])

        if st.form_submit_button("Update", type="primary"):
            execute(
                """UPDATE day_rate_options
                   SET total_exercised=?, total_used=?, additional_options=?, updated_at=datetime('now')
                   WHERE id=?""",
                (new_exercised, new_used, new_additional, day_rate["id"]),
            )
            st.success("Day rate options updated!")
            st.rerun()

# --- Day Rate Projects ---
st.markdown("---")
st.subheader("Day Rate Projects")

day_rate_projects = query("""
    SELECT p.*,
           COALESCE(SUM(le.bid_rate * le.hours), 0) as labor_charge,
           COALESCE(SUM(le.employee_rate * le.hours), 0) as labor_cost
    FROM projects p
    LEFT JOIN labor_entries le ON le.project_id = p.id
    WHERE p.is_daily_rate = 1
    GROUP BY p.id
    ORDER BY p.start_date DESC
""")

if day_rate_projects:
    dr_df = pd.DataFrame(day_rate_projects)
    display = dr_df[["pws_number", "report_title", "status", "days", "start_date", "end_date",
                      "labor_charge", "labor_cost"]].copy()
    display.columns = ["PWS", "Title", "Status", "Days", "Start", "End", "Labor Charge", "Labor Cost"]
    display["Profit"] = display["Labor Charge"] - display["Labor Cost"]
    st.dataframe(
        display.style.format({
            "Labor Charge": "${:,.2f}",
            "Labor Cost": "${:,.2f}",
            "Profit": "${:,.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown(f"**Total Day Rate Days Used:** {display['Days'].sum()}")
else:
    st.info("No day rate projects yet. Mark a project as 'Daily Rate Effort' on the Projects page.")

# --- Revenue Streams: Diamond / Athena / Sourced ---
st.markdown("---")
st.subheader("Revenue Streams")

revenue = query("SELECT * FROM revenue_streams LIMIT 1", fetchone=True)
if not revenue:
    execute("INSERT INTO revenue_streams (diamond_money, diamond_weeks, athena_billed, sourced_total) VALUES (0, 0, 0, 0)")
    revenue = query("SELECT * FROM revenue_streams LIMIT 1", fetchone=True)

rv1, rv2, rv3, rv4 = st.columns(4)
rv1.metric("Diamond Money", f"${revenue['diamond_money']:,.2f}")
rv2.metric("Diamond Weeks", f"{revenue['diamond_weeks']:.1f}")
rv3.metric("Athena Billed", f"${revenue['athena_billed']:,.2f}")
rv4.metric("Sourced Total", f"${revenue['sourced_total']:,.2f}")

with st.expander("Update Revenue Streams"):
    with st.form("revenue_form"):
        rc1, rc2 = st.columns(2)
        with rc1:
            new_diamond_money = st.number_input("Diamond Money ($)", value=float(revenue["diamond_money"]), step=100.0)
            new_diamond_weeks = st.number_input("Diamond Weeks", value=float(revenue["diamond_weeks"]), step=1.0)
        with rc2:
            new_athena = st.number_input("Athena Total Billed ($)", value=float(revenue["athena_billed"]), step=100.0)
            new_sourced = st.number_input("Sourced Total ($)", value=float(revenue["sourced_total"]), step=100.0)
        rev_notes = st.text_input("Notes", value=revenue.get("notes", "") or "")

        if st.form_submit_button("Update Revenue Streams", type="primary"):
            execute(
                """UPDATE revenue_streams
                   SET diamond_money=?, diamond_weeks=?, athena_billed=?, sourced_total=?, notes=?, updated_at=datetime('now')
                   WHERE id=?""",
                (new_diamond_money, new_diamond_weeks, new_athena, new_sourced, rev_notes, revenue["id"]),
            )
            st.success("Revenue streams updated!")
            st.rerun()
