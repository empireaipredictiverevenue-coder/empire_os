#!/usr/bin/env python3
"""Daily WAL checkpoint. Runs via systemd timer.
Folds empire_os.db-wal back into main DB. Idempotent, safe to run repeatedly.
ALWAYS sys.exit(0).
"""
import sqlite3, os, time, sys, json
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
LOG = "/root/empire_os/feedback/wal_checkpoint.jsonl"

def size(p):
    try: return os.path.getsize(p)
    except: return 0

def main():
    before_db = size(DB)
    before_wal = size(DB + "-wal")
    before_shm = size(DB + "-shm")

    try:
        uri = f"file:{DB}?mode=rw"
        c = sqlite3.connect(uri, uri=True, timeout=30)
        busy, log, ckpt = c.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        c.close()
    except Exception as e:
        # Even on error, log and exit 0 (verifier pattern)
        with open(LOG, "a") as f:
            f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                                "error": str(e)[:200],
                                "before": {"db": before_db, "wal": before_wal}}) + "\n")
        sys.exit(0)

    after_db = size(DB)
    after_wal = size(DB + "-wal")
    after_shm = size(DB + "-shm")

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "before": {"db": before_db, "wal": before_wal, "shm": before_shm},
        "after": {"db": after_db, "wal": after_wal, "shm": after_shm},
        "checkpoint": {"busy": busy, "log": log, "frames": ckpt},
        "freed_bytes": before_wal - after_wal,
    }
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print("WAL checkpoint done: {} -> {} (freed {} bytes)".format(
        before_wal, after_wal, before_wal - after_wal))
    sys.exit(0)

if __name__ == "__main__":
    main()
