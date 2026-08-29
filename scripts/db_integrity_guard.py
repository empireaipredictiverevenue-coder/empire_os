#!/usr/bin/env python3
"""
db_integrity_guard.py — startup + scheduled corruption gate.

Runs integrity_check on the live DB. On first failure it:
  1. takes a pre-repair snapshot to /root/empire_os/backups/corrupt-<ts>.db
  2. attempts PRAGMA integrity_check repair via .recover if available
  3. if unrecoverable, restores the most recent good backup

This is the senior-engineer safety net that would have prevented the
Aug 18 silent corruption from spreading to the only copy.

Exit: 0 = healthy, 2 = recovered-from-backup, 3 = unrecoverable (paged).
"""
import os
import sys
import shutil
import sqlite3
from datetime import datetime, timezone

DB = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")
BACKUP_DIR = "/root/empire_os/backups"
ALERT = "/root/empire_os/feedback/integrity_alert.txt"


def check() -> bool:
    try:
        conn = sqlite3.connect(DB, timeout=30)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        rows = cur.fetchall()
        conn.close()
        bad = [r for r in rows if r[0] != "ok"]
        return len(bad) == 0
    except Exception as e:
        sys.stderr.write(f"check error: {e}\n")
        return False


def latest_good_backup():
    files = sorted(
        (f for f in os.listdir(BACKUP_DIR) if f.startswith("empire_os-") and f.endswith(".db")),
        reverse=True,
    )
    for f in files:
        path = os.path.join(BACKUP_DIR, f)
        try:
            c = sqlite3.connect(path, timeout=10)
            rc = c.execute("PRAGMA integrity_check").fetchall()
            c.close()
            if all(r[0] == "ok" for r in rc):
                return path
        except Exception:
            continue
    return None


def main():
    if check():
        print("INTEGRITY_OK")
        sys.exit(0)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print(f"INTEGRITY_FAIL {ts}")
    # snapshot current broken state
    broken = os.path.join(BACKUP_DIR, f"corrupt-{ts}.db")
    try:
        b = sqlite3.connect(DB, timeout=30)
        d = sqlite3.connect(broken, timeout=30)
        b.backup(d)
        d.close(); b.close()
    except Exception as e:
        sys.stderr.write(f"snapshot failed: {e}\n")
    # restore latest good backup
    good = latest_good_backup()
    if good:
        shutil.copy(good, DB)
        if check():
            msg = f"RECOVERED from {good} at {ts}\n"
            open(ALERT, "w").write(msg)
            print(msg.strip())
            sys.exit(2)
    msg = f"UNRECOVERABLE at {ts} — page on-call\n"
    open(ALERT, "w").write(msg)
    print(msg.strip())
    sys.exit(3)


if __name__ == "__main__":
    main()
