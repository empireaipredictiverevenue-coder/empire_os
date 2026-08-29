"""Empire OS Enterprise Tier — white-label Omega scoring + tiered legal leads.

Implements empire-os-enterprise-tier-launch skill:
- Tiered per-lead pricing: BRONZE $8 / SILVER $15 / GOLD $25 / PLATINUM $45
- Disaster multiplier (3x) when active
- White-label client config: branding, custom Omega weights, dedicated pool
- Dedicated buyer pool routing (exclusive, no self-serve overlap)
Tables (auto-created):
  si_enterprise_clients(client_id PK, firm_name, email, plan, base_cents,
      per_lead_cents, min_leads, omega_weights_json, brand_json, subdomain,
      status, created_at)
  si_enterprise_leads(id PK, client_id, lead_ref, omega_tier, price_cents,
      disaster_mult, assigned_at, status)
  si_disaster_mode(active INTEGER, reason TEXT, activated_at TEXT)
"""
from __future__ import annotations

import json
import sqlite3
import uuid
import datetime
from typing import Optional

DB_PATH = "/root/empire_os/empire_os.db"

TIER_PRICE_CENTS = {
    "BRONZE": 800,
    "SILVER": 1500,
    "GOLD": 2500,
    "PLATINUM": 4500,
}

PLANS = {
    # base_cents, per_lead_cents, min_leads/mo
    "enterprise_base": (500000, 300, 500),
    "enterprise_plus": (1000000, 250, 1000),
    "elite": (2000000, 200, 2000),
}


def _cx() -> sqlite3.Connection:
    cx = sqlite3.connect(DB_PATH, timeout=30.0)
    cx.execute("PRAGMA busy_timeout=30000")
    return cx


def _ensure_tables(cx: sqlite3.Connection) -> None:
    cx.execute(
        """CREATE TABLE IF NOT EXISTS si_enterprise_clients (
            client_id TEXT PRIMARY KEY,
            firm_name TEXT NOT NULL,
            email TEXT,
            plan TEXT NOT NULL DEFAULT 'enterprise_base',
            base_cents INTEGER NOT NULL,
            per_lead_cents INTEGER NOT NULL,
            min_leads INTEGER NOT NULL,
            omega_weights_json TEXT,
            brand_json TEXT,
            subdomain TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT)"""
    )
    cx.execute(
        """CREATE TABLE IF NOT EXISTS si_enterprise_leads (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            lead_ref TEXT NOT NULL,
            omega_tier TEXT,
            price_cents INTEGER,
            disaster_mult REAL DEFAULT 1.0,
            assigned_at TEXT,
            status TEXT DEFAULT 'assigned')"""
    )
    cx.execute(
        """CREATE TABLE IF NOT EXISTS si_disaster_mode (
            active INTEGER NOT NULL,
            reason TEXT,
            activated_at TEXT)"""
    )
    cx.commit()


def disaster_multiplier(cx: sqlite3.Connection) -> float:
    row = cx.execute("SELECT active FROM si_disaster_mode LIMIT 1").fetchone()
    return 3.0 if row and row[0] else 1.0


def set_disaster(active: bool, reason: str = "") -> dict:
    cx = _cx()
    try:
        _ensure_tables(cx)
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        cx.execute("DELETE FROM si_disaster_mode")
        cx.execute(
            "INSERT INTO si_disaster_mode (active, reason, activated_at) VALUES (?,?,?)",
            (1 if active else 0, reason, ts),
        )
        cx.commit()
        return {"ok": True, "disaster_active": bool(active), "multiplier": 3.0 if active else 1.0}
    finally:
        cx.close()


def register_client(req: dict) -> dict:
    """req: firm_name, email, plan, subdomain(optional),
    omega_weights(optional dict), brand(optional dict {logo_url, primary_color, accent_color})"""
    firm = (req.get("firm_name") or "").strip()
    email = (req.get("email") or "").strip()
    if not firm or "@" not in email:
        return {"ok": False, "error": "firm_name and valid email required"}
    plan = req.get("plan", "enterprise_base")
    if plan not in PLANS:
        return {"ok": False, "error": f"plan must be one of {list(PLANS)}"}
    base_cents, per_lead_cents, min_leads = PLANS[plan]
    client_id = "ent-" + uuid.uuid4().hex[:10]
    weights = req.get("omega_weights") or {
        "lead_quality": 1, "speed_scale": 1, "ai_intelligence": 1,
        "revenue_optimization": 1, "automation": 1, "analytics_insight": 1,
        "integration": 1, "self_learning": 1,
    }
    brand = req.get("brand") or {}
    subdomain = (req.get("subdomain") or firm.lower().replace(" ", "-")[:30]).strip("-")
    cx = _cx()
    try:
        _ensure_tables(cx)
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        cx.execute(
            """INSERT INTO si_enterprise_clients
               (client_id, firm_name, email, plan, base_cents, per_lead_cents,
                min_leads, omega_weights_json, brand_json, subdomain, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,'active',?)""",
            (client_id, firm, email, plan, base_cents, per_lead_cents,
             min_leads, json.dumps(weights), json.dumps(brand), subdomain, ts),
        )
        # mirror as si_tenant enterprise subscription so MRR counts
        # (skip if tenant with same email already exists — reuse it)
        tid = "tenant-" + uuid.uuid4().hex[:10]
        existing = cx.execute(
            "SELECT tenant_id FROM si_tenant WHERE email=?", (email,)).fetchone()
        if existing:
            tid = existing[0]
            cx.execute(
                "UPDATE si_tenant SET plan='enterprise', status='active', updated_at=? WHERE tenant_id=?",
                (ts, tid))
            cx.execute(
                "UPDATE si_subscription SET status='paused' WHERE tenant_id=? AND status='active'",
                (tid,))
        else:
            cx.execute(
                """INSERT INTO si_tenant (tenant_id, name, email, plan, billing_cycle,
                     status, created_at, updated_at, niche, delivery_email)
                   VALUES (?,?,?,'enterprise','monthly','active',?,?, 'mass_tort', ?)""",
                (tid, firm, email, ts, ts, email),
            )
        sid = "sub-" + uuid.uuid4().hex[:10]
        end = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=30)).isoformat()
        cx.execute(
            """INSERT INTO si_subscription (subscription_id, tenant_id, plan, billing_cycle,
                 seats, price_cents, status, started_at, current_period_end, created_at,
                 niche, updated_at)
               VALUES (?,?,?,'monthly',1,?,'active',?,?,?, 'mass_tort', ?)""",
            (sid, tid, plan, base_cents, ts, end, ts, ts),
        )
        cx.commit()
        return {"ok": True, "client_id": client_id, "tenant_id": tid,
                "plan": plan, "base_usd": base_cents / 100,
                "per_lead_usd": per_lead_cents / 100, "min_leads": min_leads,
                "subdomain": subdomain}
    finally:
        cx.close()


def quote_leads(req: dict) -> dict:
    """req: niche, metro, count(optional). Returns tiered quote w/ disaster mult."""
    niche = (req.get("niche") or "mass_tort").strip()
    metro = (req.get("metro") or "").strip()
    count = min(int(req.get("count", 50)), 2000)
    cx = _cx()
    try:
        _ensure_tables(cx)
        mult = disaster_multiplier(cx)
        q = "SELECT omega_tier, COUNT(*) FROM lane_leads WHERE niche=? AND status IN ('pending','new')"
        args = [niche]
        if metro:
            q += " AND metro LIKE ?"
            args.append(f"%{metro}%")
        q += " GROUP BY omega_tier"
        tier_mix = dict(cx.execute(q, args).fetchall())
        lines = []
        for tier, cents in TIER_PRICE_CENTS.items():
            avail = tier_mix.get(tier, 0)
            if avail:
                lines.append({"tier": tier, "available": avail,
                              "unit_usd": cents / 100 * mult})
        return {"ok": True, "niche": niche, "metro": metro,
                "disaster_multiplier": mult,
                "quote": lines,
                "pool_total": sum(tier_mix.values())}
    finally:
        cx.close()


def assign_leads(req: dict) -> dict:
    """req: client_id, count(optional). Pulls top-scored pending mass_tort leads
    from lane_leads into the client's dedicated pool at tier pricing."""
    client_id = (req.get("client_id") or "").strip()
    if not client_id:
        return {"ok": False, "error": "client_id required"}
    cx = _cx()
    try:
        _ensure_tables(cx)
        cl = cx.execute(
            "SELECT client_id, per_lead_cents FROM si_enterprise_clients WHERE client_id=? AND status='active'",
            (client_id,)).fetchone()
        if not cl:
            return {"ok": False, "error": "client not found or inactive"}
        mult = disaster_multiplier(cx)
        count = min(int(req.get("count", 50)), 2000)
        rows = cx.execute(
            """SELECT lead_ref, omega_tier, omega_score FROM lane_leads
               WHERE niche='mass_tort' AND status IN ('pending','new')
               ORDER BY omega_score DESC LIMIT ?""", (count,)).fetchall()
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        out = []
        for lead_ref, tier, score in rows:
            tier = (tier or "BRONZE").upper()
            cents = int(TIER_PRICE_CENTS.get(tier, TIER_PRICE_CENTS["BRONZE"]) * mult)
            lid = "el-" + uuid.uuid4().hex[:12]
            cx.execute(
                """INSERT INTO si_enterprise_leads
                   (id, client_id, lead_ref, omega_tier, price_cents, disaster_mult,
                    assigned_at, status) VALUES (?,?,?,?,?,?,?,'assigned')""",
                (lid, client_id, lead_ref, tier, cents, mult, ts))
            cx.execute("UPDATE lane_leads SET status='assigned_pool' WHERE lead_ref=?",
                       (lead_ref,))
            out.append({"id": lid, "lead_ref": lead_ref, "tier": tier,
                        "price_usd": cents / 100})
        cx.commit()
        total = sum(x["price_usd"] for x in out)
        return {"ok": True, "client_id": client_id, "assigned": len(out),
                "pool_value_usd": round(total, 2), "disaster_multiplier": mult,
                "leads": out[:20]}
    finally:
        cx.close()


def client_config(client_id: str) -> dict:
    cx = _cx()
    try:
        _ensure_tables(cx)
        row = cx.execute(
            """SELECT client_id, firm_name, email, plan, base_cents, per_lead_cents,
               min_leads, omega_weights_json, brand_json, subdomain, status, created_at
               FROM si_enterprise_clients WHERE client_id=?""", (client_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "client not found"}
        pool = cx.execute(
            "SELECT COUNT(*), ROUND(SUM(price_cents)/100.0,2) FROM si_enterprise_leads WHERE client_id=?",
            (client_id,)).fetchone()
        return {"ok": True, "client": {
            "client_id": row[0], "firm_name": row[1], "email": row[2],
            "plan": row[3], "base_usd": row[4] / 100, "per_lead_usd": row[5] / 100,
            "min_leads": row[6], "omega_weights": json.loads(row[7] or "{}"),
            "brand": json.loads(row[8] or "{}"), "subdomain": row[9],
            "status": row[10], "created_at": row[11]},
            "pool": {"leads": pool[0], "value_usd": pool[1]}}
    finally:
        cx.close()
