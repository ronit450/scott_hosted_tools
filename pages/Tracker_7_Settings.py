import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from auth.auth_ui import require_login
from db.database import query, execute, get_connection
from utils.helpers import sidebar_quick_stats

require_login(tool="tracker")
st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
sidebar_quick_stats()

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

st.markdown("""
<div style="margin-bottom:20px;">
    <h1 style="margin:0; font-size:1.8rem;">Settings</h1>
    <p style="color:#64748b; margin:4px 0 0 0; font-size:0.95rem;">Manage roles, rates, and project data</p>
</div>
""", unsafe_allow_html=True)

tab_roles, tab_db = st.tabs(["Job Roles & Rates", "Database & Projects"])

# ========================
# JOB ROLES TAB
# ========================
with tab_roles:
    st.subheader("Manage Job Roles")
    st.markdown("Edit existing roles or add new ones. Changes apply to **new** project entries — existing projects keep their saved rates.")

    job_codes = query("SELECT * FROM job_codes ORDER BY title")

    # --- Rate Summary Table ---
    if job_codes:
        summary_df = pd.DataFrame(job_codes)
        summary_df["margin"] = summary_df["bid_rate"] - summary_df["employee_rate"]
        summary_df["margin_pct"] = (summary_df["margin"] / summary_df["bid_rate"] * 100).round(1)
        display = summary_df[["title", "bid_rate", "employee_rate", "margin", "margin_pct"]].copy()
        display.columns = ["Title", "Bid Rate", "Employee Rate", "Margin ($)", "Margin (%)"]
        st.dataframe(
            display.style.format({
                "Bid Rate": "${:,.2f}", "Employee Rate": "${:,.2f}",
                "Margin ($)": "${:,.2f}", "Margin (%)": "{:.1f}%",
            }),
            use_container_width=True, hide_index=True,
        )

        # KPI row
        avg_bid = summary_df["bid_rate"].mean()
        avg_emp = summary_df["employee_rate"].mean()
        avg_margin = summary_df["margin_pct"].mean()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Roles", len(job_codes))
        k2.metric("Avg Bid Rate", f"${avg_bid:,.2f}")
        k3.metric("Avg Employee Rate", f"${avg_emp:,.2f}")
        k4.metric("Avg Margin", f"{avg_margin:.1f}%")

    st.markdown("---")

    # --- Edit / Add Section ---
    role_options = ["-- Add New Role --"] + [jc["title"] for jc in job_codes] if job_codes else ["-- Add New Role --"]
    jc_map = {jc["title"]: jc for jc in job_codes} if job_codes else {}

    # Selectbox to choose what to do
    selected_role = st.selectbox("Select a role to edit, or add a new one:", role_options, key="role_selector")

    is_adding = selected_role == "-- Add New Role --"
    editing_jc = jc_map.get(selected_role)

    with st.form("role_form"):
        st.markdown(f"### {'Add New Role' if is_adding else f'Edit: {selected_role}'}")

        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            form_title = st.text_input(
                "Title",
                value="" if is_adding else editing_jc["title"],
                placeholder="e.g. Analyst 3 - SIGINT",
            )
        with fc2:
            form_bid = st.number_input(
                "Bid Rate ($/hr)",
                value=120.0 if is_adding else float(editing_jc["bid_rate"]),
                step=5.0, min_value=0.0,
            )
        with fc3:
            form_emp = st.number_input(
                "Employee Rate ($/hr)",
                value=100.0 if is_adding else float(editing_jc["employee_rate"]),
                step=5.0, min_value=0.0,
            )

        # Live margin preview
        if form_bid > 0:
            preview_margin = form_bid - form_emp
            preview_pct = (preview_margin / form_bid * 100)
            st.markdown(f"**Margin Preview:** ${preview_margin:,.2f} ({preview_pct:.1f}%)")

        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            submitted = st.form_submit_button(
                "Add Role" if is_adding else "Save Changes",
                type="primary", use_container_width=True,
            )
        with btn_col2:
            if not is_adding:
                delete_clicked = st.form_submit_button(
                    "Delete Role", use_container_width=True,
                )
            else:
                delete_clicked = False

        if submitted:
            if not form_title.strip():
                st.error("Title is required.")
            elif is_adding:
                existing = query("SELECT id FROM job_codes WHERE title = ?", (form_title.strip(),))
                if existing:
                    st.error(f"Role '{form_title}' already exists.")
                else:
                    execute(
                        "INSERT INTO job_codes (title, bid_rate, employee_rate) VALUES (?, ?, ?)",
                        (form_title.strip(), form_bid, form_emp),
                    )
                    st.toast(f"Added: {form_title}", icon="✅")
                    st.rerun()
            else:
                execute(
                    "UPDATE job_codes SET title=?, bid_rate=?, employee_rate=? WHERE id=?",
                    (form_title.strip(), form_bid, form_emp, editing_jc["id"]),
                )
                st.toast(f"Updated: {form_title}", icon="✅")
                st.rerun()

        if delete_clicked and not is_adding:
            # Check if role is used in any labor entries
            usage = query(
                "SELECT COUNT(*) as cnt FROM labor_entries WHERE job_code_id = ?",
                (editing_jc["id"],),
                fetchone=True,
            )
            if usage["cnt"] > 0:
                st.error(f"Cannot delete '{selected_role}' — it's used in {usage['cnt']} labor entry(ies). Remove those first.")
            else:
                execute("DELETE FROM job_codes WHERE id = ?", (editing_jc["id"],))
                st.toast(f"Deleted: {selected_role}", icon="🗑️")
                st.rerun()

# ========================
# DATABASE / PROJECTS TAB
# ========================
with tab_db:
    # --- DB Stats ---
    st.subheader("Database Info")

    project_count = query("SELECT COUNT(*) as cnt FROM projects", fetchone=True)["cnt"]
    labor_count = query("SELECT COUNT(*) as cnt FROM labor_entries", fetchone=True)["cnt"]
    imagery_count = query("SELECT COUNT(*) as cnt FROM imagery_orders", fetchone=True)["cnt"]
    catalog_count = query("SELECT COUNT(*) as cnt FROM imagery_catalog", fetchone=True)["cnt"]

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Projects", project_count)
    d2.metric("Labor Entries", labor_count)
    d3.metric("Imagery Orders", imagery_count)
    d4.metric("Catalog Products", catalog_count)

    db_path = Path(__file__).parent.parent / "data" / "tracker.db"
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        st.caption(f"Database: `{db_path}` | Size: {size_mb:.2f} MB")

    # --- Project Manager ---
    st.markdown("---")
    st.subheader("Project Manager")

    all_projects = query("SELECT * FROM projects ORDER BY pws_number, report_title")

    if not all_projects:
        st.info("No projects yet.")
    else:
        # PWS filter
        all_pws = sorted(set(p["pws_number"] for p in all_projects))
        selected_pws = st.selectbox("Filter by PWS", ["-- All --"] + all_pws, key="settings_pws")

        if selected_pws == "-- All --":
            filtered = all_projects
        else:
            filtered = [p for p in all_projects if p["pws_number"] == selected_pws]

        # Projects summary table
        proj_df = pd.DataFrame(filtered)
        display_cols = ["pws_number", "report_title", "status", "start_date", "end_date", "days"]
        display_df = proj_df[display_cols].copy()
        display_df.columns = ["PWS", "Title", "Status", "Start", "End", "Days"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Project selector for edit/delete
        proj_map = {f"{p['pws_number']} - {p['report_title']}": p for p in filtered}
        selected_proj_name = st.selectbox(
            "Select a project to view/edit:",
            list(proj_map.keys()),
            key="settings_proj_select",
        )
        proj = proj_map[selected_proj_name]

        # Project detail card
        st.markdown(f"### {proj['report_title']}")
        info1, info2, info3 = st.columns(3)
        info1.markdown(f"**PWS:** {proj['pws_number']}")
        info2.markdown(f"**Status:** {proj['status']}")
        info3.markdown(f"**Days:** {proj['days']}")

        if proj["start_date"] or proj["end_date"]:
            st.markdown(f"**Period:** {proj['start_date'] or 'N/A'} to {proj['end_date'] or 'N/A'}")
        if proj["notes"]:
            st.markdown(f"**Notes:** {proj['notes']}")

        # Labor & imagery counts for this project
        p_labor = query(
            "SELECT COUNT(*) as cnt FROM labor_entries WHERE project_id = ?",
            (proj["id"],), fetchone=True,
        )["cnt"]
        p_imagery = query(
            "SELECT COUNT(*) as cnt FROM imagery_orders WHERE project_id = ?",
            (proj["id"],), fetchone=True,
        )["cnt"]
        st.caption(f"{p_labor} personnel entries | {p_imagery} imagery orders")

        # Quick edit form
        with st.expander("Edit Project Details"):
            with st.form("edit_proj_form"):
                ep1, ep2, ep3 = st.columns(3)
                with ep1:
                    edit_pws = st.text_input("PWS Number", value=proj["pws_number"], key="ep_pws")
                    edit_title = st.text_input("Report Title", value=proj["report_title"], key="ep_title")
                with ep2:
                    edit_status = st.selectbox(
                        "Status", ["Ongoing", "Complete"],
                        index=0 if proj["status"] == "Ongoing" else 1,
                        key="ep_status",
                    )
                    edit_days = st.number_input("Days", value=proj["days"] or 1, min_value=0, key="ep_days")
                with ep3:
                    from datetime import datetime
                    edit_start = st.date_input(
                        "Start Date",
                        value=datetime.strptime(proj["start_date"], "%Y-%m-%d").date() if proj["start_date"] else None,
                        key="ep_start",
                    )
                    edit_end = st.date_input(
                        "End Date",
                        value=datetime.strptime(proj["end_date"], "%Y-%m-%d").date() if proj["end_date"] else None,
                        key="ep_end",
                    )
                edit_notes = st.text_area("Notes", value=proj["notes"] or "", key="ep_notes")

                if st.form_submit_button("Save Changes", type="primary", use_container_width=True):
                    if not edit_pws.strip() or not edit_title.strip():
                        st.error("PWS and Title are required.")
                    else:
                        execute(
                            """UPDATE projects SET pws_number=?, report_title=?, start_date=?, end_date=?,
                               status=?, notes=?, days=? WHERE id=?""",
                            (edit_pws.strip(), edit_title.strip(), str(edit_start), str(edit_end),
                             edit_status, edit_notes or None, edit_days, proj["id"]),
                        )
                        st.toast(f"Updated: {edit_title}", icon="✅")
                        st.rerun()

        # Delete with confirmation
        with st.expander("Delete Project"):
            st.warning(f"This will permanently delete **{proj['report_title']}** and all its labor entries and imagery orders.")
            if p_labor > 0 or p_imagery > 0:
                st.markdown(f"**This will also remove {p_labor} labor entries and {p_imagery} imagery orders.**")

            if st.button("Delete This Project", key="settings_del_proj"):
                st.session_state["settings_confirm_del"] = proj["id"]

            if st.session_state.get("settings_confirm_del") == proj["id"]:
                st.error("Are you sure? This cannot be undone.")
                dc1, dc2 = st.columns(2)
                if dc1.button("Yes, Delete", key="settings_confirm_del_btn"):
                    execute("DELETE FROM labor_entries WHERE project_id = ?", (proj["id"],))
                    execute("DELETE FROM imagery_orders WHERE project_id = ?", (proj["id"],))
                    execute("DELETE FROM projects WHERE id = ?", (proj["id"],))
                    st.session_state.pop("settings_confirm_del", None)
                    st.toast(f"Deleted: {proj['report_title']}", icon="🗑️")
                    st.rerun()
                if dc2.button("Cancel", key="settings_cancel_del_btn"):
                    st.session_state.pop("settings_confirm_del", None)
                    st.rerun()
