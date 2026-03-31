"""
Auth database — users, sessions, activity log.
Stored in hosted_app/data/auth.db (separate from tracker.db).
"""
import hashlib
import os
import sqlite3
import time
from datetime import datetime

import bcrypt

# Use DATA_DIR env var on Render (persistent disk); fall back to local data/ folder
_data_dir = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
DB_PATH = os.path.join(_data_dir, "auth.db")


def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_auth_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'user',  -- 'admin' or 'user'
            tool_access TEXT NOT NULL DEFAULT 'both',  -- 'tracker', 'hermes', 'both'
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            last_login  TEXT
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL,
            login_at    TEXT NOT NULL DEFAULT (datetime('now')),
            logout_at   TEXT,
            duration_s  INTEGER,
            ip_address  TEXT
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL,
            tool        TEXT NOT NULL,  -- 'tracker', 'hermes', 'admin'
            action      TEXT NOT NULL,
            detail      TEXT,
            logged_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # Seed default admin if no users exist
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing == 0:
        conn.execute("""
            INSERT INTO users (username, name, password_hash, role, tool_access)
            VALUES (?, ?, ?, 'admin', 'both')
        """, ("admin", "Admin", _hash("admin123")))
        conn.commit()
    conn.close()


def _hash(password: str) -> str:
    """Hash password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_hash(password: str, hashed: str) -> bool:
    """Verify password against hash. Supports both bcrypt and legacy SHA-256."""
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        return bcrypt.checkpw(password.encode(), hashed.encode())
    # Legacy SHA-256 fallback — matches old passwords until they're updated
    return hashed == hashlib.sha256(password.encode()).hexdigest()


# ── Rate limiting ─────────────────────────────────────────────

# In-memory store: { username_or_ip: [timestamp, timestamp, ...] }
_login_attempts: dict[str, list[float]] = {}
MAX_ATTEMPTS = 5          # max failed attempts
LOCKOUT_SECONDS = 300     # 5 minute lockout


def check_rate_limit(key: str) -> tuple[bool, int]:
    """
    Returns (allowed, seconds_remaining).
    If allowed is False, the user is locked out for seconds_remaining.
    """
    now = time.time()
    attempts = _login_attempts.get(key, [])
    # Prune old attempts outside the lockout window
    attempts = [t for t in attempts if now - t < LOCKOUT_SECONDS]
    _login_attempts[key] = attempts

    if len(attempts) >= MAX_ATTEMPTS:
        remaining = int(LOCKOUT_SECONDS - (now - attempts[0]))
        return False, max(remaining, 1)
    return True, 0


def record_failed_attempt(key: str):
    """Record a failed login attempt."""
    _login_attempts.setdefault(key, []).append(time.time())


def clear_attempts(key: str):
    """Clear failed attempts after successful login."""
    _login_attempts.pop(key, None)


# ── User management ────────────────────────────────────────────

def get_all_users():
    conn = _connect()
    rows = conn.execute(
        "SELECT id, username, name, role, tool_access, is_active, created_at, last_login FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user(username: str):
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def verify_password(username: str, password: str) -> bool:
    user = get_user(username)
    if not user or not user["is_active"]:
        return False
    match = _verify_hash(password, user["password_hash"])
    # Auto-upgrade legacy SHA-256 hashes to bcrypt on successful login
    if match and not user["password_hash"].startswith("$2b$"):
        conn = _connect()
        conn.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                      (_hash(password), username))
        conn.commit()
        conn.close()
    return match


def create_user(username: str, name: str, password: str, role: str = "user", tool_access: str = "both"):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO users (username, name, password_hash, role, tool_access) VALUES (?, ?, ?, ?, ?)",
            (username, name, _hash(password), role, tool_access)
        )
        conn.commit()
        return True, "User created."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()


def update_user(username: str, name: str = None, role: str = None,
                tool_access: str = None, is_active: int = None, password: str = None):
    conn = _connect()
    if name:
        conn.execute("UPDATE users SET name = ? WHERE username = ?", (name, username))
    if role:
        conn.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
    if tool_access:
        conn.execute("UPDATE users SET tool_access = ? WHERE username = ?", (tool_access, username))
    if is_active is not None:
        conn.execute("UPDATE users SET is_active = ? WHERE username = ?", (is_active, username))
    if password:
        conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (_hash(password), username))
    conn.commit()
    conn.close()


def delete_user(username: str):
    conn = _connect()
    conn.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()


# ── Sessions ───────────────────────────────────────────────────

def log_login(username: str, ip: str = None) -> int:
    conn = _connect()
    conn.execute("UPDATE users SET last_login = datetime('now') WHERE username = ?", (username,))
    cur = conn.execute(
        "INSERT INTO user_sessions (username, ip_address) VALUES (?, ?)", (username, ip)
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def log_logout(session_id: int):
    conn = _connect()
    conn.execute("""
        UPDATE user_sessions
        SET logout_at = datetime('now'),
            duration_s = CAST((julianday('now') - julianday(login_at)) * 86400 AS INTEGER)
        WHERE id = ?
    """, (session_id,))
    conn.commit()
    conn.close()


def get_sessions(limit: int = 200):
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM user_sessions ORDER BY login_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Activity log ───────────────────────────────────────────────

def log_activity(username: str, tool: str, action: str, detail: str = None):
    conn = _connect()
    conn.execute(
        "INSERT INTO activity_log (username, tool, action, detail) VALUES (?, ?, ?, ?)",
        (username, tool, action, detail)
    )
    conn.commit()
    conn.close()


def get_activity(username: str = None, tool: str = None, limit: int = 500):
    conn = _connect()
    clauses, params = [], []
    if username:
        clauses.append("username = ?")
        params.append(username)
    if tool:
        clauses.append("tool = ?")
        params.append(tool)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM activity_log {where} ORDER BY logged_at DESC LIMIT ?",
        params + [limit]
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
