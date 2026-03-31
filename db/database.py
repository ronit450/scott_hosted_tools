import sqlite3
import threading
from pathlib import Path

import os as _os
# Use DATA_DIR env var on Render (persistent disk); fall back to local data/ folder
DB_DIR = Path(_os.environ.get("DATA_DIR", str(Path(__file__).parent.parent / "data")))
DB_PATH = DB_DIR / "tracker.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Thread-local storage for connection reuse — one persistent connection per
# thread instead of opening/closing on every query.
_local = threading.local()


def get_connection():
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")  # check connection is still alive
            return conn
        except Exception:
            conn = None
    DB_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _local.conn = conn
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    # Migrate: add new imagery columns if missing
    cols = [r[1] for r in conn.execute("PRAGMA table_info(imagery_orders)").fetchall()]
    if "shots_requested" not in cols:
        conn.execute("ALTER TABLE imagery_orders ADD COLUMN shots_requested INTEGER DEFAULT 0")
    if "cost_per_shot" not in cols:
        conn.execute("ALTER TABLE imagery_orders ADD COLUMN cost_per_shot REAL NOT NULL DEFAULT 0")
    if "charge_per_shot" not in cols:
        conn.execute("ALTER TABLE imagery_orders ADD COLUMN charge_per_shot REAL NOT NULL DEFAULT 0")
    # Migrate: create pws_day_rate table if missing
    conn.execute("""CREATE TABLE IF NOT EXISTS pws_day_rate (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        pws_number        TEXT    NOT NULL UNIQUE,
        pws_name          TEXT    NOT NULL DEFAULT '',
        total_exercised   INTEGER NOT NULL DEFAULT 0,
        start_date        TEXT,
        end_date          TEXT,
        updated_at        TEXT    DEFAULT (datetime('now'))
    )""")
    # Migrate: add new pws_day_rate columns if missing
    pws_cols = [r[1] for r in conn.execute("PRAGMA table_info(pws_day_rate)").fetchall()]
    if "pws_name" not in pws_cols:
        conn.execute("ALTER TABLE pws_day_rate ADD COLUMN pws_name TEXT NOT NULL DEFAULT ''")
    if "start_date" not in pws_cols:
        conn.execute("ALTER TABLE pws_day_rate ADD COLUMN start_date TEXT")
    if "end_date" not in pws_cols:
        conn.execute("ALTER TABLE pws_day_rate ADD COLUMN end_date TEXT")
    # Ensure indices exist on foreign keys (safe to re-run)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_labor_project_id  ON labor_entries(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_labor_job_code_id ON labor_entries(job_code_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_project_id ON imagery_orders(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_catalog_id ON imagery_orders(catalog_id)")
    conn.commit()


def query(sql, params=(), fetchone=False):
    conn = get_connection()
    cur = conn.execute(sql, params)
    if fetchone:
        row = cur.fetchone()
        return dict(row) if row else None
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def execute(sql, params=()):
    conn = get_connection()
    cur = conn.execute(sql, params)
    conn.commit()
    return cur.lastrowid


def execute_many(sql, params_list):
    conn = get_connection()
    conn.executemany(sql, params_list)
    conn.commit()
