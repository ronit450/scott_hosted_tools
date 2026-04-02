"""
Shared auth UI — login gate, logout button, session tracking.
Call `require_login()` at the top of every page.
"""
import time

import streamlit as st
from streamlit_cookies_controller import CookieController

from auth.auth_db import (
    verify_password, get_user, log_login, log_logout, log_activity,
    init_auth_db, check_rate_limit, record_failed_attempt, clear_attempts,
    create_remember_token, validate_remember_token, revoke_remember_token,
)

SESSION_TIMEOUT_SECONDS = 30 * 60   # 30 min inactivity timeout
COOKIE_NAME = "sha_remember_token"  # sha = Stone Harp Analytics


def _get_cookie_controller():
    """Return a CookieController instance (cached in session state)."""
    if "_cookie_ctrl" not in st.session_state:
        st.session_state["_cookie_ctrl"] = CookieController()
    return st.session_state["_cookie_ctrl"]


def _show_loading_screen():
    """Full-screen loader shown while waiting for cookies on first render cycle."""
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    .stApp > header { display: none !important; }
    .loader-wrap {
        position: fixed; inset: 0; z-index: 9999;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        background: #0a0e1a;
        gap: 1.5rem;
    }
    .loader-logo {
        width: 64px; height: 64px; border-radius: 16px;
        background: linear-gradient(135deg, rgba(192,168,126,0.15), rgba(192,168,126,0.05));
        border: 1px solid rgba(192,168,126,0.2);
        display: flex; align-items: center; justify-content: center;
        animation: pulse 1.8s ease-in-out infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 0.5; transform: scale(0.97); }
        50%       { opacity: 1;   transform: scale(1.03); box-shadow: 0 0 30px rgba(192,168,126,0.15); }
    }
    .loader-ring {
        width: 36px; height: 36px;
        border: 2px solid rgba(192,168,126,0.15);
        border-top-color: #c0a87e;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .loader-text {
        font-size: 0.8125rem; color: #5a5e72;
        font-family: -apple-system, sans-serif; letter-spacing: 0.04em;
    }
    </style>
    <div class="loader-wrap">
        <div class="loader-logo">
            <svg viewBox="0 0 40 44" width="32" height="32" fill="#c0a87e" xmlns="http://www.w3.org/2000/svg">
                <path d="M20 0C18 0 16.5 1.5 16.5 3.5V6C12.5 7.5 9 10 7 13.5C4.5 17.5 4 22 5.5 26C7 30 10.5 33 14.5 34.5V38H12V40H28V38H25.5V34.5C29.5 33 33 30 34.5 26C36 22 35.5 17.5 33 13.5C31 10 27.5 7.5 23.5 6V3.5C23.5 1.5 22 0 20 0Z"/>
            </svg>
        </div>
        <div class="loader-ring"></div>
        <div class="loader-text">Stone Harp Analytics</div>
    </div>
    """, unsafe_allow_html=True)


def _try_cookie_login():
    """
    Check for a remember-me cookie and auto-login if valid.
    On the very first render cycle cookies aren't available yet — returns None (pending).
    Returns True if auto-login succeeded, False if no valid cookie, None if not ready yet.
    """
    ctrl = _get_cookie_controller()

    # First render: CookieController hasn't received cookies from browser yet.
    # Mark that we've started checking so next cycle we know it's a real result.
    if "_cookies_ready" not in st.session_state:
        st.session_state["_cookies_ready"] = False
        return None  # not ready — show loader instead of login form

    raw_token = ctrl.get(COOKIE_NAME)
    if not raw_token:
        return False

    username = validate_remember_token(raw_token)
    if not username:
        ctrl.remove(COOKIE_NAME)
        return False

    user = get_user(username)
    if not user or not user["is_active"]:
        ctrl.remove(COOKIE_NAME)
        return False

    # Auto-login
    st.session_state["auth_user"] = user
    st.session_state["_last_active"] = time.time()
    st.session_state["_remember_token"] = raw_token
    sid = log_login(username, "cookie-autologin")
    st.session_state["auth_session_id"] = sid
    log_activity(username, "app", "login", "Auto-login via Remember Me")
    return True


def _check_session_timeout():
    last_active = st.session_state.get("_last_active")
    if last_active is None:
        return False
    return time.time() - last_active > SESSION_TIMEOUT_SECONDS


def _touch_session():
    st.session_state["_last_active"] = time.time()


def require_login(tool: str = "app"):
    """
    Blocks the page until the user is authenticated.
    Returns the user dict if logged in, otherwise shows login form and stops.
    """
    init_auth_db()

    # Session timeout
    if "auth_user" in st.session_state and _check_session_timeout():
        user = st.session_state["auth_user"]
        log_activity(user["username"], "app", "timeout", "Session expired due to inactivity")
        sid = st.session_state.get("auth_session_id")
        if sid:
            log_logout(sid)
        # Don't revoke remember token on timeout — let them auto-login again via cookie
        for key in ["auth_user", "auth_session_id", "_last_active"]:
            st.session_state.pop(key, None)
        st.warning("Your session expired due to inactivity. Signing you back in...")
        st.rerun()

    # Not logged in — try cookie first, then show form
    if "auth_user" not in st.session_state:
        result = _try_cookie_login()
        if result is None:
            # First render cycle — cookies not ready yet, show loader
            st.session_state["_cookies_ready"] = True
            _show_loading_screen()
            st.rerun()
        elif result is True:
            st.rerun()
        else:
            _show_login_form()
        st.stop()

    user = st.session_state["auth_user"]

    # Check tool access
    access = user.get("tool_access", "all")
    # Resolve which tools the user can access
    allowed_tools = set()
    if access in ("all", "both"):
        allowed_tools = {"tracker", "hermes", "daedalus"}
    elif access == "hermes_daedalus":
        allowed_tools = {"hermes", "daedalus"}
    else:
        allowed_tools = {access}  # legacy single-tool values
    if tool not in ("admin", "app") and tool not in allowed_tools:
        st.error(f"You don't have access to **{tool}**. Contact your admin.")
        _logout_button()
        st.stop()

    _touch_session()
    return user


def _show_login_form():
    st.markdown("""
        <style>
        .login-wrap { max-width: 420px; margin: 80px auto 0 auto; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## Stone Harp Analytics")
        st.markdown("##### Sign in to continue")
        st.markdown("")

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            remember_me = st.checkbox("Remember me for 30 days", value=True)
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

            if remember_me:
                raw_token = create_remember_token(username)
                ctrl = _get_cookie_controller()
                ctrl.set(COOKIE_NAME, raw_token, max_age=30 * 24 * 3600)
                st.session_state["_remember_token"] = raw_token

            st.rerun()
        else:
            record_failed_attempt(username.lower())
            from auth.auth_db import _login_attempts, MAX_ATTEMPTS, LOCKOUT_SECONDS
            remaining = MAX_ATTEMPTS - len(_login_attempts.get(username.lower(), []))
            if remaining > 0:
                st.error(f"Invalid username or password. {remaining} attempt(s) remaining.")
            else:
                st.error(f"Account locked for {LOCKOUT_SECONDS // 60} minutes due to too many failed attempts.")


def logout():
    """Log out and clear the remember-me cookie."""
    user = st.session_state.get("auth_user")
    sid = st.session_state.get("auth_session_id")
    raw_token = st.session_state.get("_remember_token")

    if user:
        log_activity(user["username"], "app", "logout", "Signed out")
    if sid:
        log_logout(sid)
    if raw_token:
        revoke_remember_token(raw_token)
        try:
            ctrl = _get_cookie_controller()
            ctrl.remove(COOKIE_NAME)
        except Exception:
            pass

    for key in ["auth_user", "auth_session_id", "_last_active", "_remember_token", "_cookie_ctrl"]:
        st.session_state.pop(key, None)
    st.rerun()


def _logout_button():
    if st.button("Sign Out", key="_global_logout"):
        logout()


def sidebar_user_info():
    """Show logged-in user info + logout button in sidebar."""
    user = st.session_state.get("auth_user")
    if not user:
        return
    initial = user["name"][0].upper() if user.get("name") else "U"
    role_label = "Admin" if user["role"] == "admin" else "User"
    role_color = "#ef4444" if user["role"] == "admin" else "#22c55e"

    with st.sidebar:
        st.markdown("---")
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.75rem;">
            <div style="width:32px;height:32px;border-radius:50%;
                        background:linear-gradient(135deg,#c0a87e,#a08a5c);
                        display:flex;align-items:center;justify-content:center;
                        font-size:0.75rem;font-weight:600;color:#0a0e1a;flex-shrink:0;">{initial}</div>
            <div style="line-height:1.3;overflow:hidden;">
                <div style="font-size:0.8125rem;font-weight:500;color:#f1f1f4;
                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{user['name']}</div>
                <div style="display:flex;align-items:center;gap:0.375rem;margin-top:0.125rem;">
                    <span style="width:6px;height:6px;border-radius:50%;background:{role_color};display:inline-block;"></span>
                    <span style="font-size:0.6875rem;color:#8b8fa3;">{role_label}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Sign Out", key="_sidebar_logout", use_container_width=True):
            logout()
