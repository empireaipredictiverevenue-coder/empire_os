"""Global SQLite hardening for Empire OS.

Installed into the venv site-packages as a sitecustomize-style module
loaded at interpreter startup. Wraps sqlite3.connect so EVERY connection
(including the 235 raw sqlite3.connect() calls spread across the
codebase) gets:
  - PRAGMA busy_timeout=30000   (no more lock death spirals)
  - PRAGMA journal_mode=WAL     (concurrent readers + 1 writer)
  - PRAGMA synchronous=NORMAL   (durable enough, fast)
  - PRAGMA foreign_keys=ON

This is the surgical fix for the recurring "database is locked (5)"
cascade that took down cortex / intelligence / predictive / etc.

Load order: this file is imported early by sitecustomize.py which is
auto-loaded by CPython before any user module runs.
"""
import sqlite3

_orig_connect = sqlite3.connect

_BUSY_TIMEOUT = 30000


def _harden(conn):
    try:
        conn.execute("PRAGMA busy_timeout=%d" % _BUSY_TIMEOUT)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        # read-only / in-memory edge cases: ignore
        pass
    return conn


def connect(*args, **kwargs):
    # bump the python-level timeout too so we wait on busy
    kwargs.setdefault("timeout", 30.0)
    conn = _orig_connect(*args, **kwargs)
    return _harden(conn)


sqlite3.connect = connect
