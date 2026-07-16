#!/usr/bin/env python3
"""Affiliate / referral engine for Empire OS.
Affiliates get a tracked slug -> link. Leads attributed via ?ref=slug.
Commissions: tier-based % of lead invoice (default 20%, scale at volume).
KISS: SQLite table + functions; wired to lane billing later.
"""
import sqlite3, uuid, hashlib
from dataclasses import dataclass

DB = "/root/empire_os/empire_os.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS si_affiliate (
    affiliate_id TEXT PRIMARY KEY,
    slug         TEXT UNIQUE NOT NULL,
    name         TEXT,
    email        TEXT,
    commission_bps INTEGER DEFAULT 2000,  -- 2000 = 20%
    status       TEXT DEFAULT 'active',
    created_at   TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now'))
);
CREATE TABLE IF NOT EXISTS si_affiliate_click (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    affiliate_id TEXT,
    lead_id TEXT,
    prospect_id TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now'))
);
CREATE TABLE IF NOT EXISTS si_affiliate_commission (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    affiliate_id TEXT,
    lead_id TEXT,
    invoice_id TEXT,
    amount_cents INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now'))
);
"""

def init():
    c = sqlite3.connect(DB, timeout=15)
    c.executescript(SCHEMA)
    c.commit(); c.close()

def create_affiliate(name, email, slug=None, commission_bps=2000):
    init()
    if not slug:
        slug = hashlib.sha1(email.encode()).hexdigest()[:10]
    aid = str(uuid.uuid4())[:12]
    c = sqlite3.connect(DB, timeout=15)
    c.execute("INSERT INTO si_affiliate (affiliate_id, slug, name, email, commission_bps) "
              "VALUES (?,?,?,?,?)", (aid, slug, name, email, commission_bps))
    c.commit(); c.close()
    return {"affiliate_id": aid, "slug": slug,
            "link": f"https://empire-ai.co.uk/?ref={slug}"}

def attribute(lead_id, slug, prospect_id=""):
    c = sqlite3.connect(DB, timeout=15)
    row = c.execute("SELECT affiliate_id FROM si_affiliate WHERE slug=?", (slug,)).fetchone()
    if not row:
        c.close(); return None
    aid = row[0]
    c.execute("INSERT INTO si_affiliate_click (affiliate_id, lead_id, prospect_id) VALUES (?,?,?)",
              (aid, lead_id, prospect_id))
    c.commit(); c.close()
    return aid

def credit_commission(lead_id, invoice_id, amount_cents):
    c = sqlite3.connect(DB, timeout=15)
    row = c.execute("SELECT affiliate_id FROM si_affiliate_click WHERE lead_id=? LIMIT 1",
                    (lead_id,)).fetchone()
    if not row:
        c.close(); return None
    aid = row[0]
    bps = c.execute("SELECT commission_bps FROM si_affiliate WHERE affiliate_id=?", (aid,)).fetchone()[0]
    comm = int(amount_cents * bps / 10000)
    c.execute("INSERT INTO si_affiliate_commission (affiliate_id, lead_id, invoice_id, amount_cents) "
              "VALUES (?,?,?,?)", (aid, lead_id, invoice_id, comm))
    c.commit(); c.close()
    # money-only alert: affiliate commission = revenue event
    try:
        import empire_os.revenue_notify as _rn
        _rn.commission(aid, comm / 100.0, lead_id)
    except Exception:
        pass
    return {"affiliate_id": aid, "commission_cents": comm, "bps": bps}

def dashboard(affiliate_id):
    """Self-serve stats: clicks, conversions, earned, link."""
    c = sqlite3.connect(DB, timeout=15)
    row = c.execute("SELECT name, slug, commission_bps FROM si_affiliate "
                    "WHERE affiliate_id=?", (affiliate_id,)).fetchone()
    if not row:
        c.close(); return None
    name, slug, bps = row
    clicks = c.execute("SELECT count(*) FROM si_affiliate_click WHERE affiliate_id=?",
                       (affiliate_id,)).fetchone()[0]
    conv = c.execute("SELECT count(*), COALESCE(SUM(amount_cents),0) "
                     "FROM si_affiliate_commission WHERE affiliate_id=?",
                     (affiliate_id,)).fetchone()
    c.close()
    return {"affiliate_id": affiliate_id, "name": name,
            "link": f"https://empire-ai.co.uk/?ref={slug}",
            "commission_bps": bps, "clicks": clicks,
            "conversions": conv[0], "earned_usd": round((conv[1] or 0) / 100.0, 2)}

def signup(name, email, tier="standard"):
    """Self-serve affiliate signup -> returns affiliate + tracked link."""
    bps = {"standard": 2000, "pro": 2500, "elite": 3000}.get(tier, 2000)
    a = create_affiliate(name, email, commission_bps=bps)
    a["link"] = f"https://empire-ai.co.uk/?ref={a['slug']}"
    a["tier"] = tier
    return a

if __name__ == "__main__":
    init()
    print("affiliate schema ready")
