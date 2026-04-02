# UI/UX Overhaul — Stone Harp Analytics

**Date:** 2026-04-02
**Status:** Approved
**Scope:** Flash fix, login redesign, page transitions, landing rebalance, sidebar polish

## 1. Fix Flash on Load

**Problem:** Splash uses `layout="centered"`, then login/landing switch to `"wide"`. This config change causes a visible layout jump. The 2-cycle cookie check in `auth_ui.py` adds extra reruns.

**Changes:**
- **Unify page config:** Use `layout="wide"` for ALL states (splash, login, landing, tool pages). The login page centers its content via CSS within the wide canvas.
- **Reduce splash duration:** `time.sleep(3)` → `time.sleep(2)`.
- **Smoother rerun transitions:** Add a CSS rule that starts the app container at `opacity: 0` and fades in, so any intermediate states during reruns are invisible.

**Files:** `app.py` (lines ~725-735 page config block)

## 2. Login Page — Immersive Split Screen

**Layout:** Full-viewport split screen, no sidebar, no header.

**Left panel (~60%):**
- Dark background with subtle grid overlay and decorative concentric rings
- Radial gold glow behind center content
- Top-left: Logo icon + "Stone Harp Analytics" text
- Center: Large hero typography — "Intelligence" (white) / "Reimagined" (gold)
- Below hero: One-line tagline in muted text
- Bottom: Stat counters in a row — "3 Tools" (blue) / "24/7 Access" (teal) / "Secure" (amber)
- All content has staggered fade-up entry animations

**Right panel (~40%):**
- Slightly lighter dark surface with left border separator
- Vertically centered form:
  - "Welcome back" heading (Playfair Display)
  - "Sign in to continue" subtitle
  - Username input
  - Password input
  - Remember me checkbox
  - Sign In button (gold gradient)
- Slide-in-from-right entry animation

**Implementation approach:**
- Left panel: Pure HTML/CSS via `st.markdown(unsafe_allow_html=True)` in a `st.columns([1.2, 0.8])` left column
- Right panel: Streamlit widgets (`st.form`, `st.text_input`, etc.) in the right column
- The form uses `st.form("login_form")` exactly as today — just repositioned

**Files:** `app.py` (`_login_page()` function, ~lines 371-484)

## 3. Page Transitions

**Problem:** Pages "snap" in with brief white flash. The JS page-loader in `_load_css()` fights Streamlit and adds a hidden iframe.

**Changes:**
- **Remove JS page-loader:** Delete the entire `components.html(...)` block from `_load_css()`. It injects a script that tries to intercept navigation clicks but conflicts with Streamlit's own state management.
- **Refine CSS `pageIn`:** Increase duration from 0.5s to 0.6s. Keep the fade + slide-up + blur-clear effect.
- **Subtler exit dimming:** Change `.stApp[data-test-script-state="running"]` opacity from 0.6 to 0.85 — current dimming is too aggressive.
- **Keep gold shimmer bar:** The `shimmerBar` CSS animation during reruns stays as-is.

**Files:** `app.py` (`_load_css()`), `assets/style.css` (transition rules)

## 4. Landing Page — Equal 3-Card Row

**Layout:** Topbar + hero + 3 equal cards + footer.

**Changes:**
- **Column layout:** `st.columns([2, 2, 2])` with small padding columns on sides
- **Topbar integration:** Move Sign Out into the topbar right side (next to user badge), as a subtle text link. Move Admin Panel into topbar as a gear icon (admin-only). Eliminate the standalone button rows below the cards.
- **Card animations:** Staggered entry — 0.25s, 0.35s, 0.45s delay
- **Daedalus card:** Amber accent, grid icon (already implemented)

**Files:** `app.py` (`_landing_page()` function)

## 5. Sidebar Polish

**Changes in `assets/style.css`:**
- **Active page highlight:** Gold left border (3px) + slightly brighter background on the currently active sidebar nav link (`[aria-selected="true"]` or `[data-active="true"]`)
- **Hover transitions:** Increase from 0.15s to 0.25s for smoother feel
- **User info section:** Restyle `sidebar_user_info()` — gold avatar circle, role badge inline, cleaner typography
- **Back to Home link:** Style distinctly with a left arrow and muted color, separated from tool nav links

**Files:** `assets/style.css`, `auth/auth_ui.py` (`sidebar_user_info()`)

## Files Changed Summary

| File | Changes |
|------|---------|
| `app.py` | Unify page config to `wide`, rewrite `_login_page()` as split-screen, rewrite `_landing_page()` with topbar sign-out/admin, remove JS loader from `_load_css()`, reduce splash sleep |
| `assets/style.css` | Transition refinements (pageIn duration, exit dimming), sidebar active/hover styles, back-link styling |
| `auth/auth_ui.py` | Update `sidebar_user_info()` styling |
