#!/usr/bin/env python3
"""
db_backup.py — consistent SQLite snapshot + rotation.

Uses sqlite3's online .backup which produces a transactionally-consistent
copy even while 20+ agents write. Never copies the live -wal/-shm file
directly (that's how partial/corrupt copies get made).

Run:  db_backup.py                 # one-shot (also used by pre-action hook)
       db_backup.py --keep 14      # rotation count
Backups land in /root/empire_os/backups/ with timestamp + size.
"""
import os
import sys
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone

DB = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")
BACKUP_DIR = "/root/empire_os/backups"
KEEP = int(os.environ.get("DB_BACKUP_KEEP", "14"))


def consistent_backup(dest: str) -> bool:
    """Online backup via the sqlite3 backup API — safe under concurrent writes."""
    try:
        src = sqlite3.connect(DB, timeout=30)
        dst = sqlite3.connect(dest, timeout=30)
        src.backup(dst)
        dst.close()
        src.close()
        return True
    except Exception as e:
        sys.stderr.write(f"backup failed: {e}\n")
        return False


def main():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = os.path.join(BACKUP_DIR, f"empire_os-{ts}.db")
    if not consistent_backup(dest):
        sys.exit(1)
    size = os.path.getsize(dest)
    print(f"BACKUP_OK {dest} {size}b")
    # rotate
    files = sorted(
        (f for f in os.listdir(BACKUP_DIR) if f.startswith("empire_os-") and f.endswith(".db")),
        reverse=True,
    )
    for old in files[KEEP:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
        except OSError:
            pass
    print(f"ROTATE kept={min(len(files), KEEP)}")


if __name__ == "__main__":
    if "--keep" in sys.argv:
        KEEP = int(sys.argv[sys.argv.index("--keep") + 1])
    main()
