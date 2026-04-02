# UI/UX Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the flash-on-load, redesign login as immersive split-screen, improve page transitions, rebalance landing page for 3 tools, and polish sidebar styles.

**Architecture:** All changes are in 3 files — `app.py` (routing, login, landing page functions), `assets/style.css` (transition and sidebar styles), and `auth/auth_ui.py` (sidebar user info). No new files, no new dependencies.

**Tech Stack:** Streamlit, HTML/CSS (injected via `st.markdown(unsafe_allow_html=True)`), Python

---

## File Map

| File | Role | Changes |
|------|------|---------|
| `app.py` | Central router + page functions | Remove JS loader from `_load_css()`, unify page config to `wide`, rewrite `_login_page()`, rewrite `_landing_page()`, reduce splash sleep |
| `assets/style.css` | Global CSS overrides | Refine `pageIn` animation, soften exit dimming, add sidebar active/hover/back-link styles |
| `auth/auth_ui.py` | Auth UI components | Restyle `sidebar_user_info()` with gold avatar and role badge |

---

### Task 1: Remove JS Page-Loader from `_load_css()`

**Files:**
- Modify: `app.py:37-135` (`_load_css()` function)

The JS `components.html(...)` injects a hidden iframe that fights Streamlit's own rerun mechanism. The CSS-only shimmer bar in `style.css` already handles transition indication.

- [ ] **Step 1: Replace `_load_css()` — remove the JS loader**

In `app.py`, replace the entire `_load_css()` function (lines 37-135) with:

```python
def _load_css():
    """Load the shared style.css."""
    css_path = os.path.join(ASSETS, "style.css")
    if os.path.exists(css_path):
        css = Path(css_path).read_text()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
```

This removes the `import streamlit.components.v1 as components` and the entire `components.html(...)` block (the JS page-loader script).

- [ ] **Step 2: Verify the app loads without errors**

Run: `conda run -n rk_yolo python -m streamlit run app.py`

Expected: App loads normally. No hidden iframe in the DOM. The gold shimmer bar still appears during reruns (driven by CSS in `style.css`).

- [ ] **Step 3: Commit**

```bash
cd scott_hosted_tools
git add app.py
git commit -m "Remove JS page-loader from _load_css, use CSS-only transitions"
```

---

### Task 2: Unify Page Config + Reduce Splash

**Files:**
- Modify: `app.py:724-735` (splash + page config block)

The flash-on-load happens because `set_page_config(layout="centered")` is used for splash/login, then `layout="wide"` for landing/tools. Streamlit can't change layout without a full page reload, causing a visible jump.

- [ ] **Step 1: Change splash page config to `wide`**

In `app.py`, find the splash block (around line 724):

```python
if "_splash_done" not in st.session_state:
    st.set_page_config(page_title="Stone Harp Analytics", page_icon="🌐", layout="centered")
    _show_splash()
    st.session_state["_splash_done"] = True
    time.sleep(3)
    st.rerun()
```

Replace with:

```python
if "_splash_done" not in st.session_state:
    st.set_page_config(page_title="Stone Harp Analytics", page_icon="🌐", layout="wide")
    _show_splash()
    st.session_state["_splash_done"] = True
    time.sleep(2)
    st.rerun()
```

Changes: `layout="centered"` → `layout="wide"`, `time.sleep(3)` → `time.sleep(2)`.

- [ ] **Step 2: Change login page config to `wide`**

Find the page config block (around line 732-735):

```python
if not logged_in_now:
    st.set_page_config(page_title="Sign In — Stone Harp Analytics", page_icon="🔐", layout="centered")
```

Replace with:

```python
if not logged_in_now:
    st.set_page_config(page_title="Sign In — Stone Harp Analytics", page_icon="🔐", layout="wide")
```

- [ ] **Step 3: Change the collapsed sidebar config to `wide` without `initial_sidebar_state`**

Find (around line 721):

```python
else:
    st.set_page_config(page_title="Stone Harp Analytics", page_icon="🌐", layout="wide", initial_sidebar_state="collapsed")
```

Replace with:

```python
else:
    st.set_page_config(page_title="Stone Harp Analytics", page_icon="🌐", layout="wide")
```

The sidebar is already hidden via CSS on the landing page, so `initial_sidebar_state` is unnecessary and can cause a brief sidebar flash.

- [ ] **Step 4: Verify no layout flashing**

Run the app. Navigate: splash → login → landing. There should be no layout jump between pages.

- [ ] **Step 5: Commit**

```bash
cd scott_hosted_tools
git add app.py
git commit -m "Unify page config to layout=wide, reduce splash to 2s"
```

---

### Task 3: Refine CSS Transitions

**Files:**
- Modify: `assets/style.css:35-43` (pageIn animation), `assets/style.css:581-606` (rerun dimming)

- [ ] **Step 1: Update `pageIn` animation duration and easing**

In `assets/style.css`, find the `pageIn` block (around line 35):

```css
[data-testid="stAppViewBlockContainer"] {
  animation: pageIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(18px); filter: blur(4px); }
  to   { opacity: 1; transform: translateY(0); filter: blur(0); }
}
```

Replace with:

```css
[data-testid="stAppViewBlockContainer"] {
  animation: pageIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(14px); filter: blur(3px); }
  to   { opacity: 1; transform: translateY(0); filter: blur(0); }
}
```

Changes: 0.5s → 0.6s, translateY 18px → 14px (subtler), blur 4px → 3px.

- [ ] **Step 2: Soften exit dimming during reruns**

Find the rerun dimming rule (around line 603):

```css
.stApp[data-test-script-state="running"] [data-testid="stAppViewBlockContainer"] {
  opacity: 0.6;
  transition: opacity 0.2s ease;
}
```

Replace with:

```css
.stApp[data-test-script-state="running"] [data-testid="stAppViewBlockContainer"] {
  opacity: 0.85;
  transition: opacity 0.15s ease;
}
```

Changes: opacity 0.6 → 0.85 (much subtler), transition 0.2s → 0.15s (snappier).

- [ ] **Step 3: Commit**

```bash
cd scott_hosted_tools
git add assets/style.css
git commit -m "Refine page transitions: slower entry, subtler exit dimming"
```

---

### Task 4: Rewrite Login Page as Immersive Split-Screen

**Files:**
- Modify: `app.py:371-484` (`_login_page()` function)

This is the biggest change. Replace the centered-card login with a full-viewport split-screen: immersive branding left, form right.

- [ ] **Step 1: Replace `_login_page()` function**

In `app.py`, replace the entire `_login_page()` function (from `def _login_page():` through the closing `st.markdown('<div class="login-footer">...</div>')` line) with the following:

```python
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
    /* Remove default block padding for login */
    .block-container { padding: 0 !important; max-width: 100% !important; }

    /* ── Split-screen animations ── */
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

    /* ── Left branding panel ── */
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

    /* ── Right form panel ── */
    .login-form-panel {
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: 3rem 2.5rem;
        animation: slideInRight 0.7s cubic-bezier(0.16, 1, 0.3, 1) 0.3s both;
    }
    .login-form-panel h2 {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 1.5rem; font-weight: 600; color: #f1f1f4;
        margin-bottom: 0.25rem;
    }
    .login-form-panel .subtitle {
        font-size: 0.875rem; color: #8b8fa3; margin-bottom: 2rem;
    }
    .login-form-panel .footer-text {
        text-align: center; font-size: 0.75rem; color: #5a5e72; margin-top: 1.5rem;
    }
    .login-form-panel .footer-text span { color: #c0a87e; opacity: 0.6; }

    /* Override form container style for login */
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
        st.markdown("""
        <div class="login-form-panel">
            <h2>Welcome back</h2>
            <p class="subtitle">Sign in to continue</p>
        </div>
        """, unsafe_allow_html=True)

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
```

- [ ] **Step 2: Test the login page**

Run the app, navigate to the login page. Verify:
- Left panel shows branding with logo, hero text, stats
- Right panel shows the form
- Animations play on entry
- Login form works (username/password/submit)
- No layout flash

- [ ] **Step 3: Commit**

```bash
cd scott_hosted_tools
git add app.py
git commit -m "Redesign login as immersive split-screen with branding panel"
```

---

### Task 5: Rewrite Landing Page with Topbar Integration

**Files:**
- Modify: `app.py:486-711` (`_landing_page()` function)

Move Sign Out + Admin Panel into the topbar. Rebalance 3 tool cards.

- [ ] **Step 1: Replace the Sign Out and Admin button sections**

In `_landing_page()`, find the section after the tool cards (after the `col_daedalus` block closes). Replace from `# Sign out button` through `st.markdown('<div class="page-footer">...` with:

```python
    # Footer
    st.markdown('<div class="page-footer">Stone Harp Analytics &middot; v1.0</div>', unsafe_allow_html=True)
```

- [ ] **Step 2: Move Sign Out + Admin into the topbar HTML**

In `_landing_page()`, find the topbar `<header>` HTML block. Replace the `<div class="topbar-right">` section. The current code is:

```python
        <div class="topbar-right">
            <div class="user-badge">
                <div class="user-avatar">{initial}</div>
                <div style="line-height:1.2;">
                    <div class="user-name">{user["name"]}</div>
                    <div class="user-role">{role_label}</div>
                </div>
            </div>
        </div>
```

Replace with:

```python
        <div class="topbar-right">
            {"<a href='#' id='admin-link' style=" + '"font-size:0.75rem;color:#5a5e72;text-decoration:none;transition:color 0.2s;margin-right:0.5rem;"' + " onmouseover=" + '"this.style.color=`#c0a87e`"' + " onmouseout=" + '"this.style.color=`#5a5e72`"' + ">Admin</a>" if user["role"] == "admin" else ""}
            <div class="user-badge">
                <div class="user-avatar">{initial}</div>
                <div style="line-height:1.2;">
                    <div class="user-name">{user["name"]}</div>
                    <div class="user-role">{role_label}</div>
                </div>
            </div>
        </div>
```

Note: The Admin link is decorative HTML — the actual button still needs to be a Streamlit button for state changes. So instead of the HTML approach, keep the admin/signout as Streamlit buttons but put them in a small column row with better styling.

**Actually — simpler approach:** Keep the Streamlit buttons but restyle them into a compact row right after the topbar:

Replace the entire section from `# Sign out button` through `st.markdown('<div class="page-footer">...` with:

```python
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
```

- [ ] **Step 3: Test the landing page**

Verify:
- 3 tool cards display in a balanced row
- Sign Out and Admin are compact, not taking up full width
- Clicking tool cards navigates correctly
- Admin button only shows for admin users

- [ ] **Step 4: Commit**

```bash
cd scott_hosted_tools
git add app.py
git commit -m "Rebalance landing page, compact sign-out and admin buttons"
```

---

### Task 6: Sidebar Polish (CSS)

**Files:**
- Modify: `assets/style.css:277-343` (sidebar section)

- [ ] **Step 1: Add active page highlight and improved hover states**

In `assets/style.css`, find the sidebar section (around line 277). After the existing sidebar rules, add these new rules (before the `/* ── Selectbox, multiselect ──` section):

```css
/* ── Sidebar nav link — active page highlight ── */
section[data-testid="stSidebar"] nav a[aria-current="page"],
section[data-testid="stSidebar"] nav a[data-active="true"] {
  background: rgba(192, 168, 126, 0.08) !important;
  border-left: 3px solid var(--gold-primary) !important;
  border-radius: 0 10px 10px 0 !important;
  color: var(--text-primary) !important;
  font-weight: 500 !important;
}

/* ── Sidebar nav link — hover ── */
section[data-testid="stSidebar"] nav a {
  transition: all 0.25s ease !important;
  border-left: 3px solid transparent !important;
  border-radius: 0 10px 10px 0 !important;
}

section[data-testid="stSidebar"] nav a:hover {
  background: rgba(255, 255, 255, 0.04) !important;
  border-left-color: rgba(192, 168, 126, 0.3) !important;
  color: var(--text-primary) !important;
}

/* ── Back to Home link — distinct styling ── */
section[data-testid="stSidebar"] nav a:first-child {
  color: var(--text-muted) !important;
  font-size: 0.8125rem !important;
  margin-bottom: 0.5rem !important;
  border-bottom: 1px solid var(--border-subtle) !important;
  padding-bottom: 0.75rem !important;
  border-left: none !important;
  border-radius: 10px !important;
}

section[data-testid="stSidebar"] nav a:first-child:hover {
  color: var(--gold-primary) !important;
  background: rgba(192, 168, 126, 0.05) !important;
  border-left: none !important;
}
```

- [ ] **Step 2: Commit**

```bash
cd scott_hosted_tools
git add assets/style.css
git commit -m "Polish sidebar: active page highlight, hover transitions, back-link styling"
```

---

### Task 7: Restyle Sidebar User Info

**Files:**
- Modify: `auth/auth_ui.py:257-269` (`sidebar_user_info()` function)

- [ ] **Step 1: Replace `sidebar_user_info()` with styled version**

In `auth/auth_ui.py`, replace the `sidebar_user_info()` function with:

```python
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
```

- [ ] **Step 2: Test sidebar on a tool page**

Open the Tracker or Hermes tool. Verify the sidebar shows the gold avatar, user name, role badge with colored dot, and Sign Out button.

- [ ] **Step 3: Commit**

```bash
cd scott_hosted_tools
git add auth/auth_ui.py
git commit -m "Restyle sidebar user info with gold avatar and role badge"
```

---

### Task 8: Final Integration Test

- [ ] **Step 1: Full flow test**

Run: `conda run -n rk_yolo python -m streamlit run app.py`

Test the complete flow:
1. Fresh load → splash (2s) → login (no flash/jump)
2. Login page: immersive split-screen, branding left, form right
3. Sign in → landing page (3 tool cards, balanced row)
4. Click a tool → tool page loads with smooth fade-in, gold shimmer bar during transition
5. Sidebar: active page highlighted, hover states smooth, user info styled
6. Back to Home → landing page
7. Sign Out → back to login

- [ ] **Step 2: Fix any visual issues found during testing**

Adjust CSS values (spacing, colors, animation timing) as needed.

- [ ] **Step 3: Final commit**

```bash
cd scott_hosted_tools
git add -A
git commit -m "UI/UX overhaul: split-screen login, transitions, landing rebalance, sidebar polish"
```
