"""
Database backup & restore — auto-backup every 8 hours, retain 15 days.
Backups stored in hosted_app/data/backups/
"""
import os
import shutil
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import os as _os
# Persistent storage: check env var first, then auto-detect Render disk, then local fallback
DATA_DIR = Path(_os.environ.get("DATA_DIR") or (
    "/data" if _os.path.isdir("/data") else str(Path(__file__).parent.parent / "data")
))
BACKUP_DIR = DATA_DIR / "backups"

# Which databases to back up
DB_FILES = {
    "tracker": DATA_DIR / "tracker.db",
    "auth": DATA_DIR / "auth.db",
}

BACKUP_INTERVAL_SECONDS = 8 * 3600   # 8 hours
RETENTION_DAYS = 15
LAST_BACKUP_FILE = BACKUP_DIR / ".last_backup"


def _ensure_backup_dir():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _safe_copy_db(src: Path, dst: Path):
    """Safely copy a SQLite database using the backup API to avoid corruption."""
    if not src.exists():
        return
    src_conn = sqlite3.connect(str(src))
    dst_conn = sqlite3.connect(str(dst))
    src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()


def create_backup(label: str = "auto") -> str | None:
    """
    Create a timestamped backup of all databases.
    Returns the backup folder name, e.g. '2026-03-31_14-30-00_auto'
    """
    _ensure_backup_dir()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder_name = f"{timestamp}_{label}"
    backup_path = BACKUP_DIR / folder_name
    backup_path.mkdir(parents=True, exist_ok=True)

    backed_up = False
    for name, db_path in DB_FILES.items():
        if db_path.exists():
            _safe_copy_db(db_path, backup_path / f"{name}.db")
            backed_up = True

    if not backed_up:
        shutil.rmtree(backup_path, ignore_errors=True)
        return None

    # Update last-backup timestamp
    LAST_BACKUP_FILE.write_text(str(time.time()))
    return folder_name


def auto_backup_if_due():
    """Check if 8 hours have passed since last backup; if so, create one."""
    _ensure_backup_dir()

    if LAST_BACKUP_FILE.exists():
        try:
            last_ts = float(LAST_BACKUP_FILE.read_text().strip())
            if time.time() - last_ts < BACKUP_INTERVAL_SECONDS:
                return None  # Not due yet
        except (ValueError, OSError):
            pass

    return create_backup(label="auto")


def cleanup_old_backups():
    """Delete backups older than RETENTION_DAYS."""
    _ensure_backup_dir()
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)

    for entry in sorted(BACKUP_DIR.iterdir()):
        if not entry.is_dir():
            continue
        # Parse timestamp from folder name: 2026-03-31_14-30-00_label
        try:
            ts_str = "_".join(entry.name.split("_")[:2])  # '2026-03-31_14-30-00'
            backup_time = datetime.strptime(ts_str, "%Y-%m-%d_%H-%M-%S")
            if backup_time < cutoff:
                shutil.rmtree(entry)
        except (ValueError, IndexError):
            continue


def list_backups() -> list[dict]:
    """
    List all backups, newest first.
    Returns list of dicts: { name, timestamp, label, files, size_bytes }
    """
    _ensure_backup_dir()
    backups = []

    for entry in sorted(BACKUP_DIR.iterdir(), reverse=True):
        if not entry.is_dir():
            continue
        parts = entry.name.split("_")
        if len(parts) < 3:
            continue
        try:
            ts_str = f"{parts[0]}_{parts[1]}"
            backup_time = datetime.strptime(ts_str, "%Y-%m-%d_%H-%M-%S")
        except ValueError:
            continue

        label = "_".join(parts[2:])
        files = [f.name for f in entry.iterdir() if f.suffix == ".db"]
        size = sum(f.stat().st_size for f in entry.iterdir() if f.is_file())

        backups.append({
            "name": entry.name,
            "timestamp": backup_time,
            "label": label,
            "files": files,
            "size_bytes": size,
            "path": entry,
        })

    return backups


def restore_tracker_from_backup(backup_name: str) -> bool:
    """Restore tracker.db from an existing backup."""
    backup_path = BACKUP_DIR / backup_name / "tracker.db"
    if not backup_path.exists():
        return False

    target = DB_FILES["tracker"]
    # Create a safety backup before restoring
    create_backup(label="pre-restore")
    _safe_copy_db(backup_path, target)
    return True


def restore_tracker_from_upload(uploaded_bytes: bytes) -> bool:
    """
    Replace tracker.db with an uploaded file.
    Validates it's a valid SQLite database before replacing.
    """
    # Validate the uploaded file is a valid SQLite database
    if not uploaded_bytes[:16].startswith(b"SQLite format 3"):
        return False

    target = DB_FILES["tracker"]

    # Create a safety backup before restoring
    create_backup(label="pre-upload-restore")

    # Write to a temp file first, then replace
    tmp_path = target.with_suffix(".db.tmp")
    tmp_path.write_bytes(uploaded_bytes)

    # Verify the temp file is a valid, queryable database
    try:
        conn = sqlite3.connect(str(tmp_path))
        conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        conn.close()
    except sqlite3.DatabaseError:
        tmp_path.unlink(missing_ok=True)
        return False

    # Replace the live database
    shutil.move(str(tmp_path), str(target))
    return True


def delete_backup(backup_name: str) -> bool:
    """Delete a specific backup."""
    backup_path = BACKUP_DIR / backup_name
    if backup_path.exists() and backup_path.is_dir():
        shutil.rmtree(backup_path)
        return True
    return False
