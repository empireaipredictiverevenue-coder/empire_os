#!/usr/bin/env python3
"""empire_intelligence — Single source of truth for the AI sales loop.

Aggregates cortex + aeo + a2a + lease + affiliate + vault + payouts into
one JSON snapshot the sales agent can reason over. Runs cheap on each
agent tick, persisted to /root/feedback/intelligence.jsonl for north-mini.

Tables:
  intelligence_snapshots(id, ts, payload_json)

Functions:
  snapshot() — pull live state
  persist(snap) — write to DB + jsonl
  latest() — return most recent
"""
from __future__ import annotations
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
FEEDBACK_DIR = Path(os.getenv("FEEDBACK_DIR", "/root/empire_os/feedback"))
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
JSONL_PATH = FEEDBACK_DIR / "intelligence.jsonl"


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def ensure_table(c: sqlite3.Connection) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS intelligence_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            payload TEXT NOT NULL
        )""")
    c.commit()


def _vault_balance() -> dict:
    """Read live USDC vault balance from hub /v1/health/deep."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8081/v1/health/deep", timeout=5) as r:
            d = json.loads(r.read())
            chain = d.get("checks", {}).get("chain", {})
            rpc = chain.get("rpc", {})
            return {
                "vault_balance_usdc": rpc.get("vault_balance_usdc", rpc.get("vault_balance_usdt", 0.0)),
                "token_accounts": rpc.get("token_accounts", 0),
            }
    except Exception as e:
        return {"vault_balance_usdc": 0.0, "error": str(e)}


def snapshot() -> dict:
    """Pull live state from all monetization surfaces."""
    c = db()
    ensure_table(c)
    snap = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "vault": _vault_balance(),
    }

    try:
        # AEO
        snap["aeo"] = {
            "impressions_24h": c.execute(
                "SELECT COUNT(*) FROM aeo_events "
                "WHERE event_type='impression' AND ts >= datetime('now','-1 day')"
            ).fetchone()[0],
            "clicks_24h": c.execute(
                "SELECT COUNT(*) FROM aeo_events "
                "WHERE event_type='click' AND ts >= datetime('now','-1 day')"
            ).fetchone()[0],
            "top_niches": [dict(r) for r in c.execute("""
                SELECT niche, COUNT(*) as n FROM aeo_events
                WHERE ts >= datetime('now','-7 day')
                GROUP BY niche ORDER BY n DESC LIMIT 5
            """).fetchall()],
        }
    except Exception as e:
        snap["aeo"] = {"error": str(e)}

    try:
        snap["a2a"] = {
            "quotes_total": c.execute("SELECT COUNT(*) FROM a2a_quotes").fetchone()[0],
            "quotes_pending": c.execute(
                "SELECT COUNT(*) FROM a2a_quotes WHERE status='pending'"
            ).fetchone()[0],
            "quotes_funded": c.execute(
                "SELECT COUNT(*) FROM a2a_quotes WHERE status='funded'"
            ).fetchone()[0],
            "quotes_released": c.execute(
                "SELECT COUNT(*) FROM a2a_quotes WHERE status='released'"
            ).fetchone()[0],
            "released_revenue_usdc": c.execute(
                "SELECT COALESCE(SUM(amount_usdc),0) FROM a2a_quotes WHERE status='released'"
            ).fetchone()[0],
            "pending_revenue_usdc": c.execute(
                "SELECT COALESCE(SUM(amount_usdc),0) FROM a2a_quotes WHERE status IN ('pending','funded')"
            ).fetchone()[0],
        }
    except Exception as e:
        snap["a2a"] = {"error": str(e)}

    try:
        snap["lease"] = {
            "active": c.execute(
                "SELECT COUNT(*) FROM lead_leases WHERE status='active'"
            ).fetchone()[0],
            "active_revenue_usdc": c.execute(
                "SELECT COALESCE(SUM(price_usdc),0) FROM lead_leases WHERE status='active'"
            ).fetchone()[0],
            "total_consumed": c.execute(
                "SELECT COALESCE(SUM(used_leads),0) FROM lead_leases WHERE status='active'"
            ).fetchone()[0],
        }
    except Exception as e:
        snap["lease"] = {"error": str(e)}

    try:
        snap["affiliate"] = {
            "refs": c.execute(
                "SELECT COUNT(*) FROM affiliate_refs WHERE active=1"
            ).fetchone()[0],
            "conversions": c.execute(
                "SELECT COUNT(*) FROM affiliate_conversions"
            ).fetchone()[0],
            "pending_payout_usdc": c.execute(
                "SELECT COALESCE(SUM(amount_cents),0)/100.0 FROM affiliate_ledger WHERE status='pending'"
            ).fetchone()[0],
        }
    except Exception as e:
        snap["affiliate"] = {"error": str(e)}

    try:
        snap["settlements"] = {
            "vault_total_usdc": c.execute(
                "SELECT COALESCE(SUM(amount_cents),0)/100.0 FROM si_settlements"
            ).fetchone()[0],
            "ppc_open": c.execute(
                "SELECT COUNT(*) FROM si_ppc_invoices WHERE status='open'"
            ).fetchone()[0],
            "ppc_paid": c.execute(
                "SELECT COUNT(*) FROM si_ppc_invoices WHERE status='paid'"
            ).fetchone()[0],
            "subs_awaiting_payment": c.execute(
                "SELECT COUNT(*) FROM si_subscription WHERE status='awaiting_payment'"
            ).fetchone()[0],
        }
    except Exception as e:
        snap["settlements"] = {"error": str(e)}

    c.close()
    return snap


def persist(snap: dict) -> int:
    """Write snapshot to DB + jsonl. Returns row id."""
    c = db()
    ensure_table(c)
    payload = json.dumps(snap, default=str)
    cur = c.execute(
        "INSERT INTO intelligence_snapshots (ts, payload) VALUES (?,?)",
        (snap["ts"], payload),
    )
    c.commit()
    c.close()
    # Append to jsonl for north-mini
    with open(JSONL_PATH, "a") as f:
        f.write(payload + "\n")
    return cur.lastrowid


def latest(limit: int = 1) -> list:
    c = db()
    ensure_table(c)
    rows = c.execute(
        "SELECT * FROM intelligence_snapshots ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    snap = snapshot()
    snap_id = persist(snap)
    print(json.dumps(snap, indent=2, default=str))
    print(f"\nPersisted as snapshot #{snap_id}")