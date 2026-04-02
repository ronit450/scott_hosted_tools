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
    create_remember_token, validate_remember_token,
)
from auth.auth_ui import sidebar_user_info, logout, SESSION_TIMEOUT_SECONDS, COOKIE_NAME, _get_cookie_controller
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

def _get_logo_b64():
    """Return the Stone Harp logo as a base64 data URI (cached)."""
    if "_logo_b64" not in st.session_state:
        logo_path = os.path.join(ASSETS, "stoneharp_logo.png")
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                st.session_state["_logo_b64"] = base64.b64encode(f.read()).decode()
        else:
            st.session_state["_logo_b64"] = ""
    return st.session_state["_logo_b64"]


def _show_splash():
    """Premium full-screen splash screen shown while cookies initialise."""
    logo_b64 = _get_logo_b64()
    logo_img = f'<img src="data:image/png;base64,{logo_b64}" style="width:90px;height:auto;filter:drop-shadow(0 0 30px rgba(181,113,74,0.3));">' if logo_b64 else ""

    # ── CSS (plain string — no f-string needed) ──
    splash_css = """
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    .stApp > header { display: none !important; }
    [data-testid="stAppViewBlockContainer"] { animation: none !important; padding: 0 !important; }

    .splash-wrap {
        position: fixed; inset: 0; z-index: 9999;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        background: #060a14;
    }
    .splash-bg {
        position: fixed; inset: 0; z-index: 0;
        background:
            radial-gradient(ellipse 100% 80% at 50% 50%, rgba(181,113,74,0.06) 0%, transparent 50%),
            radial-gradient(ellipse 60% 40% at 20% 80%, rgba(79,124,255,0.03) 0%, transparent 50%),
            radial-gradient(ellipse 60% 40% at 80% 20%, rgba(192,168,126,0.04) 0%, transparent 50%),
            #060a14;
    }
    .splash-grid {
        position: fixed; inset: 0; z-index: 0;
        background-image:
            linear-gradient(rgba(192,168,126,0.018) 1px, transparent 1px),
            linear-gradient(90deg, rgba(192,168,126,0.018) 1px, transparent 1px);
        background-size: 56px 56px;
        mask-image: radial-gradient(ellipse 60% 60% at 50% 50%, black 10%, transparent 65%);
        animation: gridPulse 8s ease-in-out infinite;
    }
    @keyframes gridPulse { 0%,100% { opacity: 0.4; } 50% { opacity: 1; } }

    .splash-content {
        position: relative; z-index: 5;
        text-align: center;
        display: flex; flex-direction: column;
        align-items: center;
    }

    .splash-logo-wrap { position: relative; margin-bottom: 2.5rem; }
    .splash-ring {
        position: absolute; top: 50%; left: 50%;
        width: 180px; height: 180px;
        transform: translate(-50%, -50%);
        border-radius: 50%;
        border: 1px solid rgba(192,168,126,0.1);
        animation: ringExpand 2s cubic-bezier(0.16,1,0.3,1) 0.3s both;
    }
    .splash-ring::after {
        content: ''; position: absolute; inset: -20px;
        border-radius: 50%;
        border: 1px solid rgba(192,168,126,0.04);
        animation: ringPulse 4s ease-in-out 2s infinite;
    }
    @keyframes ringExpand { from { opacity:0; width:120px; height:120px; } to { opacity:1; width:180px; height:180px; } }
    @keyframes ringPulse { 0%,100% { transform:scale(1); opacity:0.4; } 50% { transform:scale(1.15); opacity:0.8; } }

    .splash-glow {
        position: absolute; top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        width: 160px; height: 160px; border-radius: 50%;
        background: radial-gradient(circle, rgba(181,113,74,0.2) 0%, rgba(192,168,126,0.05) 50%, transparent 70%);
        filter: blur(40px);
        animation: glowIn 2s ease 0.5s both, glowPulse 5s ease-in-out 2s infinite;
    }
    @keyframes glowIn { from { opacity:0; transform:translate(-50%,-50%) scale(0.5); } to { opacity:1; transform:translate(-50%,-50%) scale(1); } }
    @keyframes glowPulse { 0%,100% { opacity:0.7; transform:translate(-50%,-50%) scale(1); } 50% { opacity:1; transform:translate(-50%,-50%) scale(1.1); } }

    .splash-logo-icon {
        position: relative;
        opacity: 0;
        animation: logoReveal 1.4s cubic-bezier(0.16,1,0.3,1) 0.6s forwards;
    }
    @keyframes logoReveal {
        0%   { opacity:0; transform:scale(0.7) translateY(10px); }
        60%  { opacity:1; transform:scale(1.03); }
        100% { opacity:1; transform:scale(1) translateY(0); }
    }

    .splash-name { font-family: 'Playfair Display', Georgia, serif; font-size: 2.75rem; font-weight: 700; line-height: 1.1; margin-bottom: 0.75rem; overflow: hidden; }
    .splash-name-line { display: block; opacity: 0; transform: translateY(100%); }
    .splash-name-1 { color: #f1f1f4; animation: textUp 0.9s cubic-bezier(0.16,1,0.3,1) 1.1s forwards; }
    .splash-name-2 { color: #c0a87e; animation: textUp 0.9s cubic-bezier(0.16,1,0.3,1) 1.3s forwards; }
    @keyframes textUp { from { opacity:0; transform:translateY(100%); } to { opacity:1; transform:translateY(0); } }

    .splash-divider {
        display: flex; align-items: center; gap: 1rem;
        margin: 1.25rem 0 1.5rem; opacity: 0;
        animation: splashFadeIn 0.8s ease 1.6s forwards;
    }
    .splash-divider-line { width: 60px; height: 1px; background: linear-gradient(90deg, transparent, rgba(192,168,126,0.3), transparent); }
    .splash-divider-diamond { width: 6px; height: 6px; background: #c0a87e; transform: rotate(45deg); opacity: 0.6; }
    @keyframes splashFadeIn { from { opacity:0; } to { opacity:1; } }

    .splash-tagline {
        font-size: 0.875rem; color: #8b8fa3; font-weight: 400;
        letter-spacing: 0.15em; text-transform: uppercase;
        opacity: 0; animation: splashFadeIn 1s ease 1.8s forwards;
        font-family: 'DM Sans', -apple-system, sans-serif;
    }

    .splash-loader {
        margin-top: 3.5rem; display: flex; flex-direction: column;
        align-items: center; gap: 1rem;
        opacity: 0; animation: splashFadeIn 0.8s ease 2s forwards;
    }
    .splash-bar { width: 180px; height: 2px; background: rgba(255,255,255,0.04); border-radius: 2px; overflow: hidden; position: relative; }
    .splash-fill {
        position: absolute; top: 0; left: 0; height: 100%; width: 0%;
        background: linear-gradient(90deg, #a08a5c, #c0a87e, #d4c4a0);
        border-radius: 2px;
        animation: loadBar 2s cubic-bezier(0.4,0,0.2,1) 2.2s forwards;
    }
    @keyframes loadBar { 0% { width:0%; } 30% { width:40%; } 70% { width:75%; } 100% { width:100%; } }
    .splash-loader-text {
        font-size: 0.6875rem; color: #4a4e62;
        letter-spacing: 0.12em; text-transform: uppercase;
        font-family: 'DM Sans', -apple-system, sans-serif;
    }

    .splash-particle {
        position: fixed; width: 2px; height: 2px; border-radius: 50%;
        background: #c0a87e; opacity: 0; z-index: 1;
    }
    .sp1 { top: 18%; left: 25%; animation: pFloat 6s ease-in-out 2s infinite; }
    .sp2 { top: 72%; left: 70%; animation: pFloat 7s ease-in-out 2.4s infinite; }
    .sp3 { top: 35%; right: 18%; animation: pFloat 5s ease-in-out 2.8s infinite; }
    .sp4 { bottom: 25%; left: 15%; animation: pFloat 8s ease-in-out 3s infinite; }
    .sp5 { top: 50%; right: 30%; animation: pFloat 6.5s ease-in-out 3.2s infinite; width: 3px; height: 3px; }
    @keyframes pFloat {
        0%   { opacity:0; transform:translateY(0) scale(1); }
        20%  { opacity:0.6; }
        50%  { opacity:0.3; transform:translateY(-20px) scale(1.5); }
        80%  { opacity:0.5; }
        100% { opacity:0; transform:translateY(-40px) scale(0.5); }
    }

    .splash-corner {
        position: fixed; z-index: 1; width: 80px; height: 80px;
        border: 1px solid rgba(192,168,126,0.07);
        opacity: 0; animation: cornerIn 1.2s cubic-bezier(0.16,1,0.3,1) forwards;
    }
    .sc-tl { top: 2rem; left: 2rem; border-right:none; border-bottom:none; animation-delay: 1.8s; }
    .sc-tr { top: 2rem; right: 2rem; border-left:none; border-bottom:none; animation-delay: 2s; }
    .sc-bl { bottom: 2rem; left: 2rem; border-right:none; border-top:none; animation-delay: 2.2s; }
    .sc-br { bottom: 2rem; right: 2rem; border-left:none; border-top:none; animation-delay: 2.4s; }
    @keyframes cornerIn { from { opacity:0; transform:scale(0.8); } to { opacity:1; transform:scale(1); } }

    .splash-copyright {
        position: fixed; bottom: 1.5rem; left: 0; right: 0; text-align: center;
        font-size: 0.625rem; color: #4a4e62; letter-spacing: 0.1em;
        text-transform: uppercase; opacity: 0; animation: splashFadeIn 0.6s ease 2.5s forwards;
        z-index: 5; font-family: 'DM Sans', -apple-system, sans-serif;
    }
    </style>
    """

    # ── HTML body (separate string, logo injected via concatenation) ──
    splash_html = (
        '<div class="splash-bg"></div>'
        '<div class="splash-grid"></div>'
        '<div class="splash-particle sp1"></div>'
        '<div class="splash-particle sp2"></div>'
        '<div class="splash-particle sp3"></div>'
        '<div class="splash-particle sp4"></div>'
        '<div class="splash-particle sp5"></div>'
        '<div class="splash-corner sc-tl"></div>'
        '<div class="splash-corner sc-tr"></div>'
        '<div class="splash-corner sc-bl"></div>'
        '<div class="splash-corner sc-br"></div>'
        '<div class="splash-wrap">'
        '  <div class="splash-content">'
        '    <div class="splash-logo-wrap">'
        '      <div class="splash-ring"></div>'
        '      <div class="splash-glow"></div>'
        '      <div class="splash-logo-icon">' + logo_img + '</div>'
        '    </div>'
        '    <h1 class="splash-name">'
        '      <span class="splash-name-line splash-name-1">Stone Harp</span>'
        '      <span class="splash-name-line splash-name-2">Analytics</span>'
        '    </h1>'
        '    <div class="splash-divider">'
        '      <div class="splash-divider-line"></div>'
        '      <div class="splash-divider-diamond"></div>'
        '      <div class="splash-divider-line"></div>'
        '    </div>'
        '    <p class="splash-tagline">Intelligence &middot; Precision &middot; Clarity</p>'
        '    <div class="splash-loader">'
        '      <div class="splash-bar"><div class="splash-fill"></div></div>'
        '      <div class="splash-loader-text">Initializing</div>'
        '    </div>'
        '  </div>'
        '</div>'
        '<div class="splash-copyright">&copy; 2026 Stone Harp Analytics</div>'
    )

    st.markdown(splash_css, unsafe_allow_html=True)
    st.markdown(splash_html, unsafe_allow_html=True)


def _login_page():
    """Login — immersive split-screen: branding left, form right."""
    _load_css()

    # ── Hide sidebar + header, set up full-viewport split ──
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    .stApp > header { display: none !important; }
    [data-testid="stAppViewBlockContainer"] {
        padding: 0 !important;
        max-width: 100% !important;
    }
    .block-container { padding: 0 !important; max-width: 100% !important; }

    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(24px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes slideInRight {
        from { opacity: 0; transform: translateX(30px); }
        to   { opacity: 1; transform: translateX(0); }
    }
    @keyframes ringPulse {
        0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.4; }
        50%      { transform: translate(-50%, -50%) scale(1.08); opacity: 0.7; }
    }
    @keyframes glowPulse {
        0%, 100% { opacity: 0.5; transform: translate(-50%, -50%) scale(1); }
        50%      { opacity: 0.8; transform: translate(-50%, -50%) scale(1.05); }
    }

    .login-brand-panel {
        background: linear-gradient(135deg, #0a0e1a, #0f1520);
        min-height: 100vh;
        padding: 2.5rem;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        position: relative;
        overflow: hidden;
    }
    .login-brand-panel .grid-overlay {
        position: absolute; inset: 0;
        background-image:
            linear-gradient(rgba(192,168,126,0.02) 1px, transparent 1px),
            linear-gradient(90deg, rgba(192,168,126,0.02) 1px, transparent 1px);
        background-size: 60px 60px;
        pointer-events: none;
    }
    .login-brand-panel .ring {
        position: absolute; top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        border-radius: 50%;
        border: 1px solid rgba(192,168,126,0.06);
        pointer-events: none;
    }
    .login-brand-panel .ring-1 { width: 300px; height: 300px; }
    .login-brand-panel .ring-2 {
        width: 200px; height: 200px;
        border-color: rgba(192,168,126,0.1);
        animation: ringPulse 6s ease-in-out infinite;
    }
    .login-brand-panel .glow {
        position: absolute; top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        width: 350px; height: 350px; border-radius: 50%;
        background: radial-gradient(circle, rgba(192,168,126,0.08), transparent 70%);
        filter: blur(60px);
        pointer-events: none;
        animation: glowPulse 8s ease-in-out infinite;
    }

    .brand-top {
        position: relative; z-index: 1;
        display: flex; align-items: center; gap: 0.75rem;
        animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both;
    }
    .brand-top .logo-box {
        width: 40px; height: 40px; border-radius: 10px;
        background: linear-gradient(135deg, rgba(192,168,126,0.18), rgba(192,168,126,0.06));
        border: 1px solid rgba(192,168,126,0.25);
        display: flex; align-items: center; justify-content: center;
    }
    .brand-top .logo-box svg { width: 20px; height: 20px; fill: #c0a87e; }
    .brand-top span {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1rem; font-weight: 600; color: #f1f1f4;
    }

    .brand-hero {
        position: relative; z-index: 1;
        text-align: center;
        animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.4s both;
    }
    .brand-hero h1 {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2.75rem; font-weight: 600; line-height: 1.15;
        margin: 0;
    }
    .brand-hero h1 .white { color: #f1f1f4; }
    .brand-hero h1 .gold  { color: #c0a87e; }
    .brand-hero p {
        font-size: 0.875rem; color: #8b8fa3; margin-top: 1rem;
        max-width: 300px; margin-left: auto; margin-right: auto;
    }

    .brand-stats {
        position: relative; z-index: 1;
        display: flex; justify-content: center; gap: 2.5rem;
        animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.6s both;
    }
    .brand-stats .stat { text-align: center; }
    .brand-stats .stat-value {
        font-size: 1.5rem; font-weight: 700;
        font-family: 'DM Sans', sans-serif;
    }
    .brand-stats .stat-label {
        font-size: 0.6875rem; color: #8b8fa3;
        text-transform: uppercase; letter-spacing: 0.1em;
        margin-top: 0.25rem;
    }
    .brand-stats .stat-divider {
        width: 1px;
        background: rgba(255,255,255,0.06);
        align-self: stretch;
    }

    .login-form-panel [data-testid="stForm"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        max-width: none;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Layout: two columns ──
    col_brand, col_form = st.columns([1.2, 0.8], gap="none")

    with col_brand:
        st.markdown(f"""
        <div class="login-brand-panel">
            <div class="grid-overlay"></div>
            <div class="ring ring-1"></div>
            <div class="ring ring-2"></div>
            <div class="glow"></div>

            <div class="brand-top">
                <div class="logo-box">{LOGO_SVG}</div>
                <span>Stone Harp Analytics</span>
            </div>

            <div class="brand-hero">
                <h1>
                    <span class="white">Intelligence</span><br>
                    <span class="gold">Reimagined</span>
                </h1>
                <p>Geospatial analysis, data conversion, and imagery tiling — unified in one platform.</p>
            </div>

            <div class="brand-stats">
                <div class="stat">
                    <div class="stat-value" style="color:#4f7cff;">3</div>
                    <div class="stat-label">Tools</div>
                </div>
                <div class="stat-divider"></div>
                <div class="stat">
                    <div class="stat-value" style="color:#2dd4bf;">24/7</div>
                    <div class="stat-label">Access</div>
                </div>
                <div class="stat-divider"></div>
                <div class="stat">
                    <div class="stat-value" style="color:#f59e0b;">Secure</div>
                    <div class="stat-label">Platform</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_form:
        st.markdown("")
        st.markdown("")
        st.markdown("")
        st.markdown("""<h2 style="font-family:'Playfair Display',Georgia,serif;font-size:1.5rem;font-weight:600;color:#f1f1f4;margin-bottom:0.25rem;">Welcome back</h2>""", unsafe_allow_html=True)
        st.markdown("""<p style="font-size:0.875rem;color:#8b8fa3;margin-bottom:1rem;">Sign in to continue</p>""", unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            remember_me = st.checkbox("Remember me for 30 days", value=True)
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

        st.markdown('<div style="text-align:center;font-size:0.75rem;color:#5a5e72;margin-top:1.5rem;"><span style="color:#c0a87e;opacity:0.6;">&#9670;</span>&ensp;Secure access&ensp;<span style="color:#c0a87e;opacity:0.6;">&#9670;</span></div>', unsafe_allow_html=True)

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

            # Remember Me — set cookie
            if remember_me:
                try:
                    raw_token = create_remember_token(username)
                    ctrl = _get_cookie_controller()
                    ctrl.set(COOKIE_NAME, raw_token, max_age=30 * 24 * 3600)
                    st.session_state["_remember_token"] = raw_token
                except Exception:
                    pass  # cookie set failed, login still works

            st.rerun()
        else:
            record_failed_attempt(username.lower())
            allowed_now, _ = check_rate_limit(username.lower())
            if not allowed_now:
                st.error("Account locked for 5 minutes due to too many failed attempts.")
            else:
                st.error("Invalid username or password.")


def _landing_page():
    """Tool picker — matches the HTML landing design."""
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
    .tool-card.daedalus {{ --card-accent: #f59e0b; animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.45s both; }}

    .tool-icon {{
        width: 52px; height: 52px; border-radius: 14px;
        display: flex; align-items: center; justify-content: center;
        margin-bottom: 1.25rem; transition: transform 0.35s ease, box-shadow 0.35s ease;
    }}
    .tracker .tool-icon {{ background: linear-gradient(135deg, rgba(79,124,255,0.15), rgba(79,124,255,0.05)); border: 1px solid rgba(79,124,255,0.2); color: #4f7cff; }}
    .hermes .tool-icon {{ background: linear-gradient(135deg, rgba(45,212,191,0.15), rgba(45,212,191,0.05)); border: 1px solid rgba(45,212,191,0.2); color: #2dd4bf; }}
    .daedalus .tool-icon {{ background: linear-gradient(135deg, rgba(245,158,11,0.15), rgba(245,158,11,0.05)); border: 1px solid rgba(245,158,11,0.2); color: #f59e0b; }}
    .tool-card:hover .tool-icon {{ transform: scale(1.08); }}

    .tool-icon svg {{ width: 26px; height: 26px; }}
    .tool-name {{ font-family: 'Playfair Display', Georgia, serif; font-size: 1.25rem; font-weight: 600; color: #f1f1f4; margin-bottom: 0.5rem; }}
    .tool-desc {{ font-size: 0.8125rem; color: #8b8fa3; line-height: 1.6; margin-bottom: 1.5rem; }}
    .tool-cta {{ display: flex; align-items: center; gap: 0.375rem; font-size: 0.8125rem; font-weight: 500; transition: gap 0.25s ease; }}
    .tool-card:hover .tool-cta {{ gap: 0.625rem; }}
    .tool-cta svg {{ width: 16px; height: 16px; }}
    .tracker .tool-cta {{ color: #4f7cff; }}
    .hermes .tool-cta {{ color: #2dd4bf; }}
    .daedalus .tool-cta {{ color: #f59e0b; }}

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

    _, col_tracker, sp1, col_hermes, sp2, col_daedalus, _ = st.columns([0.4, 2, 0.12, 2, 0.12, 2, 0.4])

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

    if access in ("both", "daedalus"):
        with col_daedalus:
            st.markdown("""
            <div class="tool-card daedalus">
                <div class="tool-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/></svg>
                </div>
                <div class="tool-name">Daedalus</div>
                <div class="tool-desc">Generate optimised imagery tile grids from AOI files or circle definitions.</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Open Daedalus  →", use_container_width=True, key="btn_daedalus", type="primary"):
                st.session_state["active_tool"] = "daedalus"
                log_activity(user["username"], "daedalus", "open", "Opened Daedalus")
                st.rerun()

    # ── Compact action row ──
    st.markdown("")
    if user["role"] == "admin":
        _, so_col, admin_col, _ = st.columns([5, 0.8, 0.8, 5])
    else:
        _, so_col, _ = st.columns([5, 0.8, 5])

    with so_col:
        if st.button("Sign Out", key="landing_logout", use_container_width=True):
            logout()

    if user["role"] == "admin":
        with admin_col:
            if st.button("Admin", use_container_width=True, key="btn_admin"):
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

# ── 1. Splash screen (every new session, before anything else) ──
if "_splash_done" not in st.session_state:
    st.set_page_config(page_title="Stone Harp Analytics", page_icon="🌐", layout="wide")
    _show_splash()
    st.session_state["_splash_done"] = True
    time.sleep(2)
    st.rerun()

# ── Page config (must be first Streamlit command after splash) ──
logged_in_now = "auth_user" in st.session_state
active_tool_now = st.session_state.get("active_tool")
if not logged_in_now:
    st.set_page_config(page_title="Sign In — Stone Harp Analytics", page_icon="🔐", layout="wide")
elif active_tool_now:
    st.set_page_config(page_title="Stone Harp Analytics", page_icon="🌐", layout="wide")
else:
    st.set_page_config(page_title="Stone Harp Analytics", page_icon="🌐", layout="wide")

# ── 2. Session timeout check ──
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

# ── 3. Cookie auto-login (Remember Me) ──
if "auth_user" not in st.session_state:
    try:
        ctrl = _get_cookie_controller()
        raw_token = ctrl.get(COOKIE_NAME)
        if raw_token:
            username = validate_remember_token(raw_token)
            if username:
                u = get_user(username)
                if u and u["is_active"]:
                    st.session_state["auth_user"] = u
                    st.session_state["_last_active"] = time.time()
                    st.session_state["_remember_token"] = raw_token
                    sid = log_login(username, "cookie-autologin")
                    st.session_state["auth_session_id"] = sid
                    log_activity(username, "app", "login", "Auto-login via Remember Me")
                    st.rerun()
    except Exception:
        pass

# ── 4. Route to the correct page ──
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

elif active_tool == "daedalus":
    pg = st.navigation({
        "": [st.Page(_back_to_home, title="Back to Home", icon="🏠")],
        "Daedalus": [st.Page("pages/4_Daedalus.py", title="Daedalus", icon="🗺️", default=True)],
    })

elif active_tool == "admin":
    pg = st.navigation({
        "": [st.Page(_back_to_home, title="Back to Home", icon="🏠")],
        "Admin": [st.Page("pages/3_Admin.py", title="Admin Panel", icon="⚙️", default=True)],
    })

else:
    pg = st.navigation([st.Page(_landing_page, title="Home", icon="🏠")], position="hidden")

pg.run()
