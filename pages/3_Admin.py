"""
Admin Panel — user management, session history, activity log.
Only accessible to users with role = 'admin'.
"""
import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auth.auth_ui import require_login, sidebar_user_info
from auth.auth_db import (
    get_all_users, create_user, update_user, delete_user,
    get_sessions, get_activity, log_activity, verify_password,
)
from auth.backup import (
    create_backup, list_backups, restore_tracker_from_backup,
    restore_tracker_from_upload, delete_backup,
)

require_login(tool="admin")

# Load shared CSS
css_path = Path(__file__).parent.parent / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

user = st.session_state.get("auth_user", {})
sidebar_user_info()

if user.get("role") != "admin":
    st.error("Access denied. Admin only.")
    st.stop()

log_activity(user["username"], "admin", "open", "Opened Admin Panel")

# ── Admin-specific CSS ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

/* Badge styles */
.adm-badge {
    display: inline-flex; align-items: center; gap: 0.25rem;
    padding: 0.15rem 0.6rem; border-radius: 100px;
    font-size: 0.6875rem; font-weight: 600; letter-spacing: 0.02em;
}
.adm-badge-admin { background: rgba(192,168,126,0.12); color: #c0a87e; border: 1px solid rgba(192,168,126,0.15); }
.adm-badge-user  { background: rgba(79,124,255,0.12); color: #4f7cff; border: 1px solid rgba(79,124,255,0.15); }
.adm-badge-both  { background: rgba(167,139,250,0.1); color: #a78bfa; border: 1px solid rgba(167,139,250,0.15); }
.adm-badge-tracker { background: rgba(79,124,255,0.12); color: #4f7cff; border: 1px solid rgba(79,124,255,0.15); }
.adm-badge-hermes { background: rgba(45,212,191,0.1); color: #2dd4bf; border: 1px solid rgba(45,212,191,0.15); }
.adm-badge-active { background: rgba(52,211,153,0.1); color: #34d399; border: 1px solid rgba(52,211,153,0.15); }
.adm-badge-inactive { background: rgba(248,113,113,0.08); color: #f87171; border: 1px solid rgba(248,113,113,0.12); }

/* User cell with avatar */
.adm-user-cell { display: flex; align-items: center; gap: 0.625rem; }
.adm-avatar {
    width: 32px; height: 32px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.6875rem; font-weight: 700; flex-shrink: 0;
}
.adm-avatar-admin {
    background: linear-gradient(135deg, rgba(192,168,126,0.2), rgba(192,168,126,0.08));
    border: 1px solid rgba(192,168,126,0.2); color: #c0a87e;
}
.adm-avatar-user {
    background: linear-gradient(135deg, rgba(79,124,255,0.15), rgba(79,124,255,0.05));
    border: 1px solid rgba(79,124,255,0.2); color: #4f7cff;
}
.adm-user-name { font-weight: 600; color: #f1f1f4; font-size: 0.8125rem; }
.adm-user-sub  { font-size: 0.6875rem; color: #5a5e72; font-family: 'JetBrains Mono', monospace; }

/* Activity tool dot */
.adm-tool-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; margin-right: 0.375rem; }
.adm-tool-dot.tracker { background: #4f7cff; }
.adm-tool-dot.hermes  { background: #2dd4bf; }
.adm-tool-dot.admin   { background: #c0a87e; }
.adm-tool-dot.app     { background: #a78bfa; }

/* Stat boxes */
.adm-stats { display: flex; gap: 1.25rem; }
.adm-stat {
    text-align: center; padding: 0.5rem 1.25rem;
    background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
}
.adm-stat-val { font-size: 1.25rem; font-weight: 700; color: #f1f1f4; font-family: 'JetBrains Mono', monospace; }
.adm-stat-lbl { font-size: 0.6rem; color: #5a5e72; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 0.125rem; }

/* Mono text */
.adm-mono { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #5a5e72; }

/* Table header row */
.adm-th {
    color: #5a5e72 !important; font-size: 0.6875rem !important; font-weight: 600 !important;
    text-transform: uppercase !important; letter-spacing: 0.08em !important;
}

/* Row separator */
.adm-row-sep { border-bottom: 1px solid rgba(255,255,255,0.025); padding: 0.5rem 0; }

/* You badge */
.adm-you { font-size: 0.625rem; color: #3d4155; font-style: italic; }

/* Status dot inline */
.adm-status-dot {
    width: 6px; height: 6px; border-radius: 50%; display: inline-block; margin-right: 0.25rem;
}
.adm-status-dot.green { background: #34d399; box-shadow: 0 0 6px rgba(52,211,153,0.4); }

/* Detail text */
.adm-detail { font-size: 0.75rem; color: #5a5e72; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Action text */
.adm-action { color: #f1f1f4; font-weight: 500; font-size: 0.8125rem; }
</style>
""", unsafe_allow_html=True)

# ── Header with stats ──────────────────────────────────────────
all_users = get_all_users()
all_sessions = get_sessions(limit=500)
all_activity = get_activity(limit=500)

from datetime import datetime
today_str = datetime.now().strftime("%Y-%m-%d")
sessions_today = sum(1 for s in all_sessions if s["login_at"] and s["login_at"].startswith(today_str))

hdr1, hdr2 = st.columns([2, 1.5])
with hdr1:
    st.markdown(
        '<h2 style="font-family:\'Playfair Display\',Georgia,serif;font-weight:600;color:#f1f1f4;margin-bottom:0;">'
        'Admin <span style="color:#c0a87e;">Panel</span></h2>',
        unsafe_allow_html=True,
    )
with hdr2:
    st.markdown(f"""
    <div class="adm-stats" style="justify-content:flex-end;">
        <div class="adm-stat"><div class="adm-stat-val">{len(all_users)}</div><div class="adm-stat-lbl">Total Users</div></div>
        <div class="adm-stat"><div class="adm-stat-val">1</div><div class="adm-stat-lbl">Online Now</div></div>
        <div class="adm-stat"><div class="adm-stat-val">{sessions_today}</div><div class="adm-stat-lbl">Sessions Today</div></div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")

# ── Tabs ───────────────────────────────────────────────────────
tab_users, tab_sessions, tab_activity, tab_backups, tab_password = st.tabs([
    f"👤 Users  ({len(all_users)})",
    f"🕐 Login History  ({len(all_sessions)})",
    f"⚡ Activity Log  ({len(all_activity)})",
    "💾 Backup & Restore",
    "🔑 Change Password",
])


def _user_avatar_html(u):
    initial = u["name"][0].upper() if u.get("name") else "?"
    cls = "adm-avatar-admin" if u["role"] == "admin" else "adm-avatar-user"
    return f'<div class="adm-avatar {cls}">{initial}</div>'


def _role_badge(role):
    cls = "adm-badge-admin" if role == "admin" else "adm-badge-user"
    return f'<span class="adm-badge {cls}">{role.capitalize()}</span>'


def _access_badge(access):
    label_map = {"all": "All Tools", "both": "All Tools", "hermes_daedalus": "Hermes + Daedalus",
                 "tracker": "Tracker", "hermes": "Hermes", "daedalus": "Daedalus"}
    cls_map = {"all": "adm-badge-both", "both": "adm-badge-both", "hermes_daedalus": "adm-badge-hermes"}
    cls = cls_map.get(access, "adm-badge-both")
    label = label_map.get(access, access.capitalize())
    return f'<span class="adm-badge {cls}">{label}</span>'


def _status_badge(is_active):
    if is_active:
        return '<span class="adm-badge adm-badge-active"><span class="adm-status-dot green"></span>Active</span>'
    return '<span class="adm-badge adm-badge-inactive">Inactive</span>'


# ════════════════════════════════════════
# USERS TAB
# ════════════════════════════════════════
with tab_users:
    with st.expander("➕ Add New User", expanded=False):
        nu1, nu2 = st.columns(2)
        with nu1:
            new_uname = st.text_input("Username", key="nu_username")
            new_name  = st.text_input("Display Name", key="nu_name")
            new_pass  = st.text_input("Password", type="password", key="nu_pass")
        with nu2:
            new_role   = st.selectbox("Role", ["user", "admin"], key="nu_role")
            new_access = st.selectbox("Tool Access", ["all", "hermes_daedalus"],
                                     format_func=lambda x: {"all": "All Tools", "hermes_daedalus": "Hermes + Daedalus"}.get(x, x),
                                     key="nu_access")
        if st.button("Create User", type="primary", key="nu_create"):
            if not new_uname or not new_name or not new_pass:
                st.error("Fill in all fields.")
            else:
                ok, msg = create_user(new_uname, new_name, new_pass, new_role, new_access)
                if ok:
                    st.toast(f"User '{new_uname}' created", icon="✅")
                    log_activity(user["username"], "admin", "create_user", new_uname)
                    st.rerun()
                else:
                    st.error(msg)

    st.markdown("")

    if not all_users:
        st.caption("No users found.")
    else:
        # Table header
        hc = st.columns([2, 1, 1.2, 1, 1.2, 1])
        for col, label in zip(hc, ["User", "Role", "Tool Access", "Status", "Last Active", "Actions"]):
            col.markdown(f'<span class="adm-th">{label}</span>', unsafe_allow_html=True)
        st.markdown('<hr style="margin:2px 0;border-color:rgba(255,255,255,0.04);">', unsafe_allow_html=True)

        for u in all_users:
            is_self = u["username"] == user["username"]
            editing = st.session_state.get("editing_user") == u["username"]

            if not editing:
                rc = st.columns([2, 1, 1.2, 1, 1.2, 1])
                # User cell with avatar
                rc[0].markdown(
                    f'<div class="adm-user-cell">{_user_avatar_html(u)}'
                    f'<div><div class="adm-user-name">{u["name"]}</div>'
                    f'<div class="adm-user-sub">{u["username"]}</div></div></div>',
                    unsafe_allow_html=True,
                )
                rc[1].markdown(_role_badge(u["role"]), unsafe_allow_html=True)
                rc[2].markdown(_access_badge(u["tool_access"]), unsafe_allow_html=True)
                rc[3].markdown(_status_badge(u["is_active"]), unsafe_allow_html=True)
                last = u.get("last_login", "—") or "—"
                if last != "—":
                    last = last[:16]
                rc[4].markdown(f'<span class="adm-mono">{last}</span>', unsafe_allow_html=True)

                # Actions
                with rc[5]:
                    ac1, ac2 = st.columns(2)
                    if ac1.button("✏️", key=f"edit_u_{u['username']}", help="Edit"):
                        st.session_state["editing_user"] = u["username"]
                        st.rerun()
                    if not is_self:
                        if ac2.button("🗑️", key=f"del_u_{u['username']}", help="Delete"):
                            delete_user(u["username"])
                            log_activity(user["username"], "admin", "delete_user", u["username"])
                            st.toast(f"Deleted {u['username']}", icon="🗑️")
                            st.rerun()
                    else:
                        ac2.markdown('<span class="adm-you">you</span>', unsafe_allow_html=True)

                st.markdown('<div style="border-bottom:1px solid rgba(255,255,255,0.025);"></div>', unsafe_allow_html=True)
            else:
                with st.container(border=True):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_name   = st.text_input("Display Name", value=u["name"], key=f"eu_name_{u['username']}")
                        e_role   = st.selectbox("Role", ["user", "admin"],
                                                index=0 if u["role"] == "user" else 1,
                                                key=f"eu_role_{u['username']}")
                    with ec2:
                        access_options = ["all", "hermes_daedalus"]
                        access_labels = {"all": "All Tools", "hermes_daedalus": "Hermes + Daedalus"}
                        # Map legacy values
                        current_access = u["tool_access"]
                        if current_access == "both":
                            current_access = "all"
                        if current_access not in access_options:
                            current_access = "all"
                        e_access = st.selectbox("Tool Access", access_options,
                                                index=access_options.index(current_access),
                                                format_func=lambda x: access_labels.get(x, x),
                                                key=f"eu_access_{u['username']}")
                        e_active = st.checkbox("Active", value=bool(u["is_active"]), key=f"eu_active_{u['username']}")
                    e_pass = st.text_input("New Password (leave blank to keep)", type="password",
                                           key=f"eu_pass_{u['username']}")
                    sb1, sb2 = st.columns(2)
                    if sb1.button("Save", type="primary", use_container_width=True, key=f"eu_save_{u['username']}"):
                        update_user(
                            u["username"],
                            name=e_name, role=e_role, tool_access=e_access,
                            is_active=int(e_active), password=e_pass if e_pass else None
                        )
                        log_activity(user["username"], "admin", "edit_user", u["username"])
                        st.session_state.pop("editing_user", None)
                        st.toast(f"Updated {u['username']}", icon="✅")
                        st.rerun()
                    if sb2.button("Cancel", use_container_width=True, key=f"eu_cancel_{u['username']}"):
                        st.session_state.pop("editing_user", None)
                        st.rerun()


# ════════════════════════════════════════
# LOGIN HISTORY TAB
# ════════════════════════════════════════
with tab_sessions:
    filter_col, _ = st.columns([1, 3])
    unames = ["All"] + sorted({u["username"] for u in all_users})
    filter_user = filter_col.selectbox("Filter by user", unames, key="sess_filter", label_visibility="collapsed")

    sessions = all_sessions
    if filter_user != "All":
        sessions = [s for s in sessions if s["username"] == filter_user]

    if not sessions:
        st.caption("No sessions recorded yet.")
    else:
        # Table header
        shc = st.columns([1.5, 2, 1, 1.2, 1.2])
        for col, label in zip(shc, ["User", "Login Time", "Status", "Duration", "IP Address"]):
            col.markdown(f'<span class="adm-th">{label}</span>', unsafe_allow_html=True)
        st.markdown('<hr style="margin:2px 0;border-color:rgba(255,255,255,0.04);">', unsafe_allow_html=True)

        page_size = 10
        total_pages = max(1, (len(sessions) + page_size - 1) // page_size)
        page_key = "sess_page"
        if page_key not in st.session_state:
            st.session_state[page_key] = 0
        page = st.session_state[page_key]
        page_sessions = sessions[page * page_size:(page + 1) * page_size]

        for s in page_sessions:
            rc = st.columns([1.5, 2, 1, 1.2, 1.2])
            uobj = next((u for u in all_users if u["username"] == s["username"]), {"name": s["username"], "role": "user", "username": s["username"]})
            initial = uobj["name"][0].upper() if uobj.get("name") else "?"
            acls = "adm-avatar-admin" if uobj.get("role") == "admin" else "adm-avatar-user"
            rc[0].markdown(
                f'<div class="adm-user-cell"><div class="adm-avatar {acls}" style="width:28px;height:28px;border-radius:6px;font-size:0.6rem">{initial}</div>'
                f'<span class="adm-user-name" style="font-size:0.8125rem">{s["username"]}</span></div>',
                unsafe_allow_html=True,
            )
            rc[1].markdown(f'<span class="adm-mono">{s["login_at"] or "—"}</span>', unsafe_allow_html=True)
            if s["logout_at"]:
                rc[2].markdown('<span class="adm-badge adm-badge-inactive">Ended</span>', unsafe_allow_html=True)
            else:
                rc[2].markdown('<span class="adm-badge adm-badge-active"><span class="adm-status-dot green"></span>Active</span>', unsafe_allow_html=True)
            dur = s.get("duration_s")
            rc[3].markdown(f'<span class="adm-mono">{dur if dur else "—"}</span>', unsafe_allow_html=True)
            rc[4].markdown(f'<span class="adm-mono">{s.get("ip_address") or "—"}</span>', unsafe_allow_html=True)
            st.markdown('<div style="border-bottom:1px solid rgba(255,255,255,0.025);"></div>', unsafe_allow_html=True)

        # Pagination
        st.markdown("")
        info_col, pag_col = st.columns([2, 1])
        info_col.markdown(f'<span style="font-size:0.75rem;color:#3d4155;">Showing {len(page_sessions)} of {len(sessions)} sessions</span>', unsafe_allow_html=True)
        if total_pages > 1:
            with pag_col:
                pcols = st.columns(min(total_pages, 6))
                for i, pc in enumerate(pcols):
                    if i < total_pages:
                        btn_type = "primary" if i == page else "secondary"
                        if pc.button(str(i + 1), key=f"sess_p_{i}", type=btn_type):
                            st.session_state[page_key] = i
                            st.rerun()


# ════════════════════════════════════════
# ACTIVITY LOG TAB
# ════════════════════════════════════════
with tab_activity:
    af1, af2, _ = st.columns([1, 1, 2])
    act_user = af1.selectbox("User", ["All"] + sorted({u["username"] for u in all_users}), key="act_user", label_visibility="collapsed")
    act_tool = af2.selectbox("Tool", ["All", "tracker", "hermes", "admin", "app"], key="act_tool", label_visibility="collapsed")

    activities = get_activity(
        username=None if act_user == "All" else act_user,
        tool=None if act_tool == "All" else act_tool,
        limit=500,
    )

    if not activities:
        st.caption("No activity recorded yet.")
    else:
        # Table header
        ahc = st.columns([1.5, 1, 1.5, 2.5, 1.5])
        for col, label in zip(ahc, ["User", "Tool", "Action", "Detail", "Timestamp"]):
            col.markdown(f'<span class="adm-th">{label}</span>', unsafe_allow_html=True)
        st.markdown('<hr style="margin:2px 0;border-color:rgba(255,255,255,0.04);">', unsafe_allow_html=True)

        page_size_a = 10
        total_pages_a = max(1, (len(activities) + page_size_a - 1) // page_size_a)
        apage_key = "act_page"
        if apage_key not in st.session_state:
            st.session_state[apage_key] = 0
        apage = st.session_state[apage_key]
        page_acts = activities[apage * page_size_a:(apage + 1) * page_size_a]

        for a in page_acts:
            rc = st.columns([1.5, 1, 1.5, 2.5, 1.5])
            uobj = next((u for u in all_users if u["username"] == a["username"]), {"name": a["username"], "role": "user", "username": a["username"]})
            initial = uobj["name"][0].upper() if uobj.get("name") else "?"
            acls = "adm-avatar-admin" if uobj.get("role") == "admin" else "adm-avatar-user"
            rc[0].markdown(
                f'<div class="adm-user-cell"><div class="adm-avatar {acls}" style="width:28px;height:28px;border-radius:6px;font-size:0.6rem">{initial}</div>'
                f'<span class="adm-user-name" style="font-size:0.8125rem">{a["username"]}</span></div>',
                unsafe_allow_html=True,
            )
            tool = a["tool"]
            dot_cls = tool if tool in ("tracker", "hermes", "admin", "app") else "app"
            rc[1].markdown(f'<span class="adm-tool-dot {dot_cls}"></span><span style="font-size:0.75rem;color:#8b8fa3;">{tool.capitalize()}</span>', unsafe_allow_html=True)
            rc[2].markdown(f'<span class="adm-action">{a["action"]}</span>', unsafe_allow_html=True)
            detail = a.get("detail") or "—"
            rc[3].markdown(f'<span class="adm-detail">{detail}</span>', unsafe_allow_html=True)
            rc[4].markdown(f'<span class="adm-mono">{a["logged_at"]}</span>', unsafe_allow_html=True)
            st.markdown('<div style="border-bottom:1px solid rgba(255,255,255,0.025);"></div>', unsafe_allow_html=True)

        # Pagination
        st.markdown("")
        info_col_a, pag_col_a = st.columns([2, 1])
        info_col_a.markdown(f'<span style="font-size:0.75rem;color:#3d4155;">Showing {len(page_acts)} of {len(activities)} entries</span>', unsafe_allow_html=True)
        if total_pages_a > 1:
            with pag_col_a:
                pcols = st.columns(min(total_pages_a, 6))
                for i, pc in enumerate(pcols):
                    if i < total_pages_a:
                        btn_type = "primary" if i == apage else "secondary"
                        if pc.button(str(i + 1), key=f"act_p_{i}", type=btn_type):
                            st.session_state[apage_key] = i
                            st.rerun()


# ════════════════════════════════════════
# BACKUP & RESTORE TAB
# ════════════════════════════════════════
with tab_backups:
    st.markdown(
        '<p style="font-size:0.8125rem;color:#8b8fa3;margin-bottom:1rem;">'
        'Databases are auto-backed up every <strong style="color:#c0a87e;">8 hours</strong>. '
        'Backups older than <strong style="color:#c0a87e;">15 days</strong> are auto-deleted.</p>',
        unsafe_allow_html=True,
    )

    # ── Manual backup + Upload restore side by side ──
    bk_col1, bk_col2 = st.columns(2)

    # Show success banner if restore just completed
    if st.session_state.get("_restore_success"):
        msg = st.session_state.pop("_restore_success")
        st.success(f"**{msg}** A safety backup was created before restoring.", icon="✅")

    with bk_col1:
        st.markdown("##### Create Backup")
        if st.button("Backup Now", type="primary", key="bk_manual", use_container_width=True):
            result = create_backup(label="manual")
            if result:
                log_activity(user["username"], "admin", "backup_create", result)
                st.toast(f"Backup created: {result}", icon="✅")
                st.rerun()
            else:
                st.error("No databases found to back up.")

    with bk_col2:
        st.markdown("##### Upload & Restore Tracker DB")

        # Use a unique key that changes after each successful restore to reset the uploader
        upload_gen = st.session_state.get("_upload_gen", 0)
        uploaded_db = st.file_uploader(
            "Upload a tracker.db file",
            type=["db"],
            key=f"bk_upload_{upload_gen}",
            help="Upload a valid SQLite tracker.db to replace the current one.",
        )
        if uploaded_db is not None:
            st.warning(
                f"**This will replace the current tracker database** with `{uploaded_db.name}`. "
                "A safety backup will be created first."
            )
            if st.button("Confirm Restore from Upload", type="primary", key="bk_upload_confirm"):
                data = uploaded_db.read()
                if restore_tracker_from_upload(data):
                    log_activity(user["username"], "admin", "backup_restore_upload", uploaded_db.name)
                    st.session_state["_restore_success"] = f"Tracker database restored from '{uploaded_db.name}'!"
                    # Increment to reset file uploader so they can't double-click
                    st.session_state["_upload_gen"] = upload_gen + 1
                    st.rerun()
                else:
                    st.error("Invalid SQLite database file. Please upload a valid tracker.db.")

    st.markdown("---")

    # ── Existing backups list ──
    st.markdown("##### Existing Backups")
    backups = list_backups()

    if not backups:
        st.caption("No backups yet. The first auto-backup will be created within 8 hours, or click 'Backup Now'.")
    else:
        # Table header
        bhc = st.columns([2.5, 1.2, 1.5, 1, 1.5])
        for col, label in zip(bhc, ["Backup", "Type", "Files", "Size", "Actions"]):
            col.markdown(f'<span class="adm-th">{label}</span>', unsafe_allow_html=True)
        st.markdown('<hr style="margin:2px 0;border-color:rgba(255,255,255,0.04);">', unsafe_allow_html=True)

        for bk in backups:
            rc = st.columns([2.5, 1.2, 1.5, 1, 1.5])

            # Timestamp
            ts_display = bk["timestamp"].strftime("%Y-%m-%d  %H:%M:%S")
            rc[0].markdown(f'<span class="adm-mono">{ts_display}</span>', unsafe_allow_html=True)

            # Label badge
            label = bk["label"]
            if label == "auto":
                badge_cls = "adm-badge-active"
            elif label == "manual":
                badge_cls = "adm-badge-both"
            elif label.startswith("pre-"):
                badge_cls = "adm-badge-hermes"
            else:
                badge_cls = "adm-badge-user"
            rc[1].markdown(f'<span class="adm-badge {badge_cls}">{label}</span>', unsafe_allow_html=True)

            # Files
            rc[2].markdown(
                f'<span style="font-size:0.75rem;color:#8b8fa3;">{", ".join(bk["files"])}</span>',
                unsafe_allow_html=True,
            )

            # Size
            size_kb = bk["size_bytes"] / 1024
            size_display = f"{size_kb:.0f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"
            rc[3].markdown(f'<span class="adm-mono">{size_display}</span>', unsafe_allow_html=True)

            # Actions
            with rc[4]:
                ac1, ac2 = st.columns(2)
                # Restore button (only if tracker.db exists in backup)
                if "tracker.db" in bk["files"]:
                    if ac1.button("↩️", key=f"bk_restore_{bk['name']}", help="Restore tracker from this backup"):
                        st.session_state["confirm_restore"] = bk["name"]
                        st.rerun()
                # Delete button
                if ac2.button("🗑️", key=f"bk_del_{bk['name']}", help="Delete this backup"):
                    delete_backup(bk["name"])
                    log_activity(user["username"], "admin", "backup_delete", bk["name"])
                    st.toast(f"Deleted backup: {bk['name']}", icon="🗑️")
                    st.rerun()

            st.markdown('<div style="border-bottom:1px solid rgba(255,255,255,0.025);"></div>', unsafe_allow_html=True)

        # Restore confirmation dialog
        if "confirm_restore" in st.session_state:
            bk_name = st.session_state["confirm_restore"]
            st.markdown("---")
            st.warning(
                f"**Confirm restore** from backup `{bk_name}`? "
                "This will replace the current tracker database. A safety backup will be created first."
            )
            cr1, cr2, _ = st.columns([1, 1, 3])
            if cr1.button("Yes, Restore", type="primary", key="bk_confirm_yes"):
                if restore_tracker_from_backup(bk_name):
                    log_activity(user["username"], "admin", "backup_restore", bk_name)
                    st.session_state.pop("confirm_restore", None)
                    st.session_state["_restore_success"] = f"Tracker database restored from backup '{bk_name}'!"
                    st.rerun()
                else:
                    st.error("Restore failed — tracker.db not found in this backup.")
            if cr2.button("Cancel", key="bk_confirm_no"):
                st.session_state.pop("confirm_restore", None)
                st.rerun()


# ════════════════════════════════════════
# CHANGE PASSWORD TAB
# ════════════════════════════════════════
with tab_password:
    st.markdown(
        '<p style="font-size:0.8125rem;color:#8b8fa3;margin-bottom:1.5rem;">'
        'Change your own account password. You must enter your current password for verification.</p>',
        unsafe_allow_html=True,
    )

    _, pw_col, _ = st.columns([1, 2, 1])
    with pw_col:
        with st.form("change_password_form", clear_on_submit=True):
            current_pw = st.text_input("Current Password", type="password", placeholder="Enter current password")
            new_pw = st.text_input("New Password", type="password", placeholder="Enter new password")
            confirm_pw = st.text_input("Confirm New Password", type="password", placeholder="Re-enter new password")
            pw_submitted = st.form_submit_button("Update Password", use_container_width=True, type="primary")

        if pw_submitted:
            if not current_pw or not new_pw or not confirm_pw:
                st.error("Please fill in all fields.")
            elif new_pw != confirm_pw:
                st.error("New passwords do not match.")
            elif len(new_pw) < 6:
                st.error("New password must be at least 6 characters.")
            elif not verify_password(user["username"], current_pw):
                st.error("Current password is incorrect.")
            else:
                update_user(user["username"], password=new_pw)
                log_activity(user["username"], "admin", "change_password", "Changed own password")
                st.success("Password updated successfully!", icon="✅")
