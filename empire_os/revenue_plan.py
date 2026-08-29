#!/usr/bin/env python3
"""revenue_plan — Empire OS revenue plan + forecast generator.

Single source of truth for "how much are we making / going to make" across
EVERYTHING we do: buyer seats (4 tiers), per-lead PPL, per-cycle/platform.

Reads the live hub DB (/root/empire_os/empire_os.db) and produces:
  - current state: MRR, ARR, active vs awaiting pipeline, tier mix
  - forecast: 30 / 60 / 90 day MRR under 3 conversion scenarios
              (conservative 10%, base 30%, aggressive 60% of awaiting paid)
  - per-lead upside: seat MRR + modelled delivered-lead revenue

Assumptions are explicit and editable (ASSUMED_LEADS_PER_BUYER). This is a
MODEL, not booked revenue — every number is labelled.

Access:
  - CLI:   python3 empire_os/revenue_plan.py
  - Hub:   GET http://127.0.0.1:8081/v1/revenue/plan
  - File:  /root/empire_os/revenue_plan.json (written on every build)
"""
from __future__ import annotations
import json, os, sqlite3
from datetime import datetime, timezone

DB = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")
OUT = "/root/empire_os/revenue_plan.json"

# 4-tier seat pricing (USD/mo seat) + per-lead PPL rate (USD).
TIER_RATES = {
    "bronze":   {"monthly": 299.0,  "per_lead": 25.0},
    "silver":   {"monthly": 599.0,  "per_lead": 49.0},
    "gold":     {"monthly": 1199.0, "per_lead": 99.0},
    "platinum": {"monthly": 2399.0, "per_lead": 199.0},
}
TIER_ORDER = ["bronze", "silver", "gold", "platinum"]

# Modelled avg delivered leads per ACTIVE buyer per month, by tier.
# Illustrative — replace with real delivery telemetry when available.
ASSUMED_LEADS_PER_BUYER = {
    "bronze": 20, "silver": 35, "gold": 50, "platinum": 80,
}

# Conversion pace of the 489 awaiting_payment subs into paid, over 90 days.
SCENARIOS = {
    "conservative": 0.10,
    "base":        0.30,
    "aggressive":  0.60,
}


def _tier_from_plan(plan: str) -> str:
    p = (plan or "").lower()
    for t in TIER_ORDER:
        if t in p:
            return t
    return "silver"  # default marketplace tier


def build_revenue_plan() -> dict:
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row

    # ---- current state ----
    subs = c.execute(
        "SELECT plan, status, price_cents FROM si_subscription"
    ).fetchall()
    active, awaiting = [], []
    for s in subs:
        (active if s["status"] == "active" else awaiting).append(s)

    def _mrr(rows):
        return sum((r["price_cents"] or 0) for r in rows) / 100.0

    active_mrr = _mrr(active)
    awaiting_mrr = _mrr(awaiting)

    # tier mix among ACTIVE buyers
    tier_active = {t: 0 for t in TIER_ORDER}
    tier_await = {t: 0 for t in TIER_ORDER}
    for s in active:
        tier_active[_tier_from_plan(s["plan"])] += 1
    for s in awaiting:
        tier_await[_tier_from_plan(s["plan"])] += 1

    # per-lead modelled monthly revenue from active buyers
    per_lead_monthly = 0.0
    for t in TIER_ORDER:
        n = tier_active[t]
        if n:
            per_lead_monthly += n * ASSUMED_LEADS_PER_BUYER[t] * TIER_RATES[t]["per_lead"]

    current_total_mrr = active_mrr + per_lead_monthly
    current_arr = current_total_mrr * 12

    # ---- forecasts ----
    # seats that would convert, spread linearly across 90 days.
    def _scenario(conv: float) -> dict:
        converted_seats = 0.0
        converted_per_lead = 0.0
        for t in TIER_ORDER:
            n = tier_await[t] * conv
            converted_seats += n * TIER_RATES[t]["monthly"]
            converted_per_lead += n * ASSUMED_LEADS_PER_BUYER[t] * TIER_RATES[t]["per_lead"]
        # 30/60/90 day pacing (linear over 90d window)
        def _at(days):
            pace = min(1.0, days / 90.0)
            return {
                "day": days,
                "seat_mrr": round(active_mrr + converted_seats * pace, 2),
                "per_lead_mrr": round(per_lead_monthly + converted_per_lead * pace, 2),
                "total_mrr": round(current_total_mrr + (converted_seats + converted_per_lead) * pace, 2),
                "total_arr": round((current_total_mrr + (converted_seats + converted_per_lead) * pace) * 12, 2),
                "converted_buyers": round(n_conv_total(conv) * pace, 1),
            }
        return {
            "converted_buyers_total": n_conv_total(conv),
            "d30": _at(30), "d60": _at(60), "d90": _at(90),
        }

    def n_conv_total(conv):
        return round(sum(tier_await[t] * conv for t in TIER_ORDER), 1)

    forecast = {name: _scenario(rate) for name, rate in SCENARIOS.items()}

    plan = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_db": DB,
        "current": {
            "active_buyers": len(active),
            "awaiting_buyers": len(awaiting),
            "active_seat_mrr": round(active_mrr, 2),
            "active_seat_arr": round(active_mrr * 12, 2),
            "awaiting_seat_mrr_pipeline": round(awaiting_mrr, 2),
            "modelled_per_lead_mrr": round(per_lead_monthly, 2),
            "total_mrr": round(current_total_mrr, 2),
            "total_arr": round(current_arr, 2),
            "tier_mix_active": tier_active,
            "tier_mix_awaiting": tier_await,
            "collected_lifetime_usd": _collected(c),
        },
        "collect_blocker": {
            "awaiting_seat_mrr_pipeline": round(awaiting_mrr, 2),
            "root_cause": "apply flow minted empty/vault-mismatched pay URLs; "
                         "fix BSC_WALLET_ADDRESS on hub + auto_onboard default.",
            "fixed": bool(os.environ.get("BSC_WALLET_ADDRESS")),
        },
        "forecast": forecast,
        "assumptions": {
            "tier_rates": TIER_RATES,
            "assumed_leads_per_buyer": ASSUMED_LEADS_PER_BUYER,
            "scenarios": SCENARIOS,
        },
        "access": {
            "cli": "python3 empire_os/revenue_plan.py",
            "hub": "GET http://127.0.0.1:8081/v1/revenue/plan",
            "buyer_apply": "GET https://empire-ai.co.uk/buy-leads  (POST /v1/buyers/apply)",
            "dashboard": "empire_os.revenue_dashboard.RevenueDashboard().get_dashboard_data()",
        },
    }
    c.close()
    try:
        with open(OUT, "w") as f:
            json.dump(plan, f, indent=2)
    except Exception:
        pass
    return plan


def _collected(c) -> float:
    try:
        paid = c.execute(
            "SELECT COALESCE(sum(amount_cents),0) v FROM si_invoice WHERE status='paid'"
        ).fetchone()["v"]
        sett = c.execute(
            "SELECT COALESCE(sum(amount_cents),0) v FROM si_settlements WHERE settled_by!='voided'"
        ).fetchone()["v"]
        return round((paid + sett) / 100.0, 2)
    except Exception:
        return 0.0


if __name__ == "__main__":
    p = build_revenue_plan()
    print(json.dumps(p, indent=2))
