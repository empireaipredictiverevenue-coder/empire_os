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

PROPOSALS = [
    {
        "name": "Empire Global Matchmaker",
        "category": "ai_product",
        "tier": "diamond",
        "build_cost_hours": 32,
        "infra_cost_usdc_monthly": 60,
        "expected_revenue_usdc_monthly": 4500,
        "scores": {"market": 4, "defensibility": 4, "build": 4,
                   "infra_cost": 5, "fy_money": 4},
        "ship_action": {
            "kind": "create_lane",
            "args": {"niche": "global_matchmaker",
                     "metro": "GLOBAL",
                     "rate_per_call_cents": 1500,
                     "rate_per_seat_cents": 200000,
                     "ranking_method": "ai_ranked",
                     "scrapes": True},
        },
    },
    {
        "name": "Empire Niche Autopilot AI",
        "category": "lead_source",
        "tier": "silver",
        "build_cost_hours": 14,
        "infra_cost_usdc_monthly": 18,
        "expected_revenue_usdc_monthly": 1100,
        "scores": {"market": 5, "defensibility": 3, "build": 5,
                   "infra_cost": 5, "fy_money": 3},
        "ship_action": {
            "kind": "create_source",
            "args": {"name": "niche_autopilot",
                     "queries": ["roof replacement quote",
                                "hvac service near me",
                                "kitchen remodel permit"],
                     "source_kind": "search_query_mining",
                     "license": "free"},
        },
    },
    {
        "name": "Empire AI Seller Suite",
        "category": "ops",
        "tier": "empire",
        "build_cost_hours": 80,
        "infra_cost_usdc_monthly": 120,
        "expected_revenue_usdc_monthly": 6500,
        "scores": {"market": 4, "defensibility": 5, "build": 2,
                   "infra_cost": 4, "fy_money": 5},
        "ship_action": {
            "kind": "create_endpoint",
            "args": {"path": "/v1/buyers/onboarding/dashboard",
                     "method": "GET",
                     "delivers": "AI seller dashboard for enterprise tier"},
        },
    },
]


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
    for p in PROPOSALS:
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
