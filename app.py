"""
Stone Harp Analytics — Hosted App
Central router: login → tool picker → isolated tool pages via st.navigation().
"""
import base64
import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

import time

from auth.auth_db import (
    init_auth_db, verify_password, get_user, log_login, log_logout, log_activity,
    check_rate_limit, record_failed_attempt, clear_attempts,
)
from auth.auth_ui import sidebar_user_info, logout, SESSION_TIMEOUT_SECONDS
from auth.backup import auto_backup_if_due, cleanup_old_backups
from db.database import init_db
from db.seed_data import seed_all

init_auth_db()
init_db()
seed_all()

# Auto-backup every 8 hours, clean up backups older than 15 days
auto_backup_if_due()
cleanup_old_backups()

ASSETS = os.path.join(os.path.dirname(__file__), "assets")


def _load_css():
    """Load the shared style.css."""
    css_path = os.path.join(ASSETS, "style.css")
    if os.path.exists(css_path):
        css = Path(css_path).read_text()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# SVG constants used across pages
LOGO_SVG = '''<svg viewBox="0 0 40 44" xmlns="http://www.w3.org/2000/svg">
  <path d="M20 0C18 0 16.5 1.5 16.5 3.5V6C12.5 7.5 9 10 7 13.5C4.5 17.5 4 22 5.5 26C7 30 10.5 33 14.5 34.5V38H12V40H28V38H25.5V34.5C29.5 33 33 30 34.5 26C36 22 35.5 17.5 33 13.5C31 10 27.5 7.5 23.5 6V3.5C23.5 1.5 22 0 20 0ZM20 8C24 8 27.5 10 30 13C32 16 32.5 19.5 31.5 23C30.5 26 28 28.5 25 30H15C12 28.5 9.5 26 8.5 23C7.5 19.5 8 16 10 13C12.5 10 16 8 20 8Z"/>
  <line x1="14" y1="14" x2="14" y2="28" stroke="currentColor" stroke-width="1.2" opacity="0.5"/>
  <line x1="18" y1="11" x2="18" y2="30" stroke="currentColor" stroke-width="1.2" opacity="0.5"/>
  <line x1="22" y1="11" x2="22" y2="30" stroke="currentColor" stroke-width="1.2" opacity="0.5"/>
  <line x1="26" y1="14" x2="26" y2="28" stroke="currentColor" stroke-width="1.2" opacity="0.5"/>
</svg>'''

ARROW_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>'


# ═══════════════════════════════════════════════════════════════
#  Page functions
# ═══════════════════════════════════════════════════════════════

def _login_page():
    """Login — centered card with ambient background."""
    st.set_page_config(page_title="Sign In — Stone Harp Analytics", page_icon="🔐", layout="centered")
    _load_css()

    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    .stApp > header { display: none !important; }

    .bg-grid {
        position: fixed; inset: 0; z-index: 0; pointer-events: none;
        background-image:
            linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px);
        background-size: 60px 60px;
        mask-image: radial-gradient(ellipse 70% 70% at 50% 50%, black 20%, transparent 70%);
    }
    .orb { position: fixed; border-radius: 50%; filter: blur(80px); z-index: 0; pointer-events: none; animation: drift 20s ease-in-out infinite alternate; }
    .orb-1 { width: 400px; height: 400px; background: rgba(192,168,126,0.07); top: -100px; right: -100px; animation-duration: 25s; }
    .orb-2 { width: 300px; height: 300px; background: rgba(79,124,255,0.05); bottom: -80px; left: -80px; animation-duration: 30s; animation-direction: alternate-reverse; }
    @keyframes drift {
        0%  { transform: translate(0, 0) scale(1); }
        50% { transform: translate(30px, -20px) scale(1.05); }
        100%{ transform: translate(-20px, 15px) scale(0.95); }
    }
    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(24px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    .login-brand { text-align: center; margin-bottom: 2rem; animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) both; }
    .login-brand .logo-mark {
        width: 72px; height: 72px; margin: 0 auto 1.25rem; border-radius: 18px;
        background: linear-gradient(135deg, rgba(192,168,126,0.15), rgba(192,168,126,0.05));
        border: 1px solid rgba(192,168,126,0.2); display: flex; align-items: center; justify-content: center;
        color: #c0a87e; box-shadow: 0 0 40px rgba(192,168,126,0.08);
    }
    .login-brand .logo-mark svg { width: 36px; height: 36px; fill: #c0a87e; }
    .login-brand h1 { font-family: 'Playfair Display', Georgia, serif; font-size: 1.75rem; font-weight: 600; color: #f1f1f4; margin-bottom: 0.375rem; }
    .login-brand p { font-size: 0.875rem; color: #8b8fa3; }
    .login-footer { text-align: center; margin-top: 1.5rem; font-size: 0.75rem; color: #5a5e72; animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.35s both; }
    .login-footer span { color: #c0a87e; opacity: 0.6; }

    [data-testid="stForm"] {
        background: rgba(17, 24, 39, 0.6) !important;
        backdrop-filter: blur(24px) saturate(1.2) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 20px !important;
        padding: 2.25rem 2rem 2rem !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.2), 0 8px 32px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.03) !important;
        max-width: 420px; margin: 0 auto;
    }
    </style>
    <div class="bg-grid"></div>
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="login-brand">
        <div class="logo-mark">{LOGO_SVG}</div>
        <h1>Stone Harp Analytics</h1>
        <p>Sign in to your workspace</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

    if submitted:
        if not username or not password:
            st.error("Please enter both username and password.")
            return

        # Rate limiting
        allowed, wait_seconds = check_rate_limit(username.lower())
        if not allowed:
            mins, secs = divmod(wait_seconds, 60)
            st.error(f"Too many failed attempts. Try again in {mins}m {secs}s.")
            return

        if verify_password(username, password):
            clear_attempts(username.lower())
            user = get_user(username)
            st.session_state["auth_user"] = user
            st.session_state["_last_active"] = time.time()
            sid = log_login(username)
            st.session_state["auth_session_id"] = sid
            log_activity(username, "app", "login", "Signed in")
            st.rerun()
        else:
            record_failed_attempt(username.lower())
            allowed_now, _ = check_rate_limit(username.lower())
            if not allowed_now:
                st.error("Account locked for 5 minutes due to too many failed attempts.")
            else:
                st.error("Invalid username or password.")

    st.markdown('<div class="login-footer"><span>&#9670;</span>&ensp;Secure access&ensp;<span>&#9670;</span></div>', unsafe_allow_html=True)


def _landing_page():
    """Tool picker — matches the HTML landing design."""
    st.set_page_config(page_title="Stone Harp Analytics", page_icon="🌐", layout="wide", initial_sidebar_state="collapsed")
    _load_css()

    user = st.session_state["auth_user"]
    initial = user["name"][0].upper() if user["name"] else "U"
    role_label = "Administrator" if user["role"] == "admin" else "User"

    # Inject background, topbar, hide sidebar
    st.markdown(f"""
    <style>
    [data-testid="stSidebar"] {{ display: none !important; }}
    .stApp > header {{ display: none !important; }}
    [data-testid="stAppViewBlockContainer"] {{ padding-top: 5rem !important; }}

    .bg-grid {{
        position: fixed; inset: 0; z-index: 0; pointer-events: none;
        background-image: linear-gradient(rgba(255,255,255,0.012) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.012) 1px, transparent 1px);
        background-size: 60px 60px;
        mask-image: radial-gradient(ellipse 70% 70% at 50% 50%, black 20%, transparent 70%);
    }}
    .orb {{ position: fixed; border-radius: 50%; filter: blur(80px); z-index: 0; pointer-events: none; animation: drift 20s ease-in-out infinite alternate; }}
    .orb-1 {{ width: 500px; height: 500px; background: rgba(192,168,126,0.05); top: -150px; right: -150px; animation-duration: 28s; }}
    .orb-2 {{ width: 350px; height: 350px; background: rgba(79,124,255,0.04); bottom: -100px; left: -100px; animation-duration: 32s; animation-direction: alternate-reverse; }}
    @keyframes drift {{
        0%  {{ transform: translate(0, 0) scale(1); }}
        50% {{ transform: translate(30px, -20px) scale(1.05); }}
        100%{{ transform: translate(-20px, 15px) scale(0.95); }}
    }}
    @keyframes fadeDown {{
        from {{ opacity: 0; transform: translateY(-12px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes fadeUp {{
        from {{ opacity: 0; transform: translateY(20px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}

    /* Topbar */
    .topbar {{
        position: fixed; top: 0; left: 0; right: 0; z-index: 999;
        display: flex; align-items: center; justify-content: space-between;
        padding: 0.875rem 2rem;
        background: rgba(10, 14, 26, 0.75);
        backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        border-bottom: 1px solid rgba(255,255,255,0.06);
        animation: fadeDown 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
    }}
    .topbar-left {{ display: flex; align-items: center; gap: 0.75rem; }}
    .topbar-logo {{
        width: 34px; height: 34px; border-radius: 8px;
        background: linear-gradient(135deg, rgba(192,168,126,0.18), rgba(192,168,126,0.06));
        border: 1px solid rgba(192,168,126,0.2);
        display: flex; align-items: center; justify-content: center; color: #c0a87e;
    }}
    .topbar-logo svg {{ width: 18px; height: 18px; fill: #c0a87e; }}
    .topbar-title {{ font-family: 'Playfair Display', Georgia, serif; font-size: 1rem; font-weight: 600; color: #f1f1f4; }}
    .topbar-right {{ display: flex; align-items: center; gap: 1rem; }}
    .user-badge {{
        display: flex; align-items: center; gap: 0.625rem;
        padding: 0.375rem 0.875rem 0.375rem 0.5rem;
        background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06); border-radius: 100px;
    }}
    .user-avatar {{
        width: 28px; height: 28px; border-radius: 50%;
        background: linear-gradient(135deg, #c0a87e, #a08a5c);
        display: flex; align-items: center; justify-content: center;
        font-size: 0.6875rem; font-weight: 600; color: #0a0e1a;
    }}
    .user-name {{ font-size: 0.8125rem; font-weight: 500; color: #f1f1f4; }}
    .user-role {{ font-size: 0.6875rem; color: #5a5e72; text-transform: uppercase; letter-spacing: 0.05em; }}

    /* Hero */
    .hero {{ text-align: center; margin-bottom: 2.5rem; animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.15s both; }}
    .hero h1 {{ font-family: 'Playfair Display', Georgia, serif; font-size: 2.25rem; font-weight: 600; letter-spacing: -0.01em; margin-bottom: 0.5rem; color: #f1f1f4; }}
    .hero h1 .gold {{ color: #c0a87e; }}
    .hero p {{ font-size: 1rem; color: #8b8fa3; }}

    /* Tool cards */
    .tool-card {{
        background: rgba(17,24,39,0.55); backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.06); border-radius: 20px;
        padding: 2rem 1.75rem 1.75rem; cursor: pointer;
        transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
        overflow: hidden; position: relative;
    }}
    .tool-card::before {{
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
        background: linear-gradient(90deg, transparent, var(--card-accent), transparent);
        opacity: 0; transition: opacity 0.35s ease;
    }}
    .tool-card:hover {{
        background: rgba(22,31,48,0.7); border-color: rgba(255,255,255,0.1);
        transform: translateY(-4px); box-shadow: 0 12px 40px rgba(0,0,0,0.3);
    }}
    .tool-card:hover::before {{ opacity: 1; }}
    .tool-card.tracker {{ --card-accent: #4f7cff; animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.25s both; }}
    .tool-card.hermes {{ --card-accent: #2dd4bf; animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.35s both; }}

    .tool-icon {{
        width: 52px; height: 52px; border-radius: 14px;
        display: flex; align-items: center; justify-content: center;
        margin-bottom: 1.25rem; transition: transform 0.35s ease, box-shadow 0.35s ease;
    }}
    .tracker .tool-icon {{ background: linear-gradient(135deg, rgba(79,124,255,0.15), rgba(79,124,255,0.05)); border: 1px solid rgba(79,124,255,0.2); color: #4f7cff; }}
    .hermes .tool-icon {{ background: linear-gradient(135deg, rgba(45,212,191,0.15), rgba(45,212,191,0.05)); border: 1px solid rgba(45,212,191,0.2); color: #2dd4bf; }}
    .tool-card:hover .tool-icon {{ transform: scale(1.08); }}

    .tool-icon svg {{ width: 26px; height: 26px; }}
    .tool-name {{ font-family: 'Playfair Display', Georgia, serif; font-size: 1.25rem; font-weight: 600; color: #f1f1f4; margin-bottom: 0.5rem; }}
    .tool-desc {{ font-size: 0.8125rem; color: #8b8fa3; line-height: 1.6; margin-bottom: 1.5rem; }}
    .tool-cta {{ display: flex; align-items: center; gap: 0.375rem; font-size: 0.8125rem; font-weight: 500; transition: gap 0.25s ease; }}
    .tool-card:hover .tool-cta {{ gap: 0.625rem; }}
    .tool-cta svg {{ width: 16px; height: 16px; }}
    .tracker .tool-cta {{ color: #4f7cff; }}
    .hermes .tool-cta {{ color: #2dd4bf; }}

    /* Page footer */
    .page-footer {{ text-align: center; margin-top: 2rem; font-size: 0.6875rem; color: #5a5e72; animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.55s both; }}
    </style>

    <div class="bg-grid"></div>
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>

    <header class="topbar">
        <div class="topbar-left">
            <div class="topbar-logo">
                <svg viewBox="0 0 40 44" xmlns="http://www.w3.org/2000/svg"><path d="M20 0C18 0 16.5 1.5 16.5 3.5V6C12.5 7.5 9 10 7 13.5C4.5 17.5 4 22 5.5 26C7 30 10.5 33 14.5 34.5V38H12V40H28V38H25.5V34.5C29.5 33 33 30 34.5 26C36 22 35.5 17.5 33 13.5C31 10 27.5 7.5 23.5 6V3.5C23.5 1.5 22 0 20 0Z"/></svg>
            </div>
            <span class="topbar-title">Stone Harp Analytics</span>
        </div>
        <div class="topbar-right">
            <div class="user-badge">
                <div class="user-avatar">{initial}</div>
                <div style="line-height:1.2;">
                    <div class="user-name">{user["name"]}</div>
                    <div class="user-role">{role_label}</div>
                </div>
            </div>
        </div>
    </header>
    """, unsafe_allow_html=True)

    # Hero
    st.markdown(f"""
    <div class="hero">
        <h1>Welcome back, <span class="gold">{user["name"]}</span></h1>
        <p>Select a tool to continue</p>
    </div>
    """, unsafe_allow_html=True)

    # Tool cards — use columns for layout, HTML for visuals, st.button for action
    access = user.get("tool_access", "both")

    _, col_tracker, spacer, col_hermes, _ = st.columns([0.8, 2, 0.15, 2, 0.8])

    if access in ("both", "tracker"):
        with col_tracker:
            st.markdown("""
            <div class="tool-card tracker">
                <div class="tool-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="4" rx="1"/><rect x="3" y="14" width="7" height="4" rx="1"/><rect x="14" y="11" width="7" height="7" rx="1"/></svg>
                </div>
                <div class="tool-name">Dashboard Tracker</div>
                <div class="tool-desc">Manage contracts, personnel, imagery orders, and generate reports.</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Open Tracker  →", use_container_width=True, key="btn_tracker", type="primary"):
                st.session_state["active_tool"] = "tracker"
                log_activity(user["username"], "tracker", "open", "Opened Dashboard Tracker")
                st.rerun()

    if access in ("both", "hermes"):
        with col_hermes:
            st.markdown("""
            <div class="tool-card hermes">
                <div class="tool-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                </div>
                <div class="tool-name">Hermes</div>
                <div class="tool-desc">Convert intelligence analyst data (CSV / Excel) into GIS formats.</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Open Hermes  →", use_container_width=True, key="btn_hermes", type="primary"):
                st.session_state["active_tool"] = "hermes"
                log_activity(user["username"], "hermes", "open", "Opened Hermes")
                st.rerun()

    # Sign out button (in topbar position via CSS trickery)
    st.markdown("")
    _, logout_col, _ = st.columns([4, 1.2, 4])
    with logout_col:
        if st.button("Sign Out", key="landing_logout", use_container_width=True):
            logout()

    # Admin button — only for admins, subtle
    if user["role"] == "admin":
        _, admin_col, _ = st.columns([3, 1, 3])
        with admin_col:
            st.markdown("")
            if st.button("Admin Panel", use_container_width=True, key="btn_admin"):
                st.session_state["active_tool"] = "admin"
                st.rerun()

    st.markdown('<div class="page-footer">Stone Harp Analytics &middot; v1.0</div>', unsafe_allow_html=True)


def _back_to_home():
    """Pseudo-page: clears active_tool and goes back to landing."""
    st.session_state.pop("active_tool", None)
    st.rerun()


# ═══════════════════════════════════════════════════════════════
#  Navigation router
# ═══════════════════════════════════════════════════════════════

# ── Session timeout check ──
if "auth_user" in st.session_state:
    last_active = st.session_state.get("_last_active")
    if last_active and (time.time() - last_active > SESSION_TIMEOUT_SECONDS):
        _user = st.session_state["auth_user"]
        log_activity(_user["username"], "app", "timeout", "Session expired due to inactivity")
        sid = st.session_state.get("auth_session_id")
        if sid:
            log_logout(sid)
        for key in ["auth_user", "auth_session_id", "_last_active", "active_tool"]:
            st.session_state.pop(key, None)
        st.rerun()
    # Refresh activity timestamp
    st.session_state["_last_active"] = time.time()

logged_in = "auth_user" in st.session_state
active_tool = st.session_state.get("active_tool")
user = st.session_state.get("auth_user", {})

if not logged_in:
    pg = st.navigation([st.Page(_login_page, title="Sign In", icon="🔐")], position="hidden")

elif active_tool == "tracker":
    pg = st.navigation({
        "": [st.Page(_back_to_home, title="Back to Home", icon="🏠")],
        "Tracker": [
            st.Page("pages/Tracker_1_Dashboard.py", title="Dashboard", icon="📈", default=True),
            st.Page("pages/Tracker_2_Projects.py", title="Projects", icon="📁"),
            st.Page("pages/Tracker_3_Imagery_Catalog.py", title="Imagery Catalog", icon="🖼️"),
            st.Page("pages/Tracker_4_Imagery_Orders.py", title="Imagery Orders", icon="📦"),
            st.Page("pages/Tracker_5_Day_Rate_Tracker.py", title="Day Rate", icon="📅"),
            st.Page("pages/Tracker_6_Reports.py", title="Reports", icon="📄"),
            st.Page("pages/Tracker_7_Settings.py", title="Settings", icon="⚙️"),
        ],
    })

elif active_tool == "hermes":
    pg = st.navigation({
        "": [st.Page(_back_to_home, title="Back to Home", icon="🏠")],
        "Hermes": [st.Page("pages/2_Hermes.py", title="Hermes", icon="🌍", default=True)],
    })

elif active_tool == "admin":
    pg = st.navigation({
        "": [st.Page(_back_to_home, title="Back to Home", icon="🏠")],
        "Admin": [st.Page("pages/3_Admin.py", title="Admin Panel", icon="⚙️", default=True)],
    })

else:
    pg = st.navigation([st.Page(_landing_page, title="Home", icon="🏠")], position="hidden")

pg.run()
