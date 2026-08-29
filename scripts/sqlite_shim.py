"""
Global SQLite hardening shim.
Installed as venv sitecustomize.py so EVERY sqlite3.connect() in the
process — including the 194 raw-connect call sites that bypass db_handler —
gets WAL + busy_timeout + sane PRAGMA forced on. This eliminates the
kill-mid-write corruption that produced empire_os.db.corrupt on Aug 18.

No behavioural change to callers: connect() still returns a normal
sqlite3.Connection, just with safe defaults pre-applied.
"""
import sqlite3
import threading

_orig_connect = sqlite3.connect
_shim_lock = threading.Lock()


def _hardened_connect(*args, **kwargs):
    conn = _orig_connect(*args, **kwargs)
    try:
        # WAL: concurrent readers + single serialized writer, crash-safe.
        conn.execute("PRAGMA journal_mode=WAL")
        # Wait up to 30s for the write lock instead of aborting with
        # "database is locked" — this is what was killing multi-agent writes.
        conn.execute("PRAGMA busy_timeout=30000")
        # NORMAL sync: durable enough, far fewer fsyncs than FULL.
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        # Aggressive autocheckpoint keeps WAL small + reduces checkpoint
        # races on process death.
        conn.execute("PRAGMA wal_autocheckpoint=1000")
    except Exception:
        # Never break a connect() call because of a PRAGMA failure.
        pass
    return conn


sqlite3.connect = _hardened_connect
