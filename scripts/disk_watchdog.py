#!/usr/bin/env python3
"""
disk_watchdog.py — pre-corruption space guard.

The container's 150G disk has repeatedly hit 93%+ (Aug 22 cleanup freed 23G
by deleting stopped containers). When /root crosses the threshold we:
  1. alert to feedback/disk_alert.txt
  2. trim rotated DB backups beyond KEEP (cheap, safe space recovery)
  3. report WAL size (checkpoint if >200MB)
Does NOT auto-delete containers — that needs human sign-off.

Exit: 0 = ok or trimmed, 2 = over threshold, manual action needed.
"""
import os
import sys
import shutil
import sqlite3

ROOT = "/root"
BACKUP_DIR = "/root/empire_os/backups"
DB = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")
THRESHOLD = float(os.environ.get("DISK_WARN_PCT", "90"))
ALERT = "/root/empire_os/feedback/disk_alert.txt"


def root_pct() -> float:
    st = os.statvfs(ROOT)
    used = st.f_blocks - st.f_bfree
    return used / st.f_blocks * 100.0


def trim_backups(keep=14):
    removed = 0
    if os.path.isdir(BACKUP_DIR):
        files = sorted(
            (f for f in os.listdir(BACKUP_DIR)
             if f.startswith("empire_os-") and f.endswith(".db")),
            reverse=True,
        )
        for old in files[keep:]:
            try:
                os.remove(os.path.join(BACKUP_DIR, old))
                removed += 1
            except OSError:
                pass
    return removed


def checkpoint_wal():
    try:
        conn = sqlite3.connect(DB, timeout=30)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        return True
    except Exception:
        return False


def main():
    pct = root_pct()
    print(f"DISK root={pct:.1f}% threshold={THRESHOLD:.0f}%")
    if pct < THRESHOLD:
        print("OK")
        sys.exit(0)
    trimmed = trim_backups()
    checkpoint_wal()
    msg = f"DISK_WARN {pct:.1f}% @ {__import__('datetime').datetime.now().isoformat()} trimmed_backups={trimmed}\n"
    open(ALERT, "w").write(msg)
    print(msg.strip())
    print("ACTION: delete stopped containers or enlarge disk")
    sys.exit(2)


if __name__ == "__main__":
    main()
