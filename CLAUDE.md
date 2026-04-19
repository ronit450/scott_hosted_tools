# Stone Harp Analytics — Hosted App

## Project Overview

Multi-tool Streamlit web app for Stone Harp Analytics, deployed on Render via GitHub (`ronit450/scott_hosted_tools`).

**Tools inside the app:**

* **Dashboard Tracker** — Contracts, personnel, imagery orders, reports
* **Hermes** — Geospatial data converter (CSV/Excel → KML/SHP/GeoJSON)
* **Daedalus** — AOI Tiling Engine (upload AOI file or define circle → generate optimised tile grids with multiple strategies)
* **Admin Panel** — User management, sessions, activity log, backups, password changes

## Architecture

### Routing

* `app.py` is the central router using `st.navigation()` + `st.Page()`
* Only `app.py` calls `st.set_page_config()` — individual pages must NOT call it (causes flash errors)
* Login → Landing (tool picker) → Tool pages via `st.session_state["active_tool"]`
* Navigation uses dict-based sections for tracker (7 pages), single pages for hermes/daedalus/admin

### Auth System (`auth/`)

* `auth_db.py` — SQLite (`auth.db`): users, sessions, activity log, remember tokens
* `auth_ui.py` — Login gate, logout, sidebar user info, cookie controller
* Passwords: **bcrypt** with SHA-256 legacy fallback + auto-upgrade
* Rate limiting: 5 attempts, 5-min lockout (in-memory)
* Session timeout: 30 min inactivity
* Remember Me: 30-day browser cookie via `streamlit-cookies-controller`, token hash stored in DB
  * CookieController needs 2 render cycles to read cookies (cycle 1: mount, cycle 2: read)
  * Uses `_cookie_check_done` flag pattern in `app.py` for auto-login
* `tool_access` field: `'all'` (all 3 tools) or `'hermes_daedalus'` (Hermes + Daedalus only)

### Database

* `db/database.py` — tracker.db (projects, imagery, contracts, etc.)
* `db/seed_data.py` — Initial seed data
* Both DBs auto-detect data dir: `DATA_DIR` env var → `/data` if exists → local `data/` fallback

### Backups (`auth/backup.py`)

* Auto-backup every 8 hours, 15-day retention
* Manual backup + upload/restore + download from Admin panel
* Uses SQLite backup API for safe copies
* Same auto-detect data dir pattern as databases

### Daedalus (`image_tiling/`)

* `daedalus_core.py` — Main tiling engine: `run_tiling()` entrypoint
  * Supports circle AOI (center + radius) or file-based AOIs (KML/KMZ/GeoJSON/SHP/GPKG)
  * Custom KML/KMZ parser (no Fiona/GDAL dependency for KML)
  * Generates 5 strategies: balanced, full, minimal, max_coverage, compact
  * Outputs per-strategy CSV (centerpoints), GeoJSON (tiles + AOI), combined KML, strategy summary CSV
  * Tile size supports rectangular: `tile_width_km` x `tile_height_km`
* `daedalus_gui.py` — Original Tkinter desktop GUI (not used in web app)
* `tiler_core.py` — Older refactored core (skeleton only, not used)
* `tiling_v1` — Original v1 script (reference only)
* Dependencies: shapely, pyproj, geopandas

### Hermes (`hermes_core/`)

* Geospatial data converter with custom output filename field
* Outputs zipped results

### Deployment

* **Render** — Starter plan, 5GB persistent disk mounted at `/data`
* `render.yaml` has full config
* Push to `main` branch → auto-deploy
* IMPORTANT: Render persistent disk must be attached via Dashboard. Env vars in `render.yaml` only apply via Blueprint deploy, not Dashboard creation.
* Data dir auto-detection: code checks `DATA_DIR` env var first, then `/data` directory existence, then local `data/` fallback

## Key Conventions

* All changes go in `scott_hosted_tools/` — never in `hosted_app/` (old, deprecated copy)
* CSS lives in `assets/style.css` — shared across all pages via `_load_css()`
* Material icon text leaks are hidden globally via CSS (common Streamlit issue)
* All Streamlit chrome is hidden via CSS: deploy button, toolbar, hamburger menu, footer, sidebar logos
* The splash screen uses a 2-cycle approach: cycle 1 shows splash + instantiates CookieController, cycle 2 checks cookies

### Streamlit Gotchas

* `st.markdown(unsafe_allow_html=True)` — 4+ space indentation causes code block rendering. Use string concatenation with parentheses instead of f-string triple-quotes.
* `st.columns()` cannot support full-viewport-height custom backgrounds — Streamlit DOM constraints
* `gap="none"` not supported in Streamlit 1.55.0 — use `gap="small"`
* CookieController needs 2 render cycles to read cookies

## UI Design

### Login Page
* Centered card layout (420px max-width) with PNG logo (`assets/stoneharp_logo.png`)
* Gold-themed button, stats row, Playfair Display font for heading
* Sidebar and header hidden on login

### Landing Page
* Dark premium UI with 3 tool cards (Tracker, Hermes, Daedalus)
* Topbar with PNG logo, user greeting, Sign Out + Admin Panel buttons
* Cards shown based on user's `tool_access` permission

### Sidebar
* Quick Stats in tracker pages via `utils/helpers.py:sidebar_quick_stats()`
* User info + sign out via `auth/auth_ui.py:sidebar_user_info()`
* No logo in sidebar (removed)

## Running Locally

```shell
cd scott_hosted_tools
pip install -r requirements.txt
streamlit run app.py
```

## File Structure

```
scott_hosted_tools/
  app.py              # Central router + login + landing + splash screen
  render.yaml         # Render deployment config
  requirements.txt
  assets/
    style.css         # All CSS overrides (chrome hiding, sidebar, etc.)
    stoneharp_logo.png  # PNG logo used on login + landing pages
  auth/
    auth_db.py        # Auth database + user CRUD + remember tokens
    auth_ui.py        # Login UI components + cookie logic + sidebar user info
    backup.py         # Backup/restore system
  db/
    database.py       # Tracker database + migrations
    schema.sql        # DB schema
    seed_data.py      # Seed data
  pages/
    Tracker_1_Dashboard.py   # Dashboard overview
    Tracker_2_Projects.py    # Project management
    Tracker_3_Imagery_Catalog.py  # Imagery catalog
    Tracker_4_Imagery_Orders.py   # Imagery orders
    Tracker_5_Day_Rate_Tracker.py # Day rate tracking
    Tracker_6_Reports.py    # Reports
    Tracker_7_Settings.py   # Settings
    2_Hermes.py       # Hermes converter (custom filename + zip download)
    3_Admin.py        # Admin panel (users, sessions, activity, backups)
    4_Daedalus.py     # Daedalus AOI tiling (rectangular tiles, custom filename)
  image_tiling/
    daedalus_core.py  # Tiling engine core (run_tiling API, rectangular support)
    daedalus_gui.py   # Desktop GUI (Tkinter, not used in web)
    tiler_core.py     # Old core skeleton (unused)
    tiling_v1/        # Original v1 script (reference)
  hermes_core/        # Hermes conversion logic
  utils/
    helpers.py        # sidebar_quick_stats(), shared utilities
  data/               # Local DB storage (gitignored)
```
