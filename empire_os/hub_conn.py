"""Empire OS — shared SQLite connection helper for hub routes.

Replaces 10 inline `sqlite3.connect("/root/empire_os/empire_os.db", ...)` sites
in hub.py, each of which was opening a fresh connection per HTTP request.
With uvicorn workers=1 and asyncio.to_thread spawning request-handler threads,
that pattern created 10+ open SQLite connections per process, each contending
for the WAL writer lock against lead_deliverer / billing / hub_loop_standalone.

Production rule: one connection per process, accessed via get_conn().
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from empire_os.funnel import SQLiteBackend

_conn: Optional[sqlite3.Connection] = None


def init_conn(backend: SQLiteBackend) -> sqlite3.Connection:
    """Bind the shared connection to the hub's SQLiteBackend._conn.

    Idempotent. Call once during lifespan startup.
    """
    global _conn
    _conn = backend._conn
    # Belt-and-braces: ensure WAL + busy_timeout are on the shared conn.
    try:
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout=30000")
    except sqlite3.OperationalError:
        pass
    return _conn


def get_conn() -> sqlite3.Connection:
    """Return the shared connection. Raises if init_conn wasn't called."""
    if _conn is None:
        raise RuntimeError("hub_conn: init_conn() not called — lifespan wiring missing")
    return _conn