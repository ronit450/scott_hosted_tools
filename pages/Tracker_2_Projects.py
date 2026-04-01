import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from auth.auth_ui import require_login
from db.database import query, execute, get_connection, init_db
from utils.helpers import sidebar_quick_stats

require_login(tool="tracker")
init_db()
sidebar_quick_stats()

css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

ORDER_STATUSES = ["Requested", "Approved", "Ordered", "Collected", "Delivered"]


@st.dialog("Confirm Save")
def save_dialog():
    """Modal popup to confirm saving the project."""
    sd = st.session_state.get("_save_payload", {})
    st.markdown(f"Save project **'{sd.get('title', '')}'** under PWS **{sd.get('pws', '')}**?")

    labor_count = len(st.session_state.get("labor_data", []))
    imagery_count = len(st.session_state.get("imagery_data", []))
    st.caption(f"{labor_count} personnel entries, {imagery_count} imagery orders")

    c1, c2 = st.columns(2)
    if c1.button("Yes, Save", type="primary", use_container_width=True, key="dlg_save"):
        st.session_state["_do_save"] = True
        st.rerun()
    if c2.button("Cancel", use_container_width=True, key="dlg_cancel"):
        st.session_state.pop("_save_payload", None)
        st.rerun()


@st.dialog("Update Imagery Order")
def imagery_edit_dialog():
    """Modal popup to confirm imagery order update."""
    payload = st.session_state.get("_img_edit_payload", {})
    idx = payload.get("idx", 0)
    data = payload.get("data", {})

    st.markdown(f"Update order for **{data.get('Provider', '')}** — {data.get('Product', '')[:40]}?")

    # Show what changed
    preview_cost = data.get("Cost Per Shot", 0) * data.get("Shots Delivered", 0)
    preview_charge = data.get("Charge Per Shot", 0) * data.get("Shots Delivered", 0)
    preview_profit = preview_charge - preview_cost

    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Status", data.get("Status", ""))
    mc2.metric("Shots", f"{data.get('Shots Delivered', 0)} / {data.get('Shots Requested', 0)} req")
    profit_col = "#22c55e" if preview_profit >= 0 else "#ef4444"
    mc3.metric("Profit", f"${preview_profit:,.2f}")

    st.caption(f"Total Cost: ${preview_cost:,.2f}  |  Total Charge: ${preview_charge:,.2f}")

    c1, c2 = st.columns(2)
    if c1.button("Confirm Update", type="primary", use_container_width=True, key="dlg_img_confirm"):
        st.session_state["imagery_data"][idx] = data
        st.session_state.pop("editing_imagery", None)
        st.session_state.pop("_img_edit_payload", None)
        st.session_state["_dirty"] = True
        st.toast(f"Updated {data['Provider']} - {data['Product'][:25]}", icon="✅")
        st.rerun()
    if c2.button("Cancel", use_container_width=True, key="dlg_img_cancel"):
        st.session_state.pop("_img_edit_payload", None)
        st.rerun()


@st.dialog("Unlock Charge Field")
def unlock_charge_dialog():
    """Password prompt to unlock the charge/shot field."""
    st.markdown("Enter the password to unlock charge editing.")
    pwd = st.text_input("Password", type="password", key="unlock_pwd_input")
    c1, c2 = st.columns(2)
    if c1.button("Unlock", type="primary", use_container_width=True, key="dlg_unlock_confirm"):
        if pwd == "scott":
            st.session_state["_charge_unlocked"] = True
            st.toast("Charge field unlocked!", icon="🔓")
            st.rerun()
        else:
            st.error("Incorrect password.")
    if c2.button("Cancel", use_container_width=True, key="dlg_unlock_cancel"):
        st.rerun()


@st.dialog("Add New PWS")
def new_pws_dialog():
    """Modal popup to create a new PWS entry."""
    pws_num = st.text_input("PWS Number", key="new_pws_number")
    pws_name = st.text_input("PWS Name", key="new_pws_name")
    days_ex = st.number_input("Days Exercised", min_value=0, step=1, value=0, key="new_pws_days")

    add_dates = st.checkbox("Add PWS timeline", value=False, key="new_pws_add_dates")
    pws_start = None
    pws_end = None
    if add_dates:
        dc1, dc2 = st.columns(2)
        with dc1:
            pws_start = st.date_input("Start Date", value=date.today(), key="new_pws_start")
        with dc2:
            pws_end = st.date_input("End Date", value=date.today(), key="new_pws_end")

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("Save PWS", type="primary", use_container_width=True, key="dlg_pws_save"):
        if not pws_num.strip():
            st.error("PWS Number is required.")
            return
        if not pws_name.strip():
            st.error("PWS Name is required.")
            return
        # Check for duplicate
        existing = query("SELECT id FROM pws_day_rate WHERE pws_number = ?", (pws_num.strip(),), fetchone=True)
        if existing:
            st.error(f"PWS {pws_num.strip()} already exists.")
            return
        execute(
            """INSERT INTO pws_day_rate (pws_number, pws_name, total_exercised, start_date, end_date)
               VALUES (?, ?, ?, ?, ?)""",
            (pws_num.strip(), pws_name.strip(), days_ex,
             str(pws_start) if pws_start else None,
             str(pws_end) if pws_end else None),
        )
        st.toast(f"PWS {pws_num.strip()} created!", icon="✅")
        st.rerun()
    if c2.button("Cancel", use_container_width=True, key="dlg_pws_cancel"):
        st.rerun()


@st.dialog("Edit PWS")
def edit_pws_dialog(pws_number):
    """Modal popup to edit an existing PWS entry."""
    pws_record = query("SELECT * FROM pws_day_rate WHERE pws_number = ?", (pws_number,), fetchone=True)
    if not pws_record:
        st.error(f"PWS {pws_number} not found.")
        return

    pws_num = st.text_input("PWS Number", value=pws_record["pws_number"], key="edit_pws_number")
    pws_name = st.text_input("PWS Name", value=pws_record.get("pws_name", "") or "", key="edit_pws_name")
    days_ex = st.number_input("Days Exercised", min_value=0, step=1,
                              value=int(pws_record.get("total_exercised", 0) or 0), key="edit_pws_days")

    existing_start = None
    existing_end = None
    if pws_record.get("start_date"):
        try:
            existing_start = datetime.strptime(pws_record["start_date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            existing_start = None
    if pws_record.get("end_date"):
        try:
            existing_end = datetime.strptime(pws_record["end_date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            existing_end = None

    has_dates = existing_start is not None
    add_dates = st.checkbox("PWS timeline", value=has_dates, key="edit_pws_add_dates")
    pws_start = None
    pws_end = None
    if add_dates:
        dc1, dc2 = st.columns(2)
        with dc1:
            pws_start = st.date_input("Start Date", value=existing_start or date.today(), key="edit_pws_start")
        with dc2:
            pws_end = st.date_input("End Date", value=existing_end or date.today(), key="edit_pws_end")

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("Update PWS", type="primary", use_container_width=True, key="dlg_pws_update"):
        if not pws_num.strip():
            st.error("PWS Number is required.")
            return
        if not pws_name.strip():
            st.error("PWS Name is required.")
            return
        # If PWS number changed, check for duplicates
        if pws_num.strip() != pws_number:
            existing = query("SELECT id FROM pws_day_rate WHERE pws_number = ?", (pws_num.strip(),), fetchone=True)
            if existing:
                st.error(f"PWS {pws_num.strip()} already exists.")
                return
            # Update projects referencing old PWS number
            execute("UPDATE projects SET pws_number = ? WHERE pws_number = ?",
                    (pws_num.strip(), pws_number))
        execute(
            """UPDATE pws_day_rate SET pws_number=?, pws_name=?, total_exercised=?,
               start_date=?, end_date=? WHERE pws_number=?""",
            (pws_num.strip(), pws_name.strip(), days_ex,
             str(pws_start) if pws_start else None,
             str(pws_end) if pws_end else None,
             pws_number),
        )
        st.toast(f"PWS {pws_num.strip()} updated!", icon="✅")
        st.rerun()
    if c2.button("Cancel", use_container_width=True, key="dlg_pws_edit_cancel"):
        st.rerun()


@st.dialog("Available People", width="large")
def available_people_dialog():
    """Show all known people from previous projects for quick-add."""
    # Gather unique people from labor_entries across all projects
    known_people = query("""
        SELECT DISTINCT le.person_name, jc.title as role, jc.employee_rate, jc.bid_rate, jc.id as job_code_id
        FROM labor_entries le
        JOIN job_codes jc ON le.job_code_id = jc.id
        WHERE le.person_name IS NOT NULL AND le.person_name != ''
        ORDER BY le.person_name, jc.title
    """)

    if not known_people:
        st.info("No people found from previous projects. Add personnel manually using the form below.")
        if st.button("Close", use_container_width=True):
            st.rerun()
        return

    st.caption("Select people to add to this project. You can modify hours, rates, and charge status after adding.")

    # Track selections
    selected = []
    # Group by person name
    people_by_name = {}
    for p in known_people:
        name = p["person_name"]
        if name not in people_by_name:
            people_by_name[name] = []
        people_by_name[name].append(p)

    # Already added people (to show as disabled/info)
    current_labor = st.session_state.get("labor_data", [])
    current_people = {(r["Person Name"], r["Role"]) for r in current_labor if r.get("Person Name")}

    for name, roles in people_by_name.items():
        for role_entry in roles:
            already_added = (name, role_entry["role"]) in current_people
            key = f"avail_{name}_{role_entry['role']}"
            ac1, ac2, ac3 = st.columns([0.3, 2, 2])
            with ac1:
                if already_added:
                    st.markdown("✅")
                else:
                    if st.checkbox("", key=key, label_visibility="collapsed"):
                        selected.append(role_entry)
            with ac2:
                st.markdown(f"**{name}**")
            with ac3:
                if already_added:
                    st.caption(f"{role_entry['role']} — already added")
                else:
                    st.caption(role_entry["role"])

    st.markdown("---")
    bc1, bc2 = st.columns(2)
    if bc1.button("Add Selected", type="primary", use_container_width=True, key="dlg_add_people"):
        if not selected:
            st.warning("No people selected.")
            return
        for person in selected:
            st.session_state["labor_data"].append({
                "Role": person["role"],
                "Person Name": person["person_name"],
                "Hours": 8.0,
                "Employee Rate": person["employee_rate"],
                "Bid Rate": person["bid_rate"],
                "No Charge": False,
            })
        st.session_state["_dirty"] = True
        st.toast(f"Added {len(selected)} personnel", icon="✅")
        st.rerun()
    if bc2.button("Cancel", use_container_width=True, key="dlg_add_people_cancel"):
        st.rerun()


@st.dialog("Delete PWS")
def delete_pws_dialog(pws_number):
    """Modal popup to confirm deleting a PWS entry."""
    project_count = query("SELECT COUNT(*) as cnt FROM projects WHERE pws_number = ?",
                          (pws_number,), fetchone=True)["cnt"]

    st.markdown(f"Are you sure you want to delete PWS **{pws_number}**?")
    if project_count > 0:
        st.warning(f"This PWS has **{project_count} project(s)**. Deleting the PWS will **not** delete projects, "
                   "but they will no longer be linked to a PWS.")

    c1, c2 = st.columns(2)
    if c1.button("Delete", type="primary", use_container_width=True, key="dlg_pws_delete_confirm"):
        execute("DELETE FROM pws_day_rate WHERE pws_number = ?", (pws_number,))
        st.toast(f"PWS {pws_number} deleted.", icon="🗑️")
        st.rerun()
    if c2.button("Cancel", use_container_width=True, key="dlg_pws_delete_cancel"):
        st.rerun()


# --- Helper: count working days ---
def count_days(start, end, include_weekends):
    """Count days between start and end (inclusive)."""
    if end < start:
        return 0
    total = (end - start).days + 1
    if include_weekends:
        return total
    weekdays = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            weekdays += 1
        current += timedelta(days=1)
    return weekdays


# --- Section header helper ---
def section_header(title, subtitle=None):
    st.markdown(f"""
    <div style="margin: 8px 0 16px 0;">
        <h3 style="color:#f1f5f9; margin:0; font-size:1.15rem; font-weight:600;">{title}</h3>
        {f'<p style="color:#64748b; font-size:0.82rem; margin:4px 0 0 0;">{subtitle}</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


# --- Load reference data ---
job_codes = query("SELECT * FROM job_codes ORDER BY title")
job_code_map = {jc["title"]: jc for jc in job_codes}
job_code_titles = [jc["title"] for jc in job_codes]

catalog = query("SELECT * FROM imagery_catalog ORDER BY provider, description")
catalog_options = {f"{c['provider']} - {c['description']}": c for c in catalog}

# --- Handle post-save reset (must happen before widgets render) ---
if st.session_state.get("_reset_form"):
    st.session_state.pop("_reset_form", None)
    st.session_state["project_selector"] = 0
    st.session_state["labor_data"] = []
    st.session_state["imagery_data"] = []
    st.session_state.pop("_proj_key", None)
    st.session_state["_dirty"] = False
    st.session_state.pop("editing_labor", None)
    st.session_state.pop("editing_imagery", None)
    st.session_state.pop("editing_team", None)
    st.session_state.pop("confirm_delete", None)

# --- Handle pending edit navigation (must happen before widget renders) ---
if st.session_state.get("_pending_edit_project_id") is not None:
    st.session_state["_view_mode"] = "edit"
    st.session_state.pop("_proj_key", None)
    st.session_state.pop("editing_labor", None)
    st.session_state.pop("editing_imagery", None)
    st.session_state.pop("editing_team", None)
    # Will resolve index after filtered_projects is built
if st.session_state.get("_pending_new_project"):
    st.session_state.pop("_pending_new_project", None)
    st.session_state["_view_mode"] = "edit"
    st.session_state["project_selector"] = 0
    st.session_state["labor_data"] = []
    st.session_state["imagery_data"] = []
    st.session_state.pop("_proj_key", None)
    st.session_state["_dirty"] = False

# --- Sidebar: PWS filter + Project selector ---
projects = query("SELECT * FROM projects ORDER BY created_at DESC")

# Build PWS list: from projects (latest first) + any PWS in pws_day_rate that have no projects yet
all_pws = list(dict.fromkeys(p["pws_number"] for p in projects)) if projects else []
_pws_only = query("SELECT pws_number FROM pws_day_rate ORDER BY updated_at DESC")
for r in _pws_only:
    if r["pws_number"] not in all_pws:
        all_pws.append(r["pws_number"])
st.sidebar.markdown("---")
st.sidebar.markdown("### Navigate")

# Build sidebar PWS display with names
_sb_pws_records = {r["pws_number"]: r.get("pws_name", "") for r in query("SELECT pws_number, pws_name FROM pws_day_rate")}
_sb_pws_display = ["-- All --"]
_sb_pws_values = ["-- All --"]
for p in all_pws:
    name = _sb_pws_records.get(p, "")
    _sb_pws_display.append(f"{p} - {name}" if name else p)
    _sb_pws_values.append(p)
_sb_display_to_value = dict(zip(_sb_pws_display, _sb_pws_values))

selected_pws_display = st.sidebar.selectbox(
    "PWS Number",
    _sb_pws_display,
    key="pws_filter",
)
selected_pws = _sb_display_to_value.get(selected_pws_display, "-- All --")

if selected_pws == "-- All --":
    filtered_projects = projects
else:
    filtered_projects = [p for p in projects if p["pws_number"] == selected_pws]

# Resolve pending edit project -> selector index (before widget renders)
_pending_pid = st.session_state.pop("_pending_edit_project_id", None)
if _pending_pid is not None:
    for _i, _p in enumerate(filtered_projects):
        if _p["id"] == _pending_pid:
            st.session_state["project_selector"] = _i + 1
            break

project_names = ["-- New Project --"] + [
    f"{p['pws_number']} - {p['report_title']}" for p in filtered_projects
]

selected_idx = st.sidebar.selectbox(
    "Project",
    range(len(project_names)),
    format_func=lambda i: project_names[i],
    key="project_selector",
)

is_new = selected_idx == 0
current_project = None if is_new else filtered_projects[selected_idx - 1]


# --- Initialize session state for editable data ---
def _init_labor():
    if not is_new and current_project:
        rows = query(
            """SELECT le.*, jc.title as job_title
               FROM labor_entries le
               JOIN job_codes jc ON le.job_code_id = jc.id
               WHERE le.project_id = ? ORDER BY le.id""",
            (current_project["id"],),
        )
        return [
            {"Role": r["job_title"], "Person Name": r["person_name"] or "",
             "Hours": r["hours"], "Employee Rate": r["employee_rate"],
             "Bid Rate": r["bid_rate"], "No Charge": False}
            for r in rows
        ]
    return []


def _init_imagery():
    if not is_new and current_project:
        rows = query(
            "SELECT * FROM imagery_orders WHERE project_id = ? ORDER BY id",
            (current_project["id"],),
        )
        result = []
        for r in rows:
            cps = r.get("cost_per_shot", 0) or 0
            chps = r.get("charge_per_shot", 0) or 0
            shots_del = r["shots_delivered"] or 0
            # Backward compat: if per-shot is 0 but total isn't, derive per-shot
            if cps == 0 and r["cost"] > 0 and shots_del > 0:
                cps = r["cost"] / shots_del
            if chps == 0 and r["charge"] > 0 and shots_del > 0:
                chps = r["charge"] / shots_del
            result.append({
                "Provider": r["provider"], "Product": r["product"],
                "Date": r["order_date"] or "", "Status": r.get("order_status", "Requested"),
                "AOI": r["aoi"] or "",
                "Shots Requested": r.get("shots_requested", 0) or 0,
                "Shots Delivered": shots_del,
                "Cost Per Shot": cps,
                "Charge Per Shot": chps,
            })
        return result
    return []


proj_key = current_project["id"] if current_project else "new"
if st.session_state.get("_proj_key") != proj_key:
    st.session_state["_proj_key"] = proj_key
    st.session_state["labor_data"] = _init_labor()
    st.session_state["imagery_data"] = _init_imagery()
    st.session_state["_dirty"] = False
    st.session_state.pop("editing_labor", None)
    st.session_state.pop("editing_imagery", None)
    st.session_state.pop("editing_team", None)
    st.session_state.pop("_charge_unlocked", None)

if "labor_data" not in st.session_state:
    st.session_state["labor_data"] = _init_labor()
if "imagery_data" not in st.session_state:
    st.session_state["imagery_data"] = _init_imagery()


def mark_dirty():
    st.session_state["_dirty"] = True


# --- View Mode: List vs Edit ---
if "_view_mode" not in st.session_state:
    st.session_state["_view_mode"] = "list"


def switch_to_edit(project_id=None):
    """Switch to edit view for a specific project or new project."""
    if project_id is None:
        st.session_state["_pending_new_project"] = True
    else:
        st.session_state["_pending_edit_project_id"] = project_id
    st.rerun()


# ============================================================
# LIST VIEW — Projects overview with all projects, people, etc.
# ============================================================
if st.session_state["_view_mode"] == "list":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h1 style="margin:0; font-size:2rem; font-weight:700;
                   background: linear-gradient(135deg, #60a5fa, #a78bfa);
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                   background-clip: text;">Projects</h1>
        <p style="color:#64748b; margin:4px 0 0 0; font-size:0.95rem;">Manage all projects, personnel, and imagery orders</p>
    </div>
    """, unsafe_allow_html=True)

    # Top bar: Add New Project + New PWS + PWS filter + Edit/Delete PWS
    top1, top2, top3, top4, top5 = st.columns([1, 1, 1.5, 0.5, 0.5])
    with top1:
        if st.button("+ New Project", type="primary", use_container_width=True):
            switch_to_edit(None)
            st.rerun()
    with top2:
        if st.button("+ New PWS", use_container_width=True):
            new_pws_dialog()

    if not all_pws:
        st.info("No PWS found. Click **+ New PWS** to create one first.")
        st.stop()

    with top3:
        # Build display labels: "PWS_NUMBER - PWS_NAME" when name exists
        pws_records = {r["pws_number"]: r.get("pws_name", "") for r in query("SELECT pws_number, pws_name FROM pws_day_rate")}
        pws_display = []
        for p in all_pws:
            name = pws_records.get(p, "")
            pws_display.append(f"{p} - {name}" if name else p)
        pws_display_map = dict(zip(pws_display, all_pws))
        selected_display = st.selectbox("Filter by PWS", pws_display, key="list_pws_display",
                                        label_visibility="collapsed")
        list_pws_filter = pws_display_map.get(selected_display, all_pws[0] if all_pws else "")
    with top4:
        if st.button("✏️", use_container_width=True, help="Edit selected PWS", key="edit_pws_btn"):
            edit_pws_dialog(list_pws_filter)
    with top5:
        if st.button("🗑️", use_container_width=True, help="Delete selected PWS", key="delete_pws_btn"):
            delete_pws_dialog(list_pws_filter)

    # Get project data with financials
    all_project_data = query("SELECT * FROM v_project_profit")
    display_projects = [p for p in all_project_data if p["pws_number"] == list_pws_filter]

    if not display_projects:
        st.info("No projects yet. Click **+ New Project** to get started.")
        st.stop()

    # KPI summary
    ov_charge = sum(p["grand_total_charge"] for p in display_projects)
    ov_cost = sum(p["grand_total_cost"] for p in display_projects)
    ov_profit = sum(p["total_profit"] for p in display_projects)
    ov_active = sum(1 for p in display_projects if p["status"] == "Ongoing")
    ov_margin = (ov_profit / ov_charge * 100) if ov_charge > 0 else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Projects", f"{ov_active} active / {len(display_projects)} total")
    k2.metric("Revenue", f"${ov_charge:,.0f}")
    k3.metric("Cost", f"${ov_cost:,.0f}")
    k4.metric("Profit", f"${ov_profit:,.0f}")
    k5.metric("Margin", f"{ov_margin:.1f}%")

    # Day rate tracking (per-PWS)
    pws_dr = query("SELECT * FROM pws_day_rate WHERE pws_number = ?", (list_pws_filter,), fetchone=True)
    total_exercised = pws_dr["total_exercised"] if pws_dr else 0
    days_used = sum(p.get("days", 0) or 0 for p in display_projects)
    days_remaining = total_exercised - days_used

    editing_days = st.session_state.get("_editing_days_exercised", False)

    if not editing_days:
        if days_remaining >= 0:
            rem_delta = f"{days_remaining} remaining"
            rem_color = "normal"
        else:
            rem_delta = f"{abs(days_remaining)} exceeded"
            rem_color = "inverse"

        d1, d2, d3, d4 = st.columns([1, 1, 1, 0.2])
        d1.metric("Days Exercised", total_exercised)
        d2.metric("Days Used", int(days_used))
        d3.metric("Days Remaining", int(days_remaining), delta=rem_delta, delta_color=rem_color)
        with d4:
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            if st.button("✏️", key="edit_days_btn", help="Edit Days Exercised"):
                st.session_state["_editing_days_exercised"] = True
                st.rerun()
    else:
        d1, d2, d3, d4 = st.columns([1, 1, 1, 0.5])
        with d1:
            new_exercised = st.number_input("Days Exercised", value=int(total_exercised),
                                             min_value=0, step=1, key="edit_days_exercised_input")
        with d2:
            st.metric("Days Used", int(days_used))
        with d3:
            new_remaining = new_exercised - days_used
            if new_remaining >= 0:
                nr_delta = f"{int(new_remaining)} remaining"
                nr_color = "normal"
            else:
                nr_delta = f"{int(abs(new_remaining))} exceeded"
                nr_color = "inverse"
            st.metric("Days Remaining", int(new_remaining), delta=nr_delta, delta_color=nr_color)
        with d4:
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            sb1, sb2 = st.columns(2)
            if sb1.button("✓", key="save_days_btn", type="primary", help="Save"):
                if pws_dr:
                    execute("UPDATE pws_day_rate SET total_exercised = ?, updated_at = datetime('now') WHERE pws_number = ?",
                            (new_exercised, list_pws_filter))
                else:
                    execute("INSERT INTO pws_day_rate (pws_number, total_exercised) VALUES (?, ?)",
                            (list_pws_filter, new_exercised))
                st.session_state.pop("_editing_days_exercised", None)
                st.toast(f"Days Exercised updated for PWS {list_pws_filter}!", icon="✅")
                st.rerun()
            if sb2.button("✕", key="cancel_days_btn", help="Cancel"):
                st.session_state.pop("_editing_days_exercised", None)
                st.rerun()

    st.markdown("")

    # Project cards
    for proj in display_projects:
        p_margin = (proj["total_profit"] / proj["grand_total_charge"] * 100) if proj["grand_total_charge"] > 0 else 0
        if p_margin >= 20:
            margin_color = "#22c55e"
        elif p_margin >= 10:
            margin_color = "#f59e0b"
        else:
            margin_color = "#ef4444"
        status_c = "#22c55e" if proj["status"] == "Ongoing" else "#64748b"

        with st.container(border=True):
            # Row 1: Title, PWS, Status, Actions
            r1c1, r1c2, r1c3, r1c4 = st.columns([3, 1, 1, 1])
            with r1c1:
                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:1.05rem; font-weight:600; color:#f1f5f9;">{proj['report_title']}</span>
                    <span style="background:{status_c}22; color:{status_c}; padding:2px 10px; border-radius:12px;
                                 font-size:0.7rem; font-weight:600; text-transform:uppercase;">{proj['status']}</span>
                </div>
                <span style="color:#94a3b8; font-size:0.82rem;">PWS {proj['pws_number']}</span>
                """, unsafe_allow_html=True)
            with r1c2:
                st.markdown(f'<span style="color:#94a3b8; font-size:0.78rem;">Revenue</span><br><span style="font-weight:600;">${proj["grand_total_charge"]:,.0f}</span>', unsafe_allow_html=True)
            with r1c3:
                st.markdown(f'<span style="color:#94a3b8; font-size:0.78rem;">Profit</span><br><span style="color:{margin_color}; font-weight:600;">${proj["total_profit"]:,.0f}</span>', unsafe_allow_html=True)
            with r1c4:
                btn1, btn2 = st.columns(2)
                if btn1.button("Edit", key=f"list_edit_{proj['project_id']}", use_container_width=True):
                    switch_to_edit(proj["project_id"])
                    st.rerun()
                if btn2.button("Delete", key=f"list_del_{proj['project_id']}", use_container_width=True):
                    st.session_state[f"_confirm_del_{proj['project_id']}"] = True
                    st.rerun()

            # Confirm delete inline
            if st.session_state.get(f"_confirm_del_{proj['project_id']}"):
                st.warning(f"Delete **{proj['report_title']}**? This cannot be undone.")
                dc1, dc2, dc3 = st.columns([1, 1, 4])
                if dc1.button("Yes, Delete", key=f"list_confirm_del_{proj['project_id']}", type="primary"):
                    execute("DELETE FROM projects WHERE id = ?", (proj["project_id"],))
                    st.session_state.pop(f"_confirm_del_{proj['project_id']}", None)
                    st.toast("Project deleted.", icon="🗑️")
                    st.rerun()
                if dc2.button("Cancel", key=f"list_cancel_del_{proj['project_id']}"):
                    st.session_state.pop(f"_confirm_del_{proj['project_id']}", None)
                    st.rerun()

            # Row 2: People on this project
            people = query("""
                SELECT le.person_name, jc.title as role, le.hours
                FROM labor_entries le
                JOIN job_codes jc ON le.job_code_id = jc.id
                WHERE le.project_id = ?
                ORDER BY jc.title
            """, (proj["project_id"],))

            if people:
                people_chips = " ".join(
                    f'<span style="background:#1e293b; border:1px solid #334155; padding:3px 10px; border-radius:8px; '
                    f'font-size:0.75rem; color:#cbd5e1; margin-right:4px;">'
                    f'{p["role"]}{" — " + p["person_name"] if p["person_name"] else ""} '
                    f'<span style="color:#64748b;">({p["hours"]:.0f}h)</span></span>'
                    for p in people
                )
                st.markdown(f'<div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:4px;">{people_chips}</div>', unsafe_allow_html=True)

            # Row 3: Imagery orders summary
            img_orders = query("""
                SELECT COUNT(*) as cnt, SUM(shots_delivered) as shots,
                       SUM(charge) as total_charge, SUM(cost) as total_cost
                FROM imagery_orders WHERE project_id = ?
            """, (proj["project_id"],), fetchone=True)

            if img_orders and img_orders["cnt"] > 0:
                img_profit = (img_orders["total_charge"] or 0) - (img_orders["total_cost"] or 0)
                st.markdown(
                    f'<div style="margin-top:6px;">'
                    f'<span style="color:#a78bfa; font-size:0.72rem; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Imagery:</span> '
                    f'<span style="color:#cbd5e1; font-size:0.82rem;">{img_orders["cnt"]} orders</span>'
                    f'<span style="color:#64748b; font-size:0.82rem;"> | {img_orders["shots"] or 0} shots delivered</span>'
                    f'<span style="color:#64748b; font-size:0.82rem;"> | Profit: </span>'
                    f'<span style="color:{"#22c55e" if img_profit >= 0 else "#ef4444"}; font-size:0.82rem; font-weight:500;">${img_profit:,.0f}</span>'
                    f'</div>', unsafe_allow_html=True
                )

            # Dates
            if proj.get("start_date") and proj.get("end_date"):
                st.markdown(
                    f'<span style="color:#475569; font-size:0.75rem;">{proj["start_date"]} → {proj["end_date"]}'
                    f'{" | " + str(proj.get("days", "")) + " days" if proj.get("days") else ""}</span>',
                    unsafe_allow_html=True
                )

    st.stop()

# ============================================================
# EDIT VIEW — Single project editor
# ============================================================

# Back to list button
if st.button("← Back to Projects", key="back_to_list"):
    st.session_state["_view_mode"] = "list"
    st.session_state["_dirty"] = False
    st.session_state.pop("editing_labor", None)
    st.session_state.pop("editing_imagery", None)
    st.session_state.pop("editing_team", None)
    st.rerun()

# Re-initialize data for selected project (edit mode may have changed selector)
proj_key = current_project["id"] if current_project else "new"
if st.session_state.get("_proj_key") != proj_key:
    st.session_state["_proj_key"] = proj_key
    st.session_state["labor_data"] = _init_labor()
    st.session_state["imagery_data"] = _init_imagery()
    st.session_state["_dirty"] = False
    st.session_state.pop("editing_labor", None)
    st.session_state.pop("editing_imagery", None)
    st.session_state.pop("editing_team", None)

# --- Page Header ---
if is_new:
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h1 style="margin:0; font-size:1.8rem;">New Project</h1>
        <p style="color:#64748b; margin:4px 0 0 0; font-size:0.95rem;">Fill in the details below to create a new project</p>
    </div>
    """, unsafe_allow_html=True)
else:
    status_color = "#22c55e" if current_project["status"] == "Ongoing" else "#64748b"
    st.markdown(f"""
    <div style="margin-bottom:24px;">
        <div style="display:flex; align-items:center; gap:12px;">
            <h1 style="margin:0; font-size:1.8rem;">{current_project['report_title']}</h1>
            <span style="background:{status_color}; color:white; padding:4px 14px; border-radius:20px;
                         font-size:0.75rem; font-weight:600; letter-spacing:0.5px; text-transform:uppercase;">
                {current_project['status']}
            </span>
        </div>
        <p style="color:#64748b; margin:4px 0 0 0; font-size:0.95rem;">PWS {current_project['pws_number']}</p>
    </div>
    """, unsafe_allow_html=True)

# Unsaved changes
if st.session_state.get("_dirty"):
    st.warning("You have unsaved changes.")

# --- Project Details Section ---
with st.container(border=True):
    section_header("Project Details", "Basic project information and timeline")

    # Row 1: PWS, Report Title, Status
    col1, col2, col3 = st.columns(3)
    with col1:
        # PWS dropdown from pws_day_rate table
        pws_all_records = query("SELECT pws_number, pws_name FROM pws_day_rate ORDER BY updated_at DESC")
        pws_options = [f"{r['pws_number']} - {r['pws_name']}" if r["pws_name"] else r["pws_number"]
                       for r in pws_all_records]
        pws_numbers = [r["pws_number"] for r in pws_all_records]
        if is_new:
            pws_idx = 0
        else:
            try:
                pws_idx = pws_numbers.index(current_project["pws_number"])
            except ValueError:
                pws_idx = 0
        if pws_options:
            selected_pws_display = st.selectbox("PWS Number", pws_options, index=pws_idx, key="pws_select")
            pws = pws_numbers[pws_options.index(selected_pws_display)]
        else:
            st.warning("No PWS found. Please create a PWS first from the Projects list view.")
            pws = st.text_input("PWS Number",
                                 value="" if is_new else current_project["pws_number"])
    with col2:
        title = st.text_input("Report Title",
                               value="" if is_new else current_project["report_title"])
    with col3:
        status = st.selectbox(
            "Status", ["Ongoing", "Complete"],
            index=0 if is_new else (0 if current_project["status"] == "Ongoing" else 1),
        )

    # Row 2: Start Date, End Date, Days (with Include Weekends toggle)
    d1, d2, d3 = st.columns(3)
    with d1:
        start_date = st.date_input(
            "Start Date",
            value=date.today() if is_new else (
                datetime.strptime(current_project["start_date"], "%Y-%m-%d").date()
                if current_project and current_project["start_date"] else date.today()
            ),
        )
    with d2:
        end_date = st.date_input(
            "End Date",
            value=date.today() if is_new else (
                datetime.strptime(current_project["end_date"], "%Y-%m-%d").date()
                if current_project and current_project["end_date"] else date.today()
            ),
        )
    with d3:
        include_weekends = st.checkbox("Include Weekends", value=True, key="inc_weekends")
        auto_days = count_days(start_date, end_date, include_weekends)
        days = st.number_input("Days", min_value=0, value=auto_days,
                               help=f"Auto-calculated: {auto_days} {'(all days)' if include_weekends else '(weekdays only)'}")

    # Work Hours Breakdown based on days
    st.markdown(
        '<span style="color:#60a5fa; font-size:0.78rem; font-weight:600; text-transform:uppercase; '
        'letter-spacing:0.5px;">Work Hours Breakdown</span>',
        unsafe_allow_html=True,
    )
    wh1, wh2, wh3, wh4 = st.columns(4)
    wh1.metric("100%", f"{days * 8} hrs", help="Full-time — 8 hrs/day")
    wh2.metric("75%", f"{days * 6} hrs", help="6 hrs/day")
    wh3.metric("50%", f"{days * 4} hrs", help="Half-time — 4 hrs/day")
    wh4.metric("25%", f"{days * 2} hrs", help="Quarter-time — 2 hrs/day")

    notes = st.text_area("Notes", value="" if is_new else (current_project["notes"] or ""),
                         placeholder="Optional project notes...", height=80)

    is_daily_rate = 0  # kept for DB compatibility

# --- Project Team & Info Overview ---
if not is_new and current_project:
    with st.container(border=True):
        section_header("Project Team & Info", f"People assigned to this project and across PWS {current_project['pws_number']}")

        # This project's team
        labor_data_current = st.session_state.get("labor_data", [])
        if labor_data_current:
            st.markdown(f'<span style="color:#60a5fa; font-size:0.78rem; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">This Project — {current_project["report_title"]}</span>', unsafe_allow_html=True)

            for pi, person in enumerate(labor_data_current):
                editing_team = st.session_state.get("editing_team") == pi
                if not editing_team:
                    tc1, tc2, tc3, tc4, tc5 = st.columns([2, 2, 1, 1, 0.4])
                    tc1.markdown(f'**{person["Role"]}**')
                    tc2.text(person["Person Name"] or "—")
                    tc3.text(f'{person["Hours"]:.1f}h')
                    charge_val = 0.0 if person.get("No Charge", False) else person["Bid Rate"] * person["Hours"]
                    tc4.text(f'${charge_val:,.0f}')
                    if tc5.button("✏️", key=f"edit_team_{pi}", help="Edit person"):
                        st.session_state["editing_team"] = pi
                        st.rerun()
                else:
                    with st.container(border=True):
                        te1, te2, te3 = st.columns(3)
                        with te1:
                            team_edit_role = st.selectbox("Role", job_code_titles,
                                                          index=job_code_titles.index(person["Role"]) if person["Role"] in job_code_titles else 0,
                                                          key=f"team_role_{pi}")
                            team_edit_person = st.text_input("Person Name", value=person["Person Name"] or "", key=f"team_person_{pi}")
                        with te2:
                            team_edit_hours = st.number_input("Hours", value=float(person["Hours"]), min_value=0.0, step=1.0, key=f"team_hours_{pi}")
                            team_edit_nc = st.checkbox("No Charge", value=person.get("No Charge", False), key=f"team_nc_{pi}")
                        with te3:
                            jc_selected = job_code_map.get(team_edit_role, {})
                            team_edit_emp = st.number_input("Employee Rate", value=float(jc_selected.get("employee_rate", person["Employee Rate"])),
                                                            min_value=0.0, step=5.0, key=f"team_emp_{pi}")
                            team_edit_bid = st.number_input("Bid Rate", value=float(jc_selected.get("bid_rate", person["Bid Rate"])),
                                                            min_value=0.0, step=5.0, key=f"team_bid_{pi}")

                        tsb1, tsb2 = st.columns(2)
                        with tsb1:
                            if st.button("Save", key=f"team_save_{pi}", type="primary", use_container_width=True):
                                st.session_state["labor_data"][pi] = {
                                    "Role": team_edit_role, "Person Name": team_edit_person,
                                    "Hours": team_edit_hours, "Employee Rate": team_edit_emp,
                                    "Bid Rate": team_edit_bid, "No Charge": team_edit_nc,
                                }
                                st.session_state.pop("editing_team", None)
                                mark_dirty()
                                st.toast(f"Updated {team_edit_role} entry", icon="✅")
                                st.rerun()
                        with tsb2:
                            if st.button("Cancel", key=f"team_cancel_{pi}", use_container_width=True):
                                st.session_state.pop("editing_team", None)
                                st.rerun()
        else:
            st.caption("No personnel assigned to this project yet.")

        # PWS-wide team overview
        pws_number = current_project["pws_number"]
        pws_team = query("""
            SELECT DISTINCT le.person_name, jc.title as role, p.report_title, le.hours
            FROM labor_entries le
            JOIN job_codes jc ON le.job_code_id = jc.id
            JOIN projects p ON le.project_id = p.id
            WHERE p.pws_number = ? AND p.id != ?
            ORDER BY le.person_name, jc.title
        """, (pws_number, current_project["id"]))

        if pws_team:
            st.markdown("---")
            st.markdown(f'<span style="color:#a78bfa; font-size:0.78rem; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Other Projects Under PWS {pws_number}</span>', unsafe_allow_html=True)

            for member in pws_team:
                pw1, pw2, pw3, pw4 = st.columns([2, 2, 2, 1])
                pw1.markdown(f'**{member["role"]}**')
                pw2.text(member["person_name"] or "—")
                pw3.text(member["report_title"][:30])
                pw4.text(f'{member["hours"]:.1f}h')

# --- Tabs ---
tab_labor, tab_imagery, tab_summary = st.tabs(["Personnel", "Imagery Orders", "Summary"])

# ========================
# PERSONNEL TAB
# ========================
with tab_labor:
    section_header("Personnel Assignments", "Manage labor entries for this project")

    ppl_btn_col1, ppl_btn_col2 = st.columns([1, 3])
    with ppl_btn_col1:
        if st.button("👥 Available People", use_container_width=True, help="Pick from people on other projects"):
            available_people_dialog()

    with st.expander("Add Personnel Entry", expanded=len(st.session_state["labor_data"]) == 0):
        ac1, ac2, ac3, ac4 = st.columns([3, 2, 1, 1])
        with ac1:
            new_role = st.selectbox("Job Role", job_code_titles, key="new_labor_role")
        with ac2:
            new_person = st.text_input("Person Name (optional)", key="new_labor_person")
        with ac3:
            new_hours = st.number_input("Hours", min_value=0.0, step=1.0, value=8.0, key="new_labor_hours")
        with ac4:
            st.markdown("")
            new_no_charge = st.checkbox("No Charge", key="new_no_charge",
                                        help="Cost only - won't be billed")

        if st.button("Add Personnel", key="add_labor", type="primary"):
            jc = job_code_map[new_role]
            st.session_state["labor_data"].append({
                "Role": new_role, "Person Name": new_person,
                "Hours": new_hours, "Employee Rate": jc["employee_rate"],
                "Bid Rate": jc["bid_rate"], "No Charge": new_no_charge,
            })
            mark_dirty()
            st.rerun()

    labor_data = st.session_state["labor_data"]
    if labor_data:
        # Column headers using st.columns for perfect alignment
        lhdr = st.columns([2.2, 1.5, 0.7, 1, 1, 0.5, 0.4, 0.4])
        lhdr_style = "color:#7c8fa6; font-size:0.75rem; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;"
        for col, label in zip(lhdr, ["Role", "Person", "Hours", "Cost", "Charge", "NC", "", ""]):
            col.markdown(f'<span style="{lhdr_style}">{label}</span>', unsafe_allow_html=True)
        st.markdown('<hr style="margin:4px 0; border-color:#253348;">', unsafe_allow_html=True)

        for i, row in enumerate(labor_data):
            cost = row["Employee Rate"] * row["Hours"]
            no_charge = row.get("No Charge", False)
            charge = 0.0 if no_charge else row["Bid Rate"] * row["Hours"]
            editing = st.session_state.get("editing_labor") == i

            if not editing:
                c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([2.2, 1.5, 0.7, 1, 1, 0.5, 0.4, 0.4])
                c1.markdown(f"**{row['Role']}**")
                c2.text(row["Person Name"] or "-")
                c3.text(f"{row['Hours']:.1f}h")
                c4.text(f"${cost:,.0f}")
                if no_charge:
                    c5.markdown(f'<span style="color:#f59e0b; font-weight:500;">$0 (NC)</span>', unsafe_allow_html=True)
                else:
                    c5.text(f"${charge:,.0f}")
                if no_charge:
                    c6.markdown('<span style="background:#f59e0b22; color:#f59e0b; padding:2px 6px; border-radius:4px; font-size:0.72rem; font-weight:600;">NC</span>', unsafe_allow_html=True)
                else:
                    c6.text("")
                if c7.button("✏️", key=f"edit_labor_{i}", help="Edit"):
                    st.session_state["editing_labor"] = i
                    st.rerun()
                if c8.button("✕", key=f"del_labor_{i}", help="Remove"):
                    st.session_state["labor_data"].pop(i)
                    st.session_state.pop("editing_labor", None)
                    mark_dirty()
                    st.rerun()
            else:
                with st.container(border=True):
                    ec1, ec2, ec3 = st.columns(3)
                    with ec1:
                        edit_role = st.selectbox("Role", job_code_titles,
                                                 index=job_code_titles.index(row["Role"]) if row["Role"] in job_code_titles else 0,
                                                 key=f"edit_role_{i}")
                        edit_person = st.text_input("Person Name", value=row["Person Name"] or "", key=f"edit_person_{i}")
                    with ec2:
                        edit_hours = st.number_input("Hours", value=float(row["Hours"]), min_value=0.0, step=1.0, key=f"edit_hours_{i}")
                        edit_nc = st.checkbox("No Charge", value=no_charge, key=f"edit_nc_{i}",
                                              help="Cost only - won't be billed")
                    with ec3:
                        edit_emp = st.number_input("Employee Rate ($/hr)", value=float(row["Employee Rate"]),
                                                   min_value=0.0, step=5.0, key=f"edit_emp_{i}")
                        edit_bid = st.number_input("Bid Rate ($/hr)", value=float(row["Bid Rate"]),
                                                   min_value=0.0, step=5.0, key=f"edit_bid_{i}")

                    sb1, sb2 = st.columns(2)
                    with sb1:
                        if st.button("Save", key=f"save_edit_{i}", type="primary", use_container_width=True):
                            st.session_state["labor_data"][i] = {
                                "Role": edit_role, "Person Name": edit_person,
                                "Hours": edit_hours, "Employee Rate": edit_emp,
                                "Bid Rate": edit_bid, "No Charge": edit_nc,
                            }
                            st.session_state.pop("editing_labor", None)
                            mark_dirty()
                            st.toast(f"Updated {edit_role} entry", icon="✅")
                            st.rerun()
                    with sb2:
                        if st.button("Cancel", key=f"cancel_edit_{i}", use_container_width=True):
                            st.session_state.pop("editing_labor", None)
                            st.rerun()

        # Totals
        total_hours = sum(r["Hours"] for r in labor_data)
        total_cost = sum(r["Employee Rate"] * r["Hours"] for r in labor_data)
        total_charge = sum(
            0.0 if r.get("No Charge", False) else r["Bid Rate"] * r["Hours"]
            for r in labor_data
        )
        nc_count = sum(1 for r in labor_data if r.get("No Charge", False))
        st.markdown("---")
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Total Hours", f"{total_hours:.1f}")
        t2.metric("Labor Cost", f"${total_cost:,.2f}")
        t3.metric("Labor Charge", f"${total_charge:,.2f}")
        t4.metric("Labor Profit", f"${total_charge - total_cost:,.2f}")
        if nc_count > 0:
            st.caption(f"{nc_count} entry(ies) marked No Charge - cost incurred but not billed.")
    else:
        st.markdown("""
        <div style="text-align:center; padding:40px 20px; color:#64748b;">
            <p style="font-size:1.1rem; margin:0;">No personnel assigned yet</p>
            <p style="font-size:0.85rem; margin:8px 0 0 0;">Expand the form above to add personnel entries</p>
        </div>
        """, unsafe_allow_html=True)

# ========================
# IMAGERY ORDERS TAB
# ========================
with tab_imagery:
    section_header("Imagery Orders", "Track satellite imagery orders and costs")

    with st.expander("Add Imagery Order", expanded=len(st.session_state["imagery_data"]) == 0):
        selected_product = st.selectbox(
            "Select from Catalog", ["-- Manual Entry --"] + list(catalog_options.keys()),
            key="catalog_select",
        )

        ic1, ic2, ic3 = st.columns(3)
        with ic1:
            if selected_product == "-- Manual Entry --":
                img_provider = st.text_input("Provider", key="manual_provider")
                img_product = st.text_input("Product", key="manual_product")
            else:
                cat = catalog_options[selected_product]
                img_provider = cat["provider"]
                img_product = cat["description"]
                st.text_input("Provider", value=img_provider, disabled=True, key="show_prov")
                st.text_input("Product", value=img_product, disabled=True, key="show_prod")
        with ic2:
            img_date = st.date_input("Order Date", value=date.today(), key="img_date")
            img_aoi = st.text_input("AOI", key="img_aoi")
        with ic3:
            img_status = st.selectbox("Order Status", ORDER_STATUSES, key="img_status")

        # Shots & pricing
        st.markdown("")
        sh1, sh2, sh3, sh4 = st.columns(4)
        with sh1:
            img_shots_req = st.number_input("Shots Requested", min_value=0, value=0, key="img_shots_req")
        with sh2:
            img_shots_del = st.number_input("Shots Delivered", min_value=0, value=0, key="img_shots_del")

        if selected_product != "-- Manual Entry --":
            default_cost_ps = float(cat["list_price"])
            default_charge_ps = float(cat["sh_price"])
        else:
            default_cost_ps = 0.0
            default_charge_ps = 0.0

        # Use dynamic key so value updates when catalog selection changes
        cost_key = f"img_cost_ps_{selected_product}"
        charge_key = f"img_charge_ps_{selected_product}"
        charge_unlocked = st.session_state.get("_charge_unlocked", False)
        with sh3:
            img_cost_ps = st.number_input("Cost / Shot ($)", value=default_cost_ps,
                                          disabled=(selected_product != "-- Manual Entry --"),
                                          key=cost_key,
                                          help="Auto-populated from catalog")
        with sh4:
            charge_disabled = not charge_unlocked and (selected_product != "-- Manual Entry --")
            img_charge_ps = st.number_input("Charge / Shot ($)", value=default_charge_ps,
                                            disabled=charge_disabled,
                                            key=charge_key,
                                            help="Locked — click 🔒 to unlock" if charge_disabled else "Charge field unlocked")
            if charge_disabled:
                if st.button("🔒 Unlock", key="unlock_charge_btn", help="Enter password to edit charge"):
                    unlock_charge_dialog()
            else:
                if selected_product != "-- Manual Entry --":
                    st.caption("🔓 Unlocked")

        # Live totals preview
        live_total_cost = img_cost_ps * img_shots_del
        live_total_charge = img_charge_ps * img_shots_del
        live_profit = live_total_charge - live_total_cost
        if img_shots_del > 0 or img_shots_req > 0:
            pv1, pv2, pv3 = st.columns(3)
            pv1.markdown(f"**Total Cost:** ${live_total_cost:,.2f}")
            pv2.markdown(f"**Total Charge:** ${live_total_charge:,.2f}")
            profit_color = "#22c55e" if live_profit >= 0 else "#ef4444"
            pv3.markdown(f'**Profit:** <span style="color:{profit_color}">${live_profit:,.2f}</span>', unsafe_allow_html=True)

        if st.button("Add Order", key="add_imagery", type="primary"):
            if selected_product == "-- Manual Entry --" and (not img_provider or not img_product):
                st.error("Provider and Product are required for manual entries.")
            else:
                st.session_state["imagery_data"].append({
                    "Provider": img_provider, "Product": img_product,
                    "Date": str(img_date), "Status": img_status,
                    "AOI": img_aoi,
                    "Shots Requested": img_shots_req,
                    "Shots Delivered": img_shots_del,
                    "Cost Per Shot": img_cost_ps,
                    "Charge Per Shot": img_charge_ps,
                })
                mark_dirty()
                st.rerun()

    imagery_data = st.session_state["imagery_data"]
    if imagery_data:
        status_colors = {
            "Requested": "#f59e0b", "Approved": "#06b6d4", "Ordered": "#3b82f6",
            "Collected": "#8b5cf6", "Delivered": "#22c55e",
        }

        # Column headers using st.columns for perfect alignment
        hdr = st.columns([1.5, 2, 1, 0.6, 0.6, 0.8, 0.8, 0.8, 0.35, 0.35])
        header_style = "color:#7c8fa6; font-size:0.72rem; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;"
        for col, label in zip(hdr, ["Provider", "Product", "Status", "Req", "Del", "Cost", "Charge", "Profit", "", ""]):
            col.markdown(f'<span style="{header_style}">{label}</span>', unsafe_allow_html=True)
        st.markdown('<hr style="margin:4px 0; border-color:#253348;">', unsafe_allow_html=True)

        for i, row in enumerate(imagery_data):
            shots_req = row.get("Shots Requested", 0)
            shots_del = row.get("Shots Delivered", 0)
            cps = row.get("Cost Per Shot", 0)
            chps = row.get("Charge Per Shot", 0)
            total_cost = cps * shots_del
            total_charge = chps * shots_del
            row_profit = total_charge - total_cost
            editing_img = st.session_state.get("editing_imagery") == i

            if not editing_img:
                c1, c2, c3, c4, c5, c6, c7, c8, c9, c10 = st.columns([1.5, 2, 1, 0.6, 0.6, 0.8, 0.8, 0.8, 0.35, 0.35])
                c1.markdown(f"**{row['Provider']}**")
                c2.text(row["Product"][:30])
                color = status_colors.get(row["Status"], "#94a3b8")
                c3.markdown(f'<span style="background:{color}22; color:{color}; padding:4px 10px; border-radius:6px; font-size:0.78rem; font-weight:600;">{row["Status"]}</span>', unsafe_allow_html=True)
                c4.text(f"{shots_req}")
                c5.text(f"{shots_del}")
                c6.text(f"${total_cost:,.0f}")
                c7.text(f"${total_charge:,.0f}")
                profit_color = "#22c55e" if row_profit >= 0 else "#ef4444"
                c8.markdown(f'<span style="color:{profit_color}; font-weight:500;">${row_profit:,.0f}</span>', unsafe_allow_html=True)
                if c9.button("✏️", key=f"edit_img_{i}", help="Edit"):
                    st.session_state["editing_imagery"] = i
                    st.rerun()
                if c10.button("✕", key=f"del_img_{i}", help="Remove"):
                    st.session_state["imagery_data"].pop(i)
                    st.session_state.pop("editing_imagery", None)
                    mark_dirty()
                    st.rerun()
            else:
                # Inline edit form
                with st.container(border=True):
                    ei1, ei2, ei3 = st.columns(3)
                    with ei1:
                        edit_img_provider = st.text_input("Provider", value=row["Provider"], key=f"edit_img_prov_{i}")
                        edit_img_product = st.text_input("Product", value=row["Product"], key=f"edit_img_prod_{i}")
                    with ei2:
                        edit_img_status = st.selectbox("Status", ORDER_STATUSES,
                                                        index=ORDER_STATUSES.index(row["Status"]) if row["Status"] in ORDER_STATUSES else 0,
                                                        key=f"edit_img_status_{i}")
                        edit_img_aoi = st.text_input("AOI", value=row.get("AOI", "") or "", key=f"edit_img_aoi_{i}")
                    with ei3:
                        edit_img_date = st.text_input("Order Date", value=row.get("Date", "") or "", key=f"edit_img_date_{i}")

                    es1, es2, es3, es4 = st.columns(4)
                    with es1:
                        edit_shots_req = st.number_input("Shots Requested", value=int(shots_req), min_value=0, key=f"edit_img_sreq_{i}")
                    with es2:
                        edit_shots_del = st.number_input("Shots Delivered", value=int(shots_del), min_value=0, key=f"edit_img_sdel_{i}")
                    with es3:
                        edit_cps = st.number_input("Cost / Shot ($)", value=float(cps), min_value=0.0, step=10.0, key=f"edit_img_cps_{i}")
                    with es4:
                        edit_charge_unlocked = st.session_state.get("_charge_unlocked", False)
                        edit_chps = st.number_input("Charge / Shot ($)", value=float(chps), min_value=0.0, step=10.0,
                                                     disabled=not edit_charge_unlocked, key=f"edit_img_chps_{i}")
                        if not edit_charge_unlocked:
                            if st.button("🔒 Unlock", key=f"unlock_charge_edit_{i}", help="Enter password to edit charge"):
                                unlock_charge_dialog()
                        else:
                            st.caption("🔓 Unlocked")

                    # Live preview
                    preview_cost = edit_cps * edit_shots_del
                    preview_charge = edit_chps * edit_shots_del
                    preview_profit = preview_charge - preview_cost
                    pr_color = "#22c55e" if preview_profit >= 0 else "#ef4444"
                    pv1, pv2, pv3 = st.columns(3)
                    pv1.markdown(f"**Total Cost:** ${preview_cost:,.2f}")
                    pv2.markdown(f"**Total Charge:** ${preview_charge:,.2f}")
                    pv3.markdown(f'**Profit:** <span style="color:{pr_color}">${preview_profit:,.2f}</span>', unsafe_allow_html=True)

                    sb1, sb2 = st.columns(2)
                    with sb1:
                        if st.button("Save", key=f"save_img_edit_{i}", type="primary", use_container_width=True):
                            st.session_state["_img_edit_payload"] = {
                                "idx": i,
                                "data": {
                                    "Provider": edit_img_provider, "Product": edit_img_product,
                                    "Date": edit_img_date, "Status": edit_img_status,
                                    "AOI": edit_img_aoi,
                                    "Shots Requested": edit_shots_req,
                                    "Shots Delivered": edit_shots_del,
                                    "Cost Per Shot": edit_cps,
                                    "Charge Per Shot": edit_chps,
                                },
                            }
                            imagery_edit_dialog()
                    with sb2:
                        if st.button("Cancel", key=f"cancel_img_edit_{i}", use_container_width=True):
                            st.session_state.pop("editing_imagery", None)
                            st.rerun()

        # Bulk status update
        st.markdown("---")
        with st.container(border=True):
            section_header("Bulk Status Update", "Update multiple orders at once")
            us1, us2, us3 = st.columns([3, 2, 1])
            with us1:
                bulk_select = st.multiselect(
                    "Select Orders", range(len(imagery_data)),
                    format_func=lambda i: f"{imagery_data[i]['Provider']} - {imagery_data[i]['Product'][:30]}",
                    key="bulk_status_select",
                )
            with us2:
                new_status = st.selectbox("New Status", ORDER_STATUSES, key="new_order_status")
            with us3:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("Update Selected", key="update_status", type="primary",
                             disabled=len(bulk_select) == 0, use_container_width=True):
                    for idx in bulk_select:
                        st.session_state["imagery_data"][idx]["Status"] = new_status
                    mark_dirty()
                    st.toast(f"Updated {len(bulk_select)} order(s) to {new_status}", icon="✅")
                    st.rerun()

            ba1, ba2 = st.columns(2)
            with ba1:
                mark_all_status = st.selectbox("Mark ALL orders as:", ORDER_STATUSES, key="mark_all_status")
            with ba2:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("Apply to All Orders", key="mark_all_btn", use_container_width=True):
                    for i in range(len(imagery_data)):
                        st.session_state["imagery_data"][i]["Status"] = mark_all_status
                    mark_dirty()
                    st.toast(f"All {len(imagery_data)} orders marked as {mark_all_status}", icon="✅")
                    st.rerun()

        st.markdown("")
        img_total_cost = sum(r.get("Cost Per Shot", 0) * r.get("Shots Delivered", 0) for r in imagery_data)
        img_total_charge = sum(r.get("Charge Per Shot", 0) * r.get("Shots Delivered", 0) for r in imagery_data)
        total_shots_req = sum(r.get("Shots Requested", 0) for r in imagery_data)
        total_shots_del = sum(r.get("Shots Delivered", 0) for r in imagery_data)
        t1, t2, t3, t4, t5 = st.columns(5)
        t1.metric("Orders", len(imagery_data))
        t2.metric("Shots", f"{total_shots_del} / {total_shots_req} req")
        t3.metric("Imagery Cost", f"${img_total_cost:,.2f}")
        t4.metric("Imagery Charge", f"${img_total_charge:,.2f}")
        t5.metric("Imagery Profit", f"${img_total_charge - img_total_cost:,.2f}")
    else:
        st.markdown("""
        <div style="text-align:center; padding:40px 20px; color:#64748b;">
            <p style="font-size:1.1rem; margin:0;">No imagery orders yet</p>
            <p style="font-size:0.85rem; margin:8px 0 0 0;">Expand the form above to add orders</p>
        </div>
        """, unsafe_allow_html=True)

# ========================
# PROJECT SUMMARY TAB
# ========================
with tab_summary:
    section_header("Financial Summary", "Overview of all project costs and revenue")

    labor_cost = sum(r["Employee Rate"] * r["Hours"] for r in st.session_state["labor_data"])
    labor_charge = sum(
        0.0 if r.get("No Charge", False) else r["Bid Rate"] * r["Hours"]
        for r in st.session_state["labor_data"]
    )
    img_cost_total = sum(r.get("Cost Per Shot", 0) * r.get("Shots Delivered", 0) for r in st.session_state["imagery_data"])
    img_charge_total = sum(r.get("Charge Per Shot", 0) * r.get("Shots Delivered", 0) for r in st.session_state["imagery_data"])

    grand_cost = labor_cost + img_cost_total
    grand_charge = labor_charge + img_charge_total
    grand_profit = grand_charge - grand_cost
    margin = (grand_profit / grand_charge * 100) if grand_charge > 0 else 0

    # Grand totals at top
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Total Cost", f"${grand_cost:,.2f}")
    g2.metric("Total Charge", f"${grand_charge:,.2f}")
    g3.metric("Total Profit", f"${grand_profit:,.2f}",
              delta=f"{margin:.1f}% margin" if grand_charge > 0 else None)
    # Margin indicator
    if grand_charge > 0:
        if margin >= 20:
            g4.metric("Margin Health", f"{margin:.1f}%", delta="Healthy")
        elif margin >= 10:
            g4.metric("Margin Health", f"{margin:.1f}%", delta="Moderate", delta_color="off")
        else:
            g4.metric("Margin Health", f"{margin:.1f}%", delta="Low", delta_color="inverse")

    st.markdown("")

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("**Labor**")
            l1, l2, l3 = st.columns(3)
            l1.metric("Cost", f"${labor_cost:,.2f}")
            l2.metric("Charge", f"${labor_charge:,.2f}")
            l3.metric("Profit", f"${labor_charge - labor_cost:,.2f}")
    with col2:
        with st.container(border=True):
            st.markdown("**Imagery**")
            i1, i2, i3 = st.columns(3)
            i1.metric("Cost", f"${img_cost_total:,.2f}")
            i2.metric("Charge", f"${img_charge_total:,.2f}")
            i3.metric("Profit", f"${img_charge_total - img_cost_total:,.2f}")

    if margin > 0 and margin < 10:
        st.warning(f"Low margin alert: {margin:.1f}% is below 10%")

    # Export
    st.markdown("---")
    if st.session_state["labor_data"] or st.session_state["imagery_data"]:
        export_data = []
        for r in st.session_state["labor_data"]:
            nc = r.get("No Charge", False)
            export_data.append({
                "Type": "Labor", "Item": r["Role"], "Person": r["Person Name"],
                "Hours": r["Hours"], "Cost": r["Employee Rate"] * r["Hours"],
                "Charge": 0.0 if nc else r["Bid Rate"] * r["Hours"],
                "No Charge": "Yes" if nc else "No",
            })
        for r in st.session_state["imagery_data"]:
            s_del = r.get("Shots Delivered", 0)
            export_data.append({
                "Type": "Imagery", "Item": f"{r['Provider']} - {r['Product']}",
                "Person": f"{r.get('Shots Requested', 0)} req / {s_del} del",
                "Hours": "", "Cost": r.get("Cost Per Shot", 0) * s_del,
                "Charge": r.get("Charge Per Shot", 0) * s_del,
                "No Charge": "No",
            })
        export_df = pd.DataFrame(export_data)
        csv = export_df.to_csv(index=False)
        st.download_button(
            "Export Project Data (CSV)", csv,
            file_name=f"{pws}_{title.replace(' ', '_')}_data.csv" if pws and title else "project_data.csv",
            mime="text/csv",
        )

# --- Action Bar ---
st.markdown("---")
st.markdown("""
<div style="padding:4px 0 8px 0;">
    <span style="color:#7c8fa6; font-size:0.75rem; font-weight:600; text-transform:uppercase; letter-spacing:0.8px;">Actions</span>
</div>
""", unsafe_allow_html=True)

save_col, action_col = st.columns([1, 1])

with save_col:
    # Handle the actual save after dialog confirmation
    if st.session_state.get("_do_save"):
        sd = st.session_state.pop("_save_payload", {})
        st.session_state.pop("_do_save", None)
        if sd:
            conn = get_connection()
            try:
                if sd["is_new"]:
                    cur = conn.execute(
                        """INSERT INTO projects (pws_number, report_title, start_date, end_date, status, notes, days, is_daily_rate)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (sd["pws"], sd["title"], sd["start_date"], sd["end_date"],
                         sd["status"], sd["notes"], sd["days"], sd["is_daily_rate"]),
                    )
                    project_id = cur.lastrowid
                else:
                    project_id = sd["project_id"]
                    conn.execute(
                        """UPDATE projects SET pws_number=?, report_title=?, start_date=?, end_date=?,
                           status=?, notes=?, days=?, is_daily_rate=? WHERE id=?""",
                        (sd["pws"], sd["title"], sd["start_date"], sd["end_date"],
                         sd["status"], sd["notes"], sd["days"], sd["is_daily_rate"], project_id),
                    )
                    conn.execute("DELETE FROM labor_entries WHERE project_id = ?", (project_id,))
                    conn.execute("DELETE FROM imagery_orders WHERE project_id = ?", (project_id,))

                for row in st.session_state["labor_data"]:
                    jc = job_code_map.get(row["Role"])
                    if jc:
                        nc = row.get("No Charge", False)
                        conn.execute(
                            """INSERT INTO labor_entries (project_id, job_code_id, person_name, hours, employee_rate, bid_rate)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (project_id, jc["id"], row["Person Name"] or None, row["Hours"],
                             row["Employee Rate"], 0.0 if nc else row["Bid Rate"]),
                        )

                for row in st.session_state["imagery_data"]:
                    catalog_key = f"{row['Provider']} - {row['Product']}"
                    cat_entry = catalog_options.get(catalog_key)
                    catalog_id = cat_entry["id"] if cat_entry else None
                    s_del = row.get("Shots Delivered", 0)
                    cps = row.get("Cost Per Shot", 0)
                    chps = row.get("Charge Per Shot", 0)
                    conn.execute(
                        """INSERT INTO imagery_orders (project_id, catalog_id, provider, product, order_date,
                           order_status, aoi, shots_requested, shots_delivered,
                           cost_per_shot, charge_per_shot, cost, charge)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (project_id, catalog_id, row["Provider"], row["Product"],
                         row["Date"] or None, row["Status"],
                         row["AOI"] or None, row.get("Shots Requested", 0), s_del,
                         cps, chps, cps * s_del, chps * s_del),
                    )

                conn.commit()
                # Clear editing states and dirty flag
                st.session_state["_dirty"] = False
                st.session_state.pop("editing_labor", None)
                st.session_state.pop("editing_imagery", None)
                st.session_state.pop("editing_team", None)
                st.session_state.pop("confirm_delete", None)
                # Re-lock charge field after save
                st.session_state.pop("_charge_unlocked", None)
                # Go back to list view after save
                st.session_state.pop("_proj_key", None)
                st.session_state["_view_mode"] = "list"
                st.toast(f"Project '{sd['title']}' saved!", icon="✅")
                st.rerun()
            except Exception as e:
                conn.rollback()
                st.error(f"Error saving project: {e}")
            finally:
                conn.close()

    if st.button("Save Project", type="primary", use_container_width=True):
        if not pws or not title:
            st.error("PWS Number and Report Title are required.")
        elif end_date < start_date:
            st.error("End Date cannot be before Start Date.")
        else:
            st.session_state["_save_payload"] = {
                "pws": pws, "title": title,
                "start_date": str(start_date), "end_date": str(end_date),
                "status": status, "notes": notes, "days": days,
                "is_daily_rate": int(is_daily_rate),
                "is_new": is_new,
                "project_id": current_project["id"] if current_project else None,
            }
            save_dialog()

with action_col:
    if not is_new and current_project:
        btn_dup, btn_del = st.columns(2)
        with btn_dup:
            if st.button("Duplicate", use_container_width=True, help="Clone this project"):
                conn = get_connection()
                try:
                    cp = current_project
                    cur = conn.execute(
                        """INSERT INTO projects (pws_number, report_title, start_date, end_date, status, notes, days, is_daily_rate)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (cp["pws_number"], cp["report_title"] + " (Copy)", cp["start_date"], cp["end_date"],
                         cp["status"], cp["notes"], cp["days"], cp.get("is_daily_rate", 0)),
                    )
                    new_id = cur.lastrowid
                    for row in st.session_state["labor_data"]:
                        jc = job_code_map.get(row["Role"])
                        if jc:
                            nc = row.get("No Charge", False)
                            conn.execute(
                                """INSERT INTO labor_entries (project_id, job_code_id, person_name, hours, employee_rate, bid_rate)
                                   VALUES (?, ?, ?, ?, ?, ?)""",
                                (new_id, jc["id"], row["Person Name"] or None, row["Hours"],
                                 row["Employee Rate"], 0.0 if nc else row["Bid Rate"]),
                            )
                    for row in st.session_state["imagery_data"]:
                        catalog_key = f"{row['Provider']} - {row['Product']}"
                        cat_entry = catalog_options.get(catalog_key)
                        catalog_id = cat_entry["id"] if cat_entry else None
                        s_del = row.get("Shots Delivered", 0) or 0
                        cps = row.get("Cost Per Shot", 0) or 0
                        chps = row.get("Charge Per Shot", 0) or 0
                        conn.execute(
                            """INSERT INTO imagery_orders (project_id, catalog_id, provider, product, order_date,
                               order_status, aoi, shots_requested, shots_delivered,
                               cost_per_shot, charge_per_shot, cost, charge)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (new_id, catalog_id, row["Provider"], row["Product"],
                             row["Date"] or None, row["Status"],
                             row["AOI"] or None, row.get("Shots Requested", 0) or 0, s_del,
                             cps, chps, cps * s_del, chps * s_del),
                        )
                    conn.commit()
                    st.session_state["_reset_form"] = True
                    st.session_state["_view_mode"] = "list"
                    st.toast(f"Duplicated as '{cp['report_title']} (Copy)'!", icon="📋")
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error duplicating: {e}")
                finally:
                    conn.close()
        with btn_del:
            if st.button("Delete", use_container_width=True, type="secondary"):
                st.session_state["confirm_delete"] = True

        if st.session_state.get("confirm_delete"):
            st.warning(f"Delete **{current_project['report_title']}**? This cannot be undone.")
            dc1, dc2 = st.columns(2)
            if dc1.button("Yes, Delete", key="confirm_del", type="primary"):
                execute("DELETE FROM projects WHERE id = ?", (current_project["id"],))
                st.session_state.pop("confirm_delete", None)
                st.session_state["_dirty"] = False
                st.session_state["_view_mode"] = "list"
                st.toast("Project deleted.", icon="🗑️")
                st.rerun()
            if dc2.button("Cancel", key="cancel_del"):
                st.session_state.pop("confirm_delete", None)
                st.rerun()
