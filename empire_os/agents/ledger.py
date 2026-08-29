"""
Omega OS — Pillar 4: Ledger
Handles payments. Tracks lead lifecycle status.
Creative (Pillar 5) triggers when status == 'PAID'.

Schema (sqlite, shares EMPIRE_DB):
  ledger_entries (
    lead_id    TEXT PK,
    niche      TEXT,
    status     TEXT,        -- PENDING | PAID
    amount_usd REAL,
    paid_at    TEXT,
    payload    TEXT,        -- json blob (lead meta, audit leaks, etc)
    created_at TEXT
  )
"""
import os
import sqlite3
import json
from datetime import datetime, timezone

DB = os.getenv("EMPIRE_DB", "/root/empire_os/empire_os.db")


def _conn():
    c = sqlite3.connect(DB)
    c.execute(
        """CREATE TABLE IF NOT EXISTS ledger_entries (
            lead_id    TEXT PRIMARY KEY,
            niche      TEXT,
            status     TEXT DEFAULT 'PENDING',
            amount_usd REAL DEFAULT 0.0,
            paid_at    TEXT,
            payload    TEXT,
            created_at TEXT
        )"""
    )
    c.commit()
    return c


def record_lead(lead_id, niche, payload=None):
    """Scout/Auditor/Messenger call this when a lead enters the funnel."""
    c = _conn()
    c.execute(
        "INSERT OR IGNORE INTO ledger_entries "
        "(lead_id, niche, status, payload, created_at) VALUES (?,?,?,?,?)",
        (lead_id, niche, "PENDING", json.dumps(payload or {}),
         datetime.now(timezone.utc).isoformat()),
    )
    c.commit()
    c.close()


def mark_paid(lead_id, amount_usd, payload=None):
    """Ledger marks a lead PAID — this is the P5 trigger."""
    c = _conn()
    cur = c.execute(
        "UPDATE ledger_entries SET status='PAID', amount_usd=?, "
        "paid_at=?, payload=COALESCE(?, payload) WHERE lead_id=?",
        (amount_usd, datetime.now(timezone.utc).isoformat(),
         json.dumps(payload) if payload else None, lead_id),
    )
    if cur.rowcount == 0:
        # lead not pre-recorded; insert directly
        c.execute(
            "INSERT OR REPLACE INTO ledger_entries "
            "(lead_id, status, amount_usd, paid_at, payload, created_at) "
            "VALUES (?, 'PAID', ?, ?, ?, ?)",
            (lead_id, amount_usd, datetime.now(timezone.utc).isoformat(),
             json.dumps(payload or {}), datetime.now(timezone.utc).isoformat()),
        )
    c.commit()
    c.close()


def pending_paid_unprocessed(processed_ids):
    """Return PAID leads not yet handled by Creative."""
    c = _conn()
    rows = c.execute(
        "SELECT lead_id, niche, amount_usd, payload FROM ledger_entries "
        "WHERE status='PAID'"
    ).fetchall()
    c.close()
    out = []
    for lead_id, niche, amount, payload in rows:
        if lead_id in processed_ids:
            continue
        try:
            pl = json.loads(payload) if payload else {}
        except Exception:
            pl = {}
        out.append({
            "lead_id": lead_id, "niche": niche or pl.get("niche", "general"),
            "amount_usd": amount or 0.0, "payload": pl,
        })
    return out


def mark_processed(lead_id):
    """Creative flags a PAID lead as video-generated (idempotency)."""
    c = _conn()
    c.execute(
        "UPDATE ledger_entries SET status='PAID_DONE' WHERE lead_id=? "
        "AND status='PAID'", (lead_id,))
    c.commit()
    c.close()


def stats():
    c = _conn()
    total = c.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()[0]
    paid = c.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_usd),0) FROM ledger_entries "
        "WHERE status='PAID'").fetchone()
    c.close()
    return {"total": total, "paid_count": paid[0], "paid_revenue": paid[1]}


def portal_view():
    """Portal (Dashboard) reads this — full pipeline results."""
    c = _conn()
    rows = c.execute(
        "SELECT lead_id, niche, status, amount_usd, paid_at FROM ledger_entries "
        "ORDER BY paid_at DESC LIMIT 100").fetchall()
    c.close()
    ledger = [{"lead_id": r[0], "niche": r[1], "status": r[2],
               "amount_usd": r[3], "paid_at": r[4]} for r in rows]
    # join creative assets
    cc = sqlite3.connect(DB)
    cc.execute("""CREATE TABLE IF NOT EXISTS creative_assets (
        lead_id TEXT PRIMARY KEY, niche TEXT, script TEXT,
        video_url TEXT, render_id TEXT, status TEXT, created_at TEXT)""")
    arows = cc.execute(
        "SELECT lead_id, video_url, status FROM creative_assets").fetchall()
    cc.close()
    assets = {r[0]: {"video_url": r[1], "status": r[2]} for r in arows}
    for L in ledger:
        a = assets.get(L["lead_id"])
        L["video_url"] = a["video_url"] if a else None
        L["creative_status"] = a["status"] if a else "NONE"
    return {"pipeline": ledger, "totals": stats()}


if __name__ == "__main__":
    print(json.dumps(stats(), indent=2))
