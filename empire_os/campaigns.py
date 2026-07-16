#!/usr/bin/env python3
"""campaigns — outbound lead-gen campaigns on the Empire OS inventory.

A campaign = targeted push against a niche/lane in the lead inventory
(si_buyer_outreach / lane_leads). Tracks sent / billed / collected.
The email_agent + lead_deliverer execute delivery; campaigns.py is the
orchestration + state layer (KISS, SQLite).

Schema: campaigns(id, name, niche, lane, tier, angle, status,
        audience_size, sent, billed, collected, created_at, updated_at)
"""
import sqlite3, json, time, uuid, sys
sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"
SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    name TEXT,
    niche TEXT,
    lane TEXT,
    tier TEXT DEFAULT 'standard',
    angle TEXT,
    status TEXT DEFAULT 'draft',
    audience_size INTEGER DEFAULT 0,
    sent INTEGER DEFAULT 0,
    billed INTEGER DEFAULT 0,
    collected INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

STATUSES = ("draft", "active", "paused", "done")


def init():
    c = sqlite3.connect(DB, timeout=20); c.execute("PRAGMA busy_timeout=15000")
    c.executescript(SCHEMA); c.commit(); c.close()


def _audience(niche: str) -> int:
    """Count deliverable leads matching a niche in the inventory."""
    c = sqlite3.connect(DB, timeout=20)
    n = 0
    try:
        n += c.execute("SELECT count(*) FROM si_buyer_outreach WHERE niche LIKE ?",
                       (f"%{niche}%",)).fetchone()[0]
    except Exception:
        pass
    try:
        n += c.execute("SELECT count(*) FROM lane_leads WHERE niche LIKE ? AND status='pending'",
                       (f"%{niche}%",)).fetchone()[0]
    except Exception:
        pass
    c.close()
    return n


def create(name: str, niche: str, lane: str = "", tier: str = "standard",
           angle: str = "") -> dict:
    init()
    aud = _audience(niche)
    cid = f"cmp-{uuid.uuid4().hex[:10]}"
    c = sqlite3.connect(DB, timeout=20); c.execute("PRAGMA busy_timeout=15000")
    c.execute("INSERT INTO campaigns (id, name, niche, lane, tier, angle, status, audience_size) "
              "VALUES (?,?,?,?,?,?, 'draft', ?)",
              (cid, name, niche, lane, tier, angle, aud))
    c.commit(); c.close()
    return {"id": cid, "name": name, "niche": niche, "audience_size": aud, "status": "draft"}


def list_all():
    c = sqlite3.connect(DB, timeout=20)
    rows = c.execute("SELECT id, name, niche, tier, status, audience_size, sent, billed "
                     "FROM campaigns ORDER BY created_at DESC").fetchall()
    c.close()
    return [dict(zip(("id", "name", "niche", "tier", "status", "audience", "sent", "billed"), r))
            for r in rows]


def launch(cid: str) -> dict:
    """Mark active + fire the delivery sweep for this campaign's niche."""
    c = sqlite3.connect(DB, timeout=20); c.execute("PRAGMA busy_timeout=15000")
    c.execute("UPDATE campaigns SET status='active', updated_at=datetime('now') WHERE id=?", (cid,))
    c.commit(); c.close()
    try:
        import empire_os.agents.lead_deliverer_agent as ld
        sent = ld.tick_once()
    except Exception as e:
        sent = f"err:{str(e)[:80]}"
    return {"id": cid, "status": "active", "tick_result": sent}


if __name__ == "__main__":
    # seed 3 starter campaigns against real seated-buyer niches
    print(create("Roofing Storm Sweep", "roofing", "roofing", "gold",
                 "post-storm roof repair financing"))
    print(create("Mass Tort Intake", "mass tort", "mass_tort", "gold",
                 "eligibility check + case review"))
    print(create("Medical Claims Recovery", "medical", "medical_claims", "gold",
                 "unpaid medical claim recovery"))
    print("--- list ---")
    print(json.dumps(list_all(), indent=2))
