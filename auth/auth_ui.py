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


def _try_cookie_login():
    """
    Check for a remember-me cookie and auto-login if valid.
    Returns True if auto-login succeeded.
    """
    ctrl = _get_cookie_controller()
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
        if _try_cookie_login():
            st.rerun()
        _show_login_form()
        st.stop()

    user = st.session_state["auth_user"]

    # Check tool access
    access = user.get("tool_access", "both")
    if tool not in ("admin", "app") and access != "both" and access != tool:
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
    with st.sidebar:
        st.markdown("---")
        role_badge = "🔴 Admin" if user["role"] == "admin" else "🟢 User"
        st.markdown(f"**{user['name']}** &nbsp; `{role_badge}`", unsafe_allow_html=True)
        st.caption(f"@{user['username']}")
        if st.button("Sign Out", key="_sidebar_logout", use_container_width=True):
            logout()
