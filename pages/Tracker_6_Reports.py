import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from auth.auth_ui import require_login
from db.database import query
from reports.pdf_generator import generate_report, generate_pws_report
from utils.helpers import sidebar_quick_stats

require_login(tool="tracker")
sidebar_quick_stats()

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

st.title("Report Generation")

# Load projects
projects = query("SELECT * FROM projects ORDER BY created_at DESC")

if not projects:
    st.info("No projects yet. Create a project first.")
    st.stop()

# --- Report Mode ---
report_mode = st.radio("Report Type", ["Single Project", "PWS Consolidated", "Slack Notification"], horizontal=True)

all_pws = sorted(set(p["pws_number"] for p in projects))

if report_mode in ("Single Project", "PWS Consolidated"):
    # --- Project selector: PWS first, then projects under that PWS ---
    ps1, ps2 = st.columns(2)
    with ps1:
        selected_pws = st.selectbox("PWS Number", all_pws, key="report_pws")
    with ps2:
        if report_mode == "Single Project":
            pws_projects = [p for p in projects if p["pws_number"] == selected_pws]
            project_options = {p["report_title"]: p for p in pws_projects}
            selected_title = st.selectbox("Project", list(project_options.keys()), key="report_project")
        else:
            pws_projects = [p for p in projects if p["pws_number"] == selected_pws]
            st.info(f"{len(pws_projects)} project(s) under this PWS")

    # --- Report options ---
    st.subheader("Report Options")
    opt1, opt2, opt3 = st.columns(3)
    with opt1:
        include_summary = st.checkbox("Include Project Details", value=True)
    with opt2:
        include_imagery = st.checkbox("Include Imagery Orders", value=True)
    with opt3:
        include_financials = st.checkbox("Include Financial Summary", value=True)


def _load_project_data(proj):
    """Load labor and imagery for a project."""
    labor = query(
        """SELECT le.*, jc.title as job_title
           FROM labor_entries le
           JOIN job_codes jc ON le.job_code_id = jc.id
           WHERE le.project_id = ?
           ORDER BY le.id""",
        (proj["id"],),
    )
    imagery = query(
        "SELECT * FROM imagery_orders WHERE project_id = ? ORDER BY id",
        (proj["id"],),
    )
    return labor, imagery


if report_mode == "Single Project":
    project = project_options[selected_title]
    labor, imagery = _load_project_data(project)

    # --- Preview ---
    st.markdown("---")
    st.subheader("Report Preview")

    st.markdown(f"### {project['report_title']}")
    st.markdown(f"**PWS:** {project['pws_number']} | **Status:** {project['status']} | "
                f"**Days:** {project['days']}")

    if include_summary:
        st.markdown(f"**Period:** {project['start_date'] or 'N/A'} to {project['end_date'] or 'N/A'}")
        if project["notes"]:
            st.markdown(f"**Notes:** {project['notes']}")

    st.markdown("#### Personnel")
    if labor:
        labor_data = []
        total_hours = total_cost = total_charge = 0
        for entry in labor:
            hours = entry["hours"]
            cost = entry["employee_rate"] * hours
            charge = entry["bid_rate"] * hours
            total_hours += hours
            total_cost += cost
            total_charge += charge
            row = {"Role": entry["job_title"], "Person": entry["person_name"] or "", "Hours": f"{hours:.1f}"}
            if include_financials:
                row["Cost Rate"] = f"${entry['employee_rate']:,.2f}"
                row["Bid Rate"] = f"${entry['bid_rate']:,.2f}"
                row["Cost"] = f"${cost:,.2f}"
                row["Charge"] = f"${charge:,.2f}"
            labor_data.append(row)
        st.dataframe(pd.DataFrame(labor_data), use_container_width=True, hide_index=True)
        if include_financials:
            st.markdown(f"**Labor Total:** Hours: {total_hours:.1f} | Cost: ${total_cost:,.2f} | Charge: ${total_charge:,.2f}")
        else:
            st.markdown(f"**Labor Total:** Hours: {total_hours:.1f}")
    else:
        st.info("No personnel assigned.")

    if include_imagery:
        st.markdown("#### Imagery Orders")
        if imagery:
            img_data = []
            img_total_cost = img_total_charge = 0
            for order in imagery:
                img_total_cost += order["cost"]
                img_total_charge += order["charge"]
                row = {
                    "Provider": order["provider"], "Product": order["product"],
                    "Date": order["order_date"] or "", "Status": order.get("order_status", "Requested"),
                    "AOI": order["aoi"] or "",
                }
                if include_financials:
                    row["Cost"] = f"${order['cost']:,.2f}"
                    row["Charge"] = f"${order['charge']:,.2f}"
                img_data.append(row)
            st.dataframe(pd.DataFrame(img_data), use_container_width=True, hide_index=True)
            if include_financials:
                st.markdown(f"**Imagery Total:** Cost: ${img_total_cost:,.2f} | Charge: ${img_total_charge:,.2f}")
        else:
            st.info("No imagery orders.")

    if include_financials:
        st.markdown("#### Financial Summary")
        l_cost = sum(e["employee_rate"] * e["hours"] for e in labor) if labor else 0
        l_charge = sum(e["bid_rate"] * e["hours"] for e in labor) if labor else 0
        i_cost = sum(o["cost"] for o in imagery) if imagery else 0
        i_charge = sum(o["charge"] for o in imagery) if imagery else 0
        grand_cost = l_cost + i_cost
        grand_charge = l_charge + i_charge
        profit = grand_charge - grand_cost
        margin_pct = (profit / grand_charge * 100) if grand_charge > 0 else 0

        fc1, fc2, fc3, fc4 = st.columns(4)
        fc1.metric("Grand Total Cost", f"${grand_cost:,.2f}")
        fc2.metric("Grand Total Charge", f"${grand_charge:,.2f}")
        fc3.metric("Profit", f"${profit:,.2f}")
        fc4.metric("Margin", f"{margin_pct:.1f}%")

    # Generate PDF
    st.markdown("---")
    if st.button("Generate PDF Report", type="primary", use_container_width=True):
        with st.spinner("Generating PDF..."):
            pdf_buffer = generate_report(
                project, labor, imagery,
                include_summary=include_summary,
                include_imagery=include_imagery,
                include_financials=include_financials,
            )
            filename = f"{project['pws_number']}_{project['report_title'].replace(' ', '_')}_Report.pdf"
            st.download_button(
                label="Download PDF Report", data=pdf_buffer,
                file_name=filename, mime="application/pdf", use_container_width=True,
            )
            st.success("PDF generated! Click the download button above.")

elif report_mode == "PWS Consolidated":
    # PWS Consolidated Report
    st.markdown("---")
    st.subheader(f"PWS Consolidated Preview: {selected_pws}")
    st.markdown(f"**{len(pws_projects)} project(s)** under this PWS")

    grand_l_cost = grand_l_charge = grand_i_cost = grand_i_charge = 0
    all_projects_data = []

    for proj in pws_projects:
        labor, imagery = _load_project_data(proj)
        all_projects_data.append({"project": proj, "labor": labor, "imagery": imagery})

        l_cost = sum(e["employee_rate"] * e["hours"] for e in labor) if labor else 0
        l_charge = sum(e["bid_rate"] * e["hours"] for e in labor) if labor else 0
        i_cost = sum(o["cost"] for o in imagery) if imagery else 0
        i_charge = sum(o["charge"] for o in imagery) if imagery else 0
        grand_l_cost += l_cost
        grand_l_charge += l_charge
        grand_i_cost += i_cost
        grand_i_charge += i_charge

    total_cost = grand_l_cost + grand_i_cost
    total_charge = grand_l_charge + grand_i_charge
    total_profit = total_charge - total_cost
    margin_pct = (total_profit / total_charge * 100) if total_charge > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Cost", f"${total_cost:,.2f}")
    k2.metric("Total Charge", f"${total_charge:,.2f}")
    k3.metric("Profit", f"${total_profit:,.2f}")
    k4.metric("Margin", f"{margin_pct:.1f}%")

    # Projects summary
    summary_data = []
    for pd_item in all_projects_data:
        proj = pd_item["project"]
        labor = pd_item["labor"]
        imagery = pd_item["imagery"]
        l_c = sum(e["employee_rate"] * e["hours"] for e in labor) if labor else 0
        l_ch = sum(e["bid_rate"] * e["hours"] for e in labor) if labor else 0
        i_c = sum(o["cost"] for o in imagery) if imagery else 0
        i_ch = sum(o["charge"] for o in imagery) if imagery else 0
        summary_data.append({
            "Project": proj["report_title"], "Status": proj["status"],
            "Labor Cost": l_c, "Labor Charge": l_ch,
            "Imagery Cost": i_c, "Imagery Charge": i_ch,
            "Profit": (l_ch - l_c) + (i_ch - i_c),
        })

    summary_df = pd.DataFrame(summary_data)
    st.dataframe(
        summary_df.style.format({
            "Labor Cost": "${:,.2f}", "Labor Charge": "${:,.2f}",
            "Imagery Cost": "${:,.2f}", "Imagery Charge": "${:,.2f}", "Profit": "${:,.2f}",
        }),
        use_container_width=True, hide_index=True,
    )

    # Generate consolidated PDF
    st.markdown("---")
    if st.button("Generate PWS Consolidated PDF", type="primary", use_container_width=True):
        with st.spinner("Generating consolidated PDF..."):
            pdf_buffer = generate_pws_report(
                selected_pws, all_projects_data,
                include_summary=include_summary,
                include_imagery=include_imagery,
                include_financials=include_financials,
            )
            filename = f"{selected_pws}_Consolidated_Report.pdf"
            st.download_button(
                label="Download Consolidated PDF", data=pdf_buffer,
                file_name=filename, mime="application/pdf", use_container_width=True,
            )
            st.success("Consolidated PDF generated! Click the download button above.")

else:
    # --- Slack Notification Generator ---
    st.markdown("---")
    st.subheader("Slack Notification")
    st.caption("Select a PWS to see project cards with copyable Slack messages.")

    # PWS filter for slack
    slack_pws = st.selectbox("PWS Number", all_pws, key="slack_pws")
    slack_projects = [p for p in projects if p["pws_number"] == slack_pws]

    if not slack_projects:
        st.info("No projects under this PWS.")
        st.stop()

    has_any = False
    for idx, proj in enumerate(slack_projects):
        labor, _ = _load_project_data(proj)
        if not labor:
            continue

        # Group hours by person, convert to days
        person_hours = {}
        for entry in labor:
            name = entry["person_name"] or entry["job_title"]
            person_hours[name] = person_hours.get(name, 0) + entry["hours"]

        if not person_hours:
            continue

        has_any = True

        # Build the slack text for this project
        lines = [f"{proj['pws_number']} - {proj['report_title']}"]
        for name, hours in person_hours.items():
            days = hours / 8
            if days == int(days):
                day_str = f"{int(days)}d"
            else:
                day_str = f"{days:.1f}d"
            lines.append(f"@{name} {day_str}")
        card_text = "\n".join(lines)

        # Build person HTML rows
        person_rows = ""
        for name, hours in person_hours.items():
            days = hours / 8
            if days == int(days):
                day_str = f"{int(days)}d"
            else:
                day_str = f"{days:.1f}d"
            person_rows += f'<div style="padding: 4px 0; color: #c9d1d9; font-size: 0.92rem;">@{name} <b>{day_str}</b></div>'

        # Render styled card
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #141e2e, #0f1724);
                    border: 1px solid #253348; border-left: 3px solid #60a5fa;
                    border-radius: 12px; padding: 20px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <span style="color: #60a5fa; font-size: 1.05rem; font-weight: 600;">
                    {proj['pws_number']} - {proj['report_title']}
                </span>
            </div>
            {person_rows}
        </div>
        """, unsafe_allow_html=True)

        # Copy button using st.code (natively has copy icon)
        st.code(card_text, language=None)

    if not has_any:
        st.info("No personnel data found for projects under this PWS.")
