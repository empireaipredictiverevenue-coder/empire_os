#!/usr/bin/env python3
"""Switchboard persistence layer — SQLite-backed state for calls, bids, decisions."""
from __future__ import annotations
import sqlite3, os, json, time
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = Path(os.environ.get("SWITCHBOARD_DB", "/root/feedback/switchboard.db"))

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS calls (
    call_id     TEXT PRIMARY KEY,
    lane_key    TEXT NOT NULL,
    from_num    TEXT,
    to_num      TEXT,
    lead_id     TEXT,
    status      TEXT NOT NULL DEFAULT 'placed',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    duration_s  INTEGER DEFAULT 0,
    rec_url     TEXT,
    buyer_id    TEXT,
    settled_cents INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_calls_lane ON calls(lane_key);
CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status);

CREATE TABLE IF NOT EXISTS bids (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lane_key    TEXT NOT NULL,
    buyer_id    TEXT NOT NULL,
    cpm_cents   INTEGER NOT NULL,
    callback_url TEXT,
    created_at  TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_bids_lane ON bids(lane_key, active);

CREATE TABLE IF NOT EXISTS agi_decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id     TEXT,
    ts          TEXT NOT NULL,
    state       TEXT NOT NULL,
    decision    TEXT NOT NULL,
    agi_raw     TEXT,
    synth_raw   TEXT
);

CREATE INDEX IF NOT EXISTS idx_agi_call ON agi_decisions(call_id);

CREATE TABLE IF NOT EXISTS tenants (
    api_key     TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL UNIQUE,
    name        TEXT,
    created_at  TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tcpa_scrub (
    phone       TEXT PRIMARY KEY,
    list_src    TEXT NOT NULL,
    added_at    TEXT NOT NULL,
    expires_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_tcpa_expires ON tcpa_scrub(expires_at);
"""

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# ── Calls ──────────────────────────────────────────────────────────────
def create_call(call_id: str, lane_key: str, from_num: str, to_num: str, lead_id: str = "") -> dict:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO calls (call_id, lane_key, from_num, to_num, lead_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'placed', ?, ?)
        """, (call_id, lane_key, from_num, to_num, lead_id, now_iso(), now_iso()))
    return get_call(call_id)

def get_call(call_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,)).fetchone()
    return dict(row) if row else None

def update_call_status(call_id: str, status: str, **extra) -> dict | None:
    fields = ["status = ?", "updated_at = ?"]
    vals = [status, now_iso()]
    for k, v in extra.items():
        fields.append(f"{k} = ?")
        vals.append(v)
    vals.append(call_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE calls SET {', '.join(fields)} WHERE call_id = ?", vals)
    return get_call(call_id)

def list_active_calls() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM calls WHERE status IN ('placed','ringing','answered') ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]

# ── Bids ──────────────────────────────────────────────────────────────
def place_bid(lane_key: str, buyer_id: str, cpm_cents: int, callback_url: str = "") -> dict:
    with get_conn() as conn:
        # deactivate old bids for this buyer+lane
        conn.execute("UPDATE bids SET active = 0 WHERE lane_key = ? AND buyer_id = ?", (lane_key, buyer_id))
        cur = conn.execute("""
            INSERT INTO bids (lane_key, buyer_id, cpm_cents, callback_url, created_at, active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (lane_key, buyer_id, cpm_cents, callback_url, now_iso()))
        bid_id = cur.lastrowid
    return get_top_bid(lane_key)

def get_top_bid(lane_key: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT * FROM bids WHERE lane_key = ? AND active = 1
            ORDER BY cpm_cents DESC, created_at ASC LIMIT 1
        """, (lane_key,)).fetchone()
    return dict(row) if row else None

def list_bids(lane_key: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM bids WHERE lane_key = ? AND active = 1 ORDER BY cpm_cents DESC", (lane_key,)).fetchall()
    return [dict(r) for r in rows]

# ── AGI Decisions ─────────────────────────────────────────────────────
def log_agi_decision(call_id: str | None, state: dict, decision: dict, agi_raw: dict, synth_raw: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO agi_decisions (call_id, ts, state, decision, agi_raw, synth_raw)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (call_id or "", now_iso(), json.dumps(state), json.dumps(decision), json.dumps(agi_raw), json.dumps(synth_raw)))
    return cur.lastrowid

def get_recent_decisions(n: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM agi_decisions ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
    return [dict(r) for r in rows]

# ── Tenants / API Keys ────────────────────────────────────────────────
def create_tenant(api_key: str, tenant_id: str, name: str = "") -> None:
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO tenants (api_key, tenant_id, name, created_at, active) VALUES (?, ?, ?, ?, 1)",
                     (api_key, tenant_id, name, now_iso()))

def get_tenant(api_key: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tenants WHERE api_key = ? AND active = 1", (api_key,)).fetchone()
    return dict(row) if row else None

# ── TCPA / DNC ────────────────────────────────────────────────────────
def is_scrubbed(phone: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM tcpa_scrub WHERE phone = ? AND (expires_at IS NULL OR expires_at > ?)", (phone, now_iso())).fetchone()
    return row is not None

def add_scrub(phone: str, list_src: str, expires_at: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO tcpa_scrub (phone, list_src, added_at, expires_at) VALUES (?, ?, ?, ?)",
                     (phone, list_src, now_iso(), expires_at))

if __name__ == "__main__":
    init_db()
    print("switchboard.db initialized at", DB_PATH)