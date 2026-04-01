# Stone Harp Analytics — Hosted App

## Project Overview
Multi-tool Streamlit web app for Stone Harp Analytics, deployed on Render via GitHub (`ronit450/scott_hosted_tools`).

**Tools inside the app:**
- **Dashboard Tracker** — Contracts, personnel, imagery orders, reports
- **Hermes** — Geospatial data converter (CSV/Excel → KML/SHP/GeoJSON)
- **Admin Panel** — User management, sessions, activity log, backups, password changes

## Architecture

### Routing
- `app.py` is the central router using `st.navigation()` + `st.Page()`
- Only `app.py` calls `st.set_page_config()` — individual pages must NOT call it (causes flash errors)
- Login → Landing (tool picker) → Tool pages via `st.session_state["active_tool"]`

### Auth System (`auth/`)
- `auth_db.py` — SQLite (`auth.db`): users, sessions, activity log, remember tokens
- `auth_ui.py` — Login gate, logout, sidebar user info, cookie controller
- Passwords: **bcrypt** with SHA-256 legacy fallback + auto-upgrade
- Rate limiting: 5 attempts, 5-min lockout (in-memory)
- Session timeout: 30 min inactivity
- Remember Me: 30-day browser cookie via `streamlit-cookies-controller`, token hash stored in DB

### Database
- `db/database.py` — tracker.db (projects, imagery, contracts, etc.)
- `db/seed_data.py` — Initial seed data
- Both DBs use `DATA_DIR` env var (`/data` on Render, local `data/` folder in dev)

### Backups (`auth/backup.py`)
- Auto-backup every 8 hours, 15-day retention
- Manual backup + upload/restore from Admin panel
- Uses SQLite backup API for safe copies

### Deployment
- **Render** — Starter plan, 5GB persistent disk at `/data`
- `render.yaml` has full config
- Push to `main` branch → auto-deploy

## Key Conventions
- All changes go in `scott_hosted_tools/` — never in `hosted_app/` (old, deprecated copy)
- CSS lives in `assets/style.css` — shared across all pages via `_load_css()`
- Material icon text leaks are hidden globally via CSS (common Streamlit issue)
- The splash screen uses a 2-cycle approach: cycle 1 shows splash + instantiates CookieController, cycle 2 checks cookies

## Running Locally
```bash
cd scott_hosted_tools
pip install -r requirements.txt
streamlit run app.py
```

## File Structure
```
scott_hosted_tools/
  app.py              # Central router + login + landing page
  render.yaml         # Render deployment config
  requirements.txt
  assets/style.css    # All CSS overrides
  auth/
    auth_db.py        # Auth database + user CRUD + remember tokens
    auth_ui.py        # Login UI components + cookie logic
    backup.py         # Backup/restore system
  db/
    database.py       # Tracker database
    seed_data.py      # Seed data
  pages/
    Tracker_1-7.py    # Dashboard tracker pages
    2_Hermes.py       # Hermes converter
    3_Admin.py        # Admin panel
  hermes_core/        # Hermes conversion logic
  utils/              # Shared utilities
  data/               # Local DB storage (gitignored)
```
