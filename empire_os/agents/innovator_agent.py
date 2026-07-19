#!/usr/bin/env python3
"""
Empire OS v3 - Innovator agent (v4 with ship_action proposals).

Weekly: 3 proposals, each with concrete ship_action (lane creation,
new source, new endpoint) that council can approve.

Cadence: weekly (Monday 06:00 UTC).
"""
import json, os, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path

FB = Path("/root/feedback")
PROP_LOG = FB / "innovator_proposals.jsonl"
ASSESS_LOG = FB / "innovator_assessments.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(7 * 24 * 3600)))

def derive_proposals():
    """Build innovation proposals from LIVE CRM + stack state (not a
    hardcoded list). Targets real gaps: uncollected revenue, untapped
    prospects, monetizable AEO surface."""
    import sqlite3, urllib.request
    props = []
    try:
        crm = sqlite3.connect("/root/empire_os/empire_os.db")
        awaiting_n, awaiting_usd = crm.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_usdc),0) FROM crm_deals "
            "WHERE stage='awaiting_payment'").fetchone()
        contacts = crm.execute("SELECT COUNT(*) FROM crm_contacts").fetchone()[0]
        crm.close()
    except Exception:
        awaiting_n, awaiting_usd, contacts = 0, 0, 0
    try:
        pages = len(json.loads(urllib.request.urlopen(
            "http://127.0.0.1:8081/v1/aeo/pages", timeout=10).read()).get("pages", []))
    except Exception:
        pages = 0

    if awaiting_n > 0:
        props.append({
            "name": "Stuck-Deal Recovery Engine",
            "category": "ops", "tier": "gold",
            "build_cost_hours": 12, "infra_cost_usdc_monthly": 10,
            "expected_revenue_usdc_monthly": int(awaiting_usd * 0.15),
            "scores": {"market": 5, "defensibility": 3, "build": 5,
                       "infra_cost": 5, "fy_money": 5},
            "ship_action": {"kind": "create_endpoint",
                            "args": {"path": "/v1/recovery/sequence",
                                     "method": "POST",
                                     "delivers": "3-touch USDC pay-link recovery on awaiting deals"}},
            "rationale": f"{awaiting_n} seats awaiting payment = ${awaiting_usd:,.0f} uncollected",
        })
    if contacts > 0:
        props.append({
            "name": "AEO Page Pro (Done-For-You SEO)",
            "category": "ai_product", "tier": "silver",
            "build_cost_hours": 20, "infra_cost_usdc_monthly": 15,
            "expected_revenue_usdc_monthly": contacts * 8,
            "scores": {"market": 4, "defensibility": 4, "build": 4,
                       "infra_cost": 5, "fy_money": 4},
            "ship_action": {"kind": "create_lane",
                            "args": {"niche": "aeo_page_pro", "metro": "USA",
                                     "rate_per_seat_cents": 4900, "scrapes": False}},
            "rationale": f"{contacts} prospects + {pages} live AEO pages to upsell",
        })
    if pages > 0:
        props.append({
            "name": "Lead-to-Page Converter",
            "category": "lead_source", "tier": "bronze",
            "build_cost_hours": 8, "infra_cost_usdc_monthly": 5,
            "expected_revenue_usdc_monthly": pages * 2,
            "scores": {"market": 4, "defensibility": 3, "build": 5,
                       "infra_cost": 5, "fy_money": 3},
            "ship_action": {"kind": "create_source",
                            "args": {"name": "page_signup", "source_kind": "aeo_cta", "license": "free"}},
            "rationale": f"{pages} AEO pages generating buyer intent to capture",
        })
    return props


def avg(scores: dict) -> float:
    return sum(scores.values()) / max(len(scores), 1)


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
         "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(PROP_LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    with open(ASSESS_LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    print(json.dumps(e), flush=True)


def cycle():
    out = []
    for p in derive_proposals():
        a = avg(p["scores"])
        decision = "ship" if a >= 3.5 else "park"
        record = {
            "id": "prop_" + uuid.uuid4().hex[:8],
            "ts": datetime.now(timezone.utc).isoformat(),
            "name": p["name"],
            "category": p["category"],
            "tier": p["tier"],
            "build_cost_hours": p["build_cost_hours"],
            "infra_cost_usdc_monthly": p["infra_cost_usdc_monthly"],
            "expected_revenue_usdc_monthly": p["expected_revenue_usdc_monthly"],
            "scores": p["scores"],
            "average_score": a,
            "ship_action": p["ship_action"],
            "decision": decision,
        }
        out.append(record)
        log("PROPOSAL", "emitted",
            id=record["id"], name=p["name"],
            avg=a, decision=decision)
    return out


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] innovator v4 online - weekly cadence",
          flush=True)
    while True:
        try:
            cycle()
        except Exception as e:
            with open("/root/feedback/innovator_proposals.jsonl", "a") as f:
                f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                                    "level": "ERROR",
                                    "msg": "cycle_failed",
                                    "err": str(e)[:200]}) + "\n")
        time.sleep(INTERVAL)
