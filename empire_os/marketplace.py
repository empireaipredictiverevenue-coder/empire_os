"""
Lead Marketplace — the per-lead revenue engine.

Pricing model:
  Pay-per-lead (PPL): $25-$150 per qualified lead
  Monthly seat:       $500-$2,000/mo for unlimited leads in a category+metro

Tiers (per lead):
  Bronze (low intent):  $25/lead
  Silver (medium):      $75/lead
  Gold (high intent):   $150/lead

The buyer picks a lane (category:sub_niche:metro) and a tier. When a lead
enters that lane and is scored at or above the tier threshold, the marketplace:
  1. Marks the lead as `reserved` for the buyer
  2. Generates an invoice line item
  3. Notifies the buyer
  4. On payment, transitions lead to `delivered` and emits a settlement event

DB lives inside empire-hub. All functions shell out via `incus exec
empire-hub` so the marketplace can be run from any container or the host.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("marketplace")

HUB_CONTAINER = "empire-hub"
HUB_DB_PATH = "/root/empire_os/empire_os.db"


def _hub_sql(query: str, params: tuple = ()) -> list:
    """Run SQL inside empire-hub and return rows as list of dicts.

    If the hub DB is reachable directly (we're in empire-hub or a sibling
    that can read the file), run the query in-process. Otherwise shell out
    via ``incus exec``. Mirrors the fallback logic in ``_hub_exec``.
    """
    if os.path.exists(HUB_DB_PATH):
        try:
            import sqlite3 as _sql
            c = _sql.connect(HUB_DB_PATH)
            c.row_factory = _sql.Row
            cur = c.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            c.close()
            return rows
        except Exception as e:
            logger.warning("hub_sql local failed: %s", e)
            return []
    try:
        script = (
            "import sqlite3, json, sys\n"
            "c = sqlite3.connect('%s')\n"
            "c.row_factory = sqlite3.Row\n"
            "params = json.loads(sys.argv[1])\n"
            "cur = c.execute(sys.argv[2], params)\n"
            "rows = [dict(r) for r in cur.fetchall()]\n"
            "c.close()\n"
            "print(json.dumps(rows, default=str))\n"
        ) % HUB_DB_PATH
        r = subprocess.run(
            ["incus", "exec", HUB_CONTAINER, "--",
             "/root/venv/bin/python3", "-c", script,
             json.dumps(list(params)), query],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return []
        out = r.stdout.strip()
        if not out:
            return []
        lines = out.split("\n")
        return json.loads(lines[-1])
    except Exception as e:
        logger.warning("hub_sql failed: %s", e)
        return []


def _hub_exec(script: str) -> tuple[bool, str]:
    """Run a Python script in empire-hub. Returns (success, stdout).

    If the DB is reachable directly (we're in empire-hub OR a sibling
    that can read the file), execute the script in-process with the
    existing python interpreter. Otherwise shell out via incus exec.
    """
    if os.path.exists(HUB_DB_PATH):
        try:
            # Inject common imports
            full_script = "import os, sys\n" + script
            r = subprocess.run(
                [sys.executable, "-c", full_script],
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "HUB_DB_PATH": HUB_DB_PATH},
            )
            return r.returncode == 0, (r.stdout + r.stderr).strip()
        except Exception:
            pass
    try:
        r = subprocess.run(
            ["incus", "exec", HUB_CONTAINER, "--",
             "/root/venv/bin/python3", "-c", script],
            capture_output=True, text=True, timeout=30,
        )
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


# Backwards-compat name (some callers pass DB_PATH)
DB_PATH = HUB_DB_PATH

# ─────────────────────────────────────────────────────────────────
# 1. TIER PRICING
# ─────────────────────────────────────────────────────────────────

LEAD_TIERS = {
    "bronze": {
        "min_omega_score": 20,
        "price_per_lead_cents": 2500,  # $25
        "description": "Low intent, high volume",
        "example": "Online form fill, no phone",
    },
    "silver": {
        "min_omega_score": 50,
        "price_per_lead_cents": 7500,  # $75
        "description": "Medium intent, qualified details",
        "example": "Form with name + zip + clear ask",
    },
    "gold": {
        "min_omega_score": 75,
        "price_per_lead_cents": 15000,  # $150
        "description": "High intent, ready to buy",
        "example": "Form with phone + email + specific need + budget signal",
    },
}

# Monthly seat pricing per category tier
SEAT_PRICING = {
    "solo":  {"seats": 1,  "monthly_cents": 50000,  "name": "Solo (1 user)"},
    "team":  {"seats": 5,  "monthly_cents": 200000, "name": "Team (5 users)"},
    "firm":  {"seats": 25, "monthly_cents": 750000, "name": "Firm (25 users)"},
}

# Per-lane seat subscription pricing — gold/standard model
# Each seat gives the buyer exclusive access to that niche+metro,
# unlimited leads, paying a flat fee per month. Backward-compat
# per-lead tier kept but de-emphasized in /v1/buyers/signup.
LANE_SEAT_PRICING = {
    # HYBRID tier model (v3, 2026-07-13):
    #   base = per-seat monthly subscription
    #   on_top = per-call fee (heads 1+2 from PPC engine).
    # Buyer pays a flat monthly seat fee for unlimited lead access in
    # their lanes, AND pays $15 per 90s call + $200 per hybrid-call connect
    # + 7% backend on contract closes. Total cost scales with both seats
    # AND activity — Empire OS captures revenue on both streams.
    #
    # High-ticket enterprise tiers (v3.1, 2026-07-13):
    #   Diamond / Empire / Titanium unlock large-seats packages with
    #   per-call fee discounts and SLA. Production gate: requires manual
    #   contract & KYC verification (see /v1/buyers/enterprise).

    # Bronze — starter tier, single-niche single-metro access
    "bronze": {
        "monthly_cents": 20000,   # $200/mo (was $100)
        "seats": 1,                # 1 niche × 1 metro
        "leads_per_month": "unlimited",
        "per_call_cents": 1500,    # $15 per 90s call (head 1)
        "hybrid_call_cents": 15000, # $150 per hybrid connect (head 2 up-front)
        "backend_pct": 0.05,       # 5% backend (head 2 close) — was 7%
        "description": "1 lane (niche × metro), all leads, real-time delivery",
    },
    # Silver — multi-niche OR multi-metro
    "silver": {
        "monthly_cents": 50000,   # $500/mo (was $250)
        "seats": 5,                # 5 lanes (niche × metro combinations)
        "leads_per_month": "unlimited",
        "per_call_cents": 2000,    # $20 per 90s call
        "hybrid_call_cents": 20000, # $200 per hybrid connect
        "backend_pct": 0.07,       # 7% backend
        "description": "5 lanes (any niche × metro mix), all leads, webhook + email",
    },
    # Gold — premium tier, broad coverage
    "gold": {
        "monthly_cents": 100000,  # $1000/mo (was $500)
        "seats": 25,               # 25 lanes
        "leads_per_month": "unlimited",
        "per_call_cents": 2500,    # $25 per 90s call
        "hybrid_call_cents": 25000, # $250 per hybrid connect
        "backend_pct": 0.10,       # 10% backend
        "description": "25 lanes (any tier × metro), priority routing, dashboard",
    },

    # ─── HIGH-TICKET ENTERPRISE (manual-contract + KYC-gated) ───
    "diamond": {
        "monthly_cents": 500000,  # $5,000/mo
        "seats": 100,             # 100 lanes
        "leads_per_month": "unlimited",
        "per_call_cents": 1250,   # $12.50 per 90s call (50% off)
        "hybrid_call_cents": 12500, # $125 per hybrid connect (50% off)
        "backend_pct": 0.07,      # 7% backend
        "sla_hours_response": 4,
        "support_level": "email + chat",
        "contract_required": True,
        "kyc_required": True,
        "description": "100 lanes, all metros, 50% per-call discount, 4h SLA",
    },
    "empire": {
        "monthly_cents": 1500000, # $15,000/mo
        "seats": 500,             # 500 lanes
        "leads_per_month": "unlimited",
        "per_call_cents": 0,      # calls included
        "hybrid_call_cents": 0,   # hybrid calls included
        "backend_pct": 0.05,      # 5% backend only
        "sla_hours_response": 1,
        "support_level": "dedicated AE + Slack",
        "contract_required": True,
        "kyc_required": True,
        "description": "500 lanes, calls included, ded AE, 1h SLA, 5% backend",
    },
    "titanium": {
        "monthly_cents": 5000000, # $50,000/mo
        "seats": 462,             # entire empire-lane universe
        "leads_per_month": "unlimited",
        "per_call_cents": 0,
        "hybrid_call_cents": 0,
        "backend_pct": 0.03,      # 3% backend
        "sla_hours_response": 0.5,  # 30 min
        "support_level": "named CSM + 24/7 phone + custom integrations",
        "contract_required": True,
        "kyc_required": True,
        "description": "all 462 lanes, $0 fees except 3% backend, 30min SLA, named CSM",
    },
}


def get_lane_seat_price(tier: str) -> dict:
    """Return per-seat tier config. Falls back to silver."""
    return LANE_SEAT_PRICING.get(tier, LANE_SEAT_PRICING["silver"])


# ─────────────────────────────────────────────────────────────────
# 2. LANE PRICING — per-niche+metro lead prices
# ─────────────────────────────────────────────────────────────────

def get_lane_price(niche: str, metro: str, tier: str = "silver") -> int:
    """Return price in cents for a lead in this lane at this tier.

    Premium metros (NYC, LAX, CHI) cost more — they have more demand.
    Premium niches (legal, finance) cost more — higher LTV.
    """
    base = LEAD_TIERS.get(tier, LEAD_TIERS["silver"])["price_per_lead_cents"]

    premium_metros = {"NYC", "LAX", "CHI", "DFW", "WDC"}
    premium_niches = {"hvac", "residential_roofing", "weight_loss",
                      "cybersecurity", "personal_injury"}

    multiplier = 1.0
    if metro in premium_metros:
        multiplier += 0.20
    if niche in premium_niches:
        multiplier += 0.30

    return int(base * multiplier)


def revenue_summary() -> dict:
    """Aggregate real revenue from settled charges.

    Returns the shape revenue_goals.fleet_summary expects:
    ``{"paid_mrr_usd": float, ...}``. Falls back to $0 gracefully if the
    table/column is missing — never raises into the caller.
    """
    try:
        rows = _hub_sql(
            "SELECT COALESCE(SUM(amount_cents),0) AS paid_cents "
            "FROM si_charges WHERE status='paid'"
        )
        paid_cents = rows[0]["paid_cents"] if rows else 0
    except Exception:
        paid_cents = 0
    # Open (unpaid) test/dry-run charges are intentionally excluded from MRR
    # but reported separately so the operator sees pending pipeline.
    try:
        open_rows = _hub_sql(
            "SELECT COALESCE(SUM(amount_cents),0) AS open_cents "
            "FROM si_charges WHERE status='open'"
        )
        open_cents = open_rows[0]["open_cents"] if open_rows else 0
    except Exception:
        open_cents = 0
    return {
        "paid_mrr_usd": round(paid_cents / 100.0, 2),
        "open_usd": round(open_cents / 100.0, 2),
        "currency": "USD",
    }


# ─────────────────────────────────────────────────────────────────
# 3. BUYER MANAGEMENT
# ─────────────────────────────────────────────────────────────────

def create_buyer(name: str, email: str, wallet: str = "",
                 method: str = "manual") -> str:
    """Create a buyer (tenant) record. Returns tenant_id."""
    tenant_id = "buyer_%s" % uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()

    script = (
        "import sqlite3, sys\n"
        "c = sqlite3.connect('%s')\n"
        "c.execute('INSERT INTO si_tenant (tenant_id, name, email, crypto_wallet, plan, "
        "billing_cycle, status, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)', "
        "(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], 'starter', 'monthly', 'active', "
        "sys.argv[5], sys.argv[5]))\n"
        "c.commit()\n"
        "c.close()\n"
    ) % HUB_DB_PATH
    ok, _ = _hub_exec(
        script.replace("sys.argv[1]", repr(tenant_id))
              .replace("sys.argv[2]", repr(name))
              .replace("sys.argv[3]", repr(email))
              .replace("sys.argv[4]", repr(wallet))
              .replace("sys.argv[5]", repr(now))
    )
    if not ok:
        return ""
    return tenant_id


def list_buyers() -> list:
    """List all buyers."""
    return _hub_sql("SELECT tenant_id, name, email, plan, status, created_at, "
                    "webhook_url, delivery_email, api_key, last_delivery_at "
                    "FROM si_tenant ORDER BY created_at DESC")


def set_buyer_webhook(tenant_id: str, webhook_url: str,
                      api_key: str = "", delivery_email: str = "") -> bool:
    """Configure a buyer's webhook + email for lead delivery."""
    # Pass everything as argv — no shell escaping needed.
    # Use Python's datetime at the top level to avoid __import__("datetime") in SQL.
    script = (
        "import sqlite3, sys\n"
        "from datetime import datetime, timezone\n"
        "c = sqlite3.connect('/root/empire_os/empire_os.db')\n"
        "now = datetime.now(timezone.utc).isoformat()\n"
        "c.execute(\n"
        "  'UPDATE si_tenant SET webhook_url = ?, api_key = ?, '\n"
        "  'delivery_email = ?, updated_at = ? WHERE tenant_id = ?',\n"
        "  (sys.argv[1], sys.argv[2], sys.argv[3], now, sys.argv[4])\n"
        ")\n"
        "c.commit()\n"
        "c.close()\n"
        "print('OK')\n"
    )
    full_cmd = [
        "incus", "exec", HUB_CONTAINER, "--",
        "/root/venv/bin/python3", "-c", script,
        webhook_url, api_key, delivery_email, tenant_id,
    ]
    try:
        r = subprocess.run(full_cmd, capture_output=True, text=True, timeout=15)
        if r.returncode != 0 or "OK" not in r.stdout:
            print(f"DEBUG set_buyer_webhook failed: rc={r.returncode} stderr={r.stderr[:200]}",
                  file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"DEBUG set_buyer_webhook exception: {e}", file=sys.stderr)
        return False


# ─────────────────────────────────────────────────────────────────
# 4. LANE SUBSCRIPTION
# ─────────────────────────────────────────────────────────────────

def buy_lane_access(tenant_id: str, niche: str, metro: str,
                    tier: str = "silver") -> dict:
    """Buyer subscribes to a lane (category:sub_niche:metro) at a tier.

    Returns subscription details + invoice.
    """
    if tier not in LEAD_TIERS:
        raise ValueError("Unknown tier: %s" % tier)

    price = get_lane_price(niche, metro, tier)
    sub_id = "sub_%s" % uuid.uuid4().hex[:12]
    inv_id = "inv_%s" % uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    desc = "Lane access: %s:%s (%s tier, $%.2f/lead)" % (niche, metro, tier, price/100)

    # Position by query, in order:
    # Subscription INSERT (11 cols): subscription_id, tenant_id, plan, billing_cycle,
    #   seats, price_cents, status, payment_method, started_at, current_period_end, created_at
    # Invoice INSERT (11 cols): invoice_id, tenant_id, subscription_id, amount_cents,
    #   currency, status, method, description, period_start, period_end, created_at
    # Metering INSERT (5 cols, with created_at): tenant_id, metric, value, period, created_at
    sub_args = [sub_id, tenant_id, "lane_%s" % tier, "per_lead", "1", str(price),
                "pending", "manual", now, now, now]
    inv_args = [inv_id, tenant_id, sub_id, str(price), "USD", "pending",
                "manual", desc, now, now, now]
    met_args = [tenant_id, "lane_subscription_created", "1", now[:7], now]
    all_args = sub_args + inv_args + met_args

    script = (
        "import sqlite3, sys\n"
        "c = sqlite3.connect('%s')\n"
        "c.execute('INSERT INTO si_subscription (subscription_id, tenant_id, plan, "
        "billing_cycle, seats, price_cents, status, payment_method, "
        "started_at, current_period_end, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)', "
        "(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), "
        "int(sys.argv[6]), sys.argv[7], sys.argv[8], sys.argv[9], sys.argv[10], sys.argv[11]))\n"
        "c.execute('INSERT INTO si_invoice (invoice_id, tenant_id, subscription_id, "
        "amount_cents, currency, status, method, description, "
        "period_start, period_end, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)', "
        "(sys.argv[12], sys.argv[13], sys.argv[14], int(sys.argv[15]), sys.argv[16], "
        "sys.argv[17], sys.argv[18], sys.argv[19], sys.argv[20], sys.argv[21], sys.argv[22]))\n"
        "c.execute('INSERT INTO si_metering (tenant_id, metric, value, period, created_at) "
        "VALUES (?,?,?,?,?)', (sys.argv[23], sys.argv[24], int(sys.argv[25]), sys.argv[26], sys.argv[27]))\n"
        "c.commit()\n"
        "c.close()\n"
        "print('OK')\n"
    ) % HUB_DB_PATH

    full = script
    for i, val in enumerate(all_args, 1):
        full = full.replace(f"sys.argv[{i}]", repr(val))

    ok, err = _hub_exec(full)
    if not ok:
        return {"error": err}

    return {
        "subscription_id": sub_id,
        "invoice_id": inv_id,
        "tenant_id": tenant_id,
        "niche": niche,
        "metro": metro,
        "tier": tier,
        "price_per_lead_cents": price,
        "status": "pending",
    }



def buy_seat_subscription(tenant_id: str, tier: str,
                           lanes: list = None) -> dict:
    """Per-seat subscription model.

    Buyer picks tier (bronze/silver/gold) -> monthly flat fee.
    Lanes determine which niche+metro combos are covered.
    """
    if tier not in LANE_SEAT_PRICING:
        raise ValueError("tier must be bronze/silver/gold")
    cfg = LANE_SEAT_PRICING[tier]
    monthly_cents = cfg["monthly_cents"]
    seats_allowed = cfg["seats"]
    if not lanes:
        raise ValueError("lanes[] required")
    if len(lanes) > seats_allowed:
        raise ValueError(
            "tier %s allows %d seats, got %d" % (tier, seats_allowed, len(lanes))
        )
    if cfg.get("contract_required"):
        # Enterprise gate: tier {tier} requires a signed contract and
        # KYC review. Surface this to the caller — the hub endpoint
        # returns it as a structured error so the UI can redirect to
        # /v1/buyers/enterprise.
        raise ValueError(
            "tier %s requires manual contract + KYC — "
            "POST /v1/buyers/enterprise to begin onboarding" % tier
        )

    sub_id = "sub_" + uuid.uuid4().hex[:12]
    now_iso = datetime.now(timezone.utc).isoformat()

    script_lines = [
        "import sqlite3, sys",
        "c = sqlite3.connect('" + HUB_DB_PATH + "')",
        # 12 cols, payment_ref = NULL literal, 11 placeholders
        "c.execute('INSERT INTO si_subscription "
        "(subscription_id, tenant_id, plan, billing_cycle, seats, "
        "price_cents, status, payment_method, payment_ref, "
        "started_at, current_period_end, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)'"
        ", (sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], "
        "int(sys.argv[5]), int(sys.argv[6]), sys.argv[7], "
        "sys.argv[8], sys.argv[9], sys.argv[10], sys.argv[11]))",
        "c.commit()",
        "c.close()",
    ]
    sub_script = "\n".join(script_lines) + "\n"

    args = [
        sub_id, tenant_id, "seat_" + tier, "monthly",
        seats_allowed, monthly_cents, "pending",
        "usdc_self_serve", now_iso, now_iso, now_iso,
    ]
    sub_full = sub_script
    for ii, v in enumerate(args, 1):
        sub_full = sub_full.replace("sys.argv[%d]" % ii, repr(v))

    ok, err = _hub_exec(sub_full)
    if not ok:
        return {"error": err}

    return {
        "subscription_id": sub_id,
        "tenant_id": tenant_id,
        "tier": tier,
        "seats": seats_allowed,
        "lane_count": len(lanes),
        "lanes": lanes,
        "monthly_cents": monthly_cents,
        "amount_usdc": monthly_cents / 100,
        "status": "pending",
    }



def mark_invoice_paid(invoice_id: str, reference: str = "manual") -> bool:
    """Mark an invoice as paid (manual confirmation)."""
    now = datetime.now(timezone.utc).isoformat()
    script = (
        "import sqlite3, sys\n"
        "c = sqlite3.connect('%s')\n"
        "cur = c.execute('UPDATE si_invoice SET status=\\\"paid\\\", paid_at=?, reference=? "
        "WHERE invoice_id=?', (sys.argv[1], sys.argv[2], sys.argv[3]))\n"
        "if cur.rowcount == 0:\n"
        "    print('NOTFOUND')\n"
        "else:\n"
        "    c.execute('UPDATE si_subscription SET status=\\\"active\\\" "
        "WHERE subscription_id=(SELECT subscription_id FROM si_invoice "
        "WHERE invoice_id=?)', (sys.argv[3],))\n"
        "    c.commit()\n"
        "    print('OK')\n"
        "c.close()\n"
    ) % HUB_DB_PATH
    full = script.replace("sys.argv[1]", repr(now))                   .replace("sys.argv[2]", repr(reference))                   .replace("sys.argv[3]", repr(invoice_id))
    ok, out = _hub_exec(full)
    return out == "OK"
