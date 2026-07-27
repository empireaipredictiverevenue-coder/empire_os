#!/usr/bin/env python3
"""amount_policy — Min/max USDC guards for every monetization channel.

Single source of truth for floor/ceiling on AEO/A2A/Lease amounts.
Rejects sub-floor with clear error. Read by hub endpoints before
quote/lease creation.

Tables: amount_policy(channel, min_usdc, max_usdc, default_usdc, niche_multiplier)
"""
from __future__ import annotations
import json
import os
import sqlite3
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")

DEFAULTS = {
    "aeo": {"min_usdc": 4.0, "max_usdc": 50.0, "default_usdc": 12.0},
    "a2a": {"min_usdc": 25.0, "max_usdc": 10000.0, "default_usdc": 100.0},
    "lease": {"min_usdc": 80.0, "max_usdc": 50000.0, "default_usdc": 200.0},
}


def db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, timeout=15)


def ensure_table(c: sqlite3.Connection) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS amount_policy (
            channel TEXT PRIMARY KEY,
            min_usdc REAL NOT NULL,
            max_usdc REAL NOT NULL,
            default_usdc REAL NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        )""")
    c.commit()


def seed_defaults(c: sqlite3.Connection) -> None:
    n = c.execute("SELECT COUNT(*) FROM amount_policy").fetchone()[0]
    if n == 0:
        for ch, vals in DEFAULTS.items():
            c.execute(
                "INSERT INTO amount_policy (channel, min_usdc, max_usdc, default_usdc) VALUES (?,?,?,?)",
                (ch, vals["min_usdc"], vals["max_usdc"], vals["default_usdc"]),
            )
        c.commit()


def get_policy(c: sqlite3.Connection, channel: str) -> dict:
    ensure_table(c)
    seed_defaults(c)
    row = c.execute(
        "SELECT min_usdc, max_usdc, default_usdc FROM amount_policy WHERE channel=?",
        (channel,),
    ).fetchone()
    if row:
        return {"min_usdc": row[0], "max_usdc": row[1], "default_usdc": row[2]}
    return DEFAULTS.get(channel, DEFAULTS["aeo"])


def validate(channel: str, amount_usdc: float, c: Optional[sqlite3.Connection] = None) -> dict:
    """Returns {ok, error?, min, max}. ok=False means reject the request."""
    own = c is None
    if own:
        c = db()
    try:
        p = get_policy(c, channel)
        if amount_usdc < p["min_usdc"]:
            return {
                "ok": False,
                "error": f"amount_below_min:{channel}_min=${p['min_usdc']:.2f}_got=${amount_usdc:.2f}",
                "min_usdc": p["min_usdc"],
                "max_usdc": p["max_usdc"],
            }
        if amount_usdc > p["max_usdc"]:
            return {
                "ok": False,
                "error": f"amount_above_max:{channel}_max=${p['max_usdc']:.2f}_got=${amount_usdc:.2f}",
                "min_usdc": p["min_usdc"],
                "max_usdc": p["max_usdc"],
            }
        return {"ok": True, "min_usdc": p["min_usdc"], "max_usdc": p["max_usdc"]}
    finally:
        if own:
            c.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        ch, amt = sys.argv[1], float(sys.argv[2])
        c = db()
        print(json.dumps(validate(ch, amt, c), indent=2))
        c.close()
    else:
        print("usage: amount_policy.py <channel> <amount_usdc>")