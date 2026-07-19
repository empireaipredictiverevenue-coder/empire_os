"""empire_os/db_handler.py - Singleton WAL connection pool with lock-safe txns.

Every agent/hub route uses this instead of raw sqlite3.connect(). Solves the
'database is locked' errors from concurrent processes + per-call connections.
"""
import os
import sqlite3
import threading
from contextlib import contextmanager

DB_PATH = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")
_local = threading.local()
_lock = threading.Lock()


def get_conn() -> sqlite3.Connection:
    """Per-thread connection, WAL + 30s busy_timeout, reuse across calls."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return conn


def close_conn():
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


@contextmanager
def txn():
    """Lock-safe transaction. Rolls back on exception, never leaves open txn."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise


@contextmanager
def txn_immediate():
    """WRITE transaction with IMMEDIATE lock acquisition (no upgrade deadlock)."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def query(sql: str, params=()):
    cur = get_conn().cursor()
    cur.execute(sql, params)
    return cur.fetchall()


def execute(sql: str, params=()):
    with txn() as cur:
        cur.execute(sql, params)
        return cur.rowcount
