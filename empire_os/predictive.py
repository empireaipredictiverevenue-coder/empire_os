"""
Predictive Revenue + Market Gap Detector
========================================

Three jobs:
1. **Predictive revenue formula** — projects MRR from current funnel + lane
   occupancy + conversion rates. Catches problems BEFORE the month closes.

2. **Market gap detector** — finds niches where demand > supply. Surfaces
   the gap as a $ opportunity.

3. **Leak detector** — finds where leads/money are dropping out of the
   pipeline. Funnel drop-offs, lane vacancies, dead niches.

4. **Waste detector** — finds over-resourced lanes with low conversion,
   agents burning cycles with no output, repeated errors.

Each output is a structured report that the operator can act on.
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("predictive")

DB_PATH = "/root/empire_os/empire_os.db"


# ─────────────────────────────────────────────────────────────────
# 1. PREDICTIVE REVENUE FORMULA
# ─────────────────────────────────────────────────────────────────

def predict_revenue(
    lane_count: int,
    occupied_lanes: int,
    leads_total: int,
    funnel_by_state: dict,
    avg_seat_price: float = 500.0,  # $/seat/month default
    conversion_rate: float = 0.05,  # lead → paid customer baseline
) -> dict:
    """Predict monthly recurring revenue from current state.

    Formula:
      active_seats = occupied_lanes × avg_seat_price
      projected_new_customers = leads_total × conversion_rate
      funnel_velocity = matched→claimed ratio × (1 - drop-off)
      predicted_mrr = active_seats + projected_new_customers × seat_price
      confidence = function of data volume
    """
    active_seats = occupied_lanes * avg_seat_price
    projected_new_customers = leads_total * conversion_rate

    matched = funnel_by_state.get("matched", 0)
    claimed = funnel_by_state.get("claimed", 0)
    settled = funnel_by_state.get("settled", 0)
    total_in_funnel = matched + claimed + settled

    funnel_velocity = 0.0
    if total_in_funnel > 0:
        settled_rate = settled / total_in_funnel
        claimed_rate = claimed / total_in_funnel
        funnel_velocity = (claimed_rate + settled_rate) / 2.0

    predicted_new_mrr = projected_new_customers * avg_seat_price * funnel_velocity

    empty_lanes = lane_count - occupied_lanes
    potential_mrr = lane_count * avg_seat_price
    unrealized = (empty_lanes / max(lane_count, 1)) * potential_mrr

    sample_size = leads_total + total_in_funnel
    confidence = min(1.0, math.log10(max(sample_size, 1)) / 3.0)

    return {
        "active_seats_mrr": round(active_seats, 2),
        "projected_new_customers": round(projected_new_customers, 1),
        "projected_new_mrr": round(predicted_new_mrr, 2),
        "total_predicted_mrr": round(active_seats + predicted_new_mrr, 2),
        "potential_mrr_if_full": round(potential_mrr, 2),
        "unrealized_mrr": round(unrealized, 2),
        "funnel_velocity": round(funnel_velocity, 3),
        "confidence": round(confidence, 2),
        "formula_version": "v1",
    }


# ─────────────────────────────────────────────────────────────────
# 2. MARKET GAP DETECTOR
# ─────────────────────────────────────────────────────────────────

def detect_market_gaps(
    lane_data: list,
    lead_data: list,
    lead_threshold: int = 5,
    occupancy_threshold: float = 0.7,
) -> dict:
    """Find niches where demand exists but supply (lane occupancy) is high
    OR where occupancy is low and so is demand (dead market).

    Returns:
      - hot_gaps: niches with high occupancy + rising lead volume (price up)
      - dead_markets: niches with low leads + low occupancy (kill or pivot)
      - unsaturated: low occupancy + healthy leads (recruit providers)
    """
    lane_by_niche = defaultdict(lambda: {"total": 0, "occupied": 0})
    for lane in lane_data:
        sub = lane.get("sub_niche", "")
        m = lane.get("metro", "")
        key = "%s:%s" % (sub, m)
        lane_by_niche[key]["total"] += 1
        if lane.get("occupied_by"):
            lane_by_niche[key]["occupied"] += 1

    leads_by_niche_metro = defaultdict(int)
    for lead in lead_data:
        niche = lead.get("niche", "")
        metro = lead.get("metro", "") or lead.get("state", "")
        leads_by_niche_metro["%s:%s" % (niche, metro)] += 1

    hot_gaps = []
    dead_markets = []
    unsaturated = []

    for key, lane_info in lane_by_niche.items():
        occupancy = lane_info["occupied"] / max(lane_info["total"], 1)
        leads = leads_by_niche_metro.get(key, 0)

        if occupancy >= occupancy_threshold and leads >= lead_threshold:
            hot_gaps.append({
                "niche_metro": key,
                "occupancy": round(occupancy, 2),
                "leads": leads,
                "action": "raise_seat_price",
                "rationale": "high demand + high occupancy = price elasticity test",
            })
        elif leads < 2 and occupancy < 0.3:
            dead_markets.append({
                "niche_metro": key,
                "occupancy": round(occupancy, 2),
                "leads": leads,
                "action": "kill_or_pivot",
                "rationale": "no demand, no supply — dead market",
            })
        elif occupancy < 0.5 and leads >= lead_threshold:
            unsaturated.append({
                "niche_metro": key,
                "occupancy": round(occupancy, 2),
                "leads": leads,
                "action": "recruit_providers",
                "rationale": "demand exists, supply thin — recruit",
            })

    hot_gaps.sort(key=lambda x: -x["leads"])
    unsaturated.sort(key=lambda x: -x["leads"])
    dead_markets.sort(key=lambda x: x["leads"])

    return {
        "hot_gaps": hot_gaps[:20],
        "dead_markets": dead_markets[:20],
        "unsaturated": unsaturated[:20],
        "counts": {
            "hot": len(hot_gaps),
            "dead": len(dead_markets),
            "unsaturated": len(unsaturated),
        },
    }


# ─────────────────────────────────────────────────────────────────
# 3. LEAK DETECTOR
# ─────────────────────────────────────────────────────────────────

def detect_leaks(funnel_by_state: dict) -> dict:
    """Find where leads are dropping out of the funnel.

    Looks at ratios between consecutive funnel states. A big drop
    between matched → outreach_drafted = leak in the matching layer.
    """
    states_order = [
        "discovered", "matched", "outreach_drafted",
        "outreach_sent", "replied", "claimed", "settled",
    ]

    leaks = []
    for i in range(len(states_order) - 1):
        from_state = states_order[i]
        to_state = states_order[i + 1]
        from_count = funnel_by_state.get(from_state, 0)
        to_count = funnel_by_state.get(to_state, 0)

        if from_count == 0:
            continue

        pass_rate = to_count / from_count
        drop_count = from_count - to_count

        if pass_rate < 0.3 and from_count >= 5:
            severity = "HIGH" if drop_count > 20 else "MEDIUM"
            leaks.append({
                "from_state": from_state,
                "to_state": to_state,
                "from_count": from_count,
                "to_count": to_count,
                "drop_count": drop_count,
                "pass_rate": round(pass_rate, 2),
                "severity": severity,
                "likely_cause": _infer_leak_cause(from_state, to_state),
            })

    return {
        "leaks": sorted(leaks, key=lambda x: -x["drop_count"]),
        "total_leaked": sum(l["drop_count"] for l in leaks),
        "funnel_states_observed": {s: funnel_by_state.get(s, 0) for s in states_order},
    }


def _infer_leak_cause(from_state: str, to_state: str) -> str:
    causes = {
        ("discovered", "matched"): "scoring too loose OR niche mismatch in routing",
        ("matched", "outreach_drafted"): "outreach agent bottleneck OR copy quality",
        ("outreach_drafted", "outreach_sent"): "drafts sitting in queue, no operator approval",
        ("outreach_sent", "replied"): "subject lines not converting OR message too generic",
        ("replied", "claimed"): "lead interested but no scheduling slot offered",
        ("claimed", "settled"): "payment friction OR follow-up lapse",
    }
    return causes.get((from_state, to_state), "investigate manually")


# ─────────────────────────────────────────────────────────────────
# 4. WASTE DETECTOR
# ─────────────────────────────────────────────────────────────────

def detect_waste(
    lane_data: list,
    agent_health: dict,
    error_log_lines: int = 0,
) -> dict:
    """Find over-resourced lanes with low conversion, agents burning
    cycles with no output, and error hot spots.
    """
    waste_lanes = []
    for lane in lane_data:
        if not lane.get("occupied_by"):
            continue
        if lane.get("seat_price", 0) > 1000:
            waste_lanes.append({
                "lane_id": lane.get("id"),
                "seat_price": lane.get("seat_price"),
                "metro": lane.get("metro"),
                "concern": "high-price lane — verify conversion justifies cost",
            })

    waste_agents = []
    for name, info in agent_health.items():
        if not info.get("running") and info.get("role") != "hub":
            waste_agents.append({"agent": name, "issue": "not running"})
        elif info.get("log_lines", 0) == 0 and info.get("running"):
            waste_agents.append({"agent": name, "issue": "running but no output"})

    waste_hotspots = []
    if error_log_lines > 100:
        waste_hotspots.append({
            "scope": "global_logs",
            "error_lines": error_log_lines,
            "action": "review logs, fix recurring errors",
        })

    return {
        "waste_lanes": waste_lanes[:20],
        "waste_agents": waste_agents[:20],
        "waste_hotspots": waste_hotspots,
        "total_waste_indicators": len(waste_lanes) + len(waste_agents) + len(waste_hotspots),
    }


# ─────────────────────────────────────────────────────────────────
# 5. FULL DAILY REPORT
# ─────────────────────────────────────────────────────────────────

def generate_daily_report(hub_container: str = "empire-hub", db_path: str = "/root/empire_os/empire_os.db") -> dict:
    """Pull state from hub DB (inside container) and generate the full predictive report."""
    import subprocess

    pull_script = '''
import json, sqlite3
c = sqlite3.connect("{db_path}")
c.row_factory = sqlite3.Row

cur = c.execute("SELECT COUNT(*) as c, SUM(CASE WHEN occupied_by IS NOT NULL THEN 1 ELSE 0 END) as occ FROM lanes")
row = cur.fetchone()
result = {{"lane_count": row["c"] or 0, "occupied": row["occ"] or 0}}

cur = c.execute("SELECT id, category, sub_niche, metro, occupied_by, seat_price FROM lanes")
result["lanes"] = [dict(r) for r in cur.fetchall()]

cur = c.execute("SELECT niche, metro, status FROM lane_leads ORDER BY created_at DESC LIMIT 500")
result["leads"] = [dict(r) for r in cur.fetchall()]

cur = c.execute("SELECT COUNT(*) as c FROM lane_leads")
result["leads_total"] = cur.fetchone()["c"] or 0

funnel = {{}}
cur = c.execute("""
    SELECT to_state, COUNT(*) as c FROM (
        SELECT prospect_id, to_state, MAX(id) as max_id
        FROM si_funnel_event
        GROUP BY prospect_id
    ) GROUP BY to_state
""")
for r in cur.fetchall():
    funnel[r["to_state"]] = r["c"]
result["funnel"] = funnel

print(json.dumps(result))
'''.format(db_path=db_path)

    import sys
    try:
        r = subprocess.run(
            ["incus", "exec", hub_container, "--", "/root/venv/bin/python3", "-c", pull_script],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return {"error": "hub query failed", "stderr": r.stderr[:500]}
        data = json.loads(r.stdout.strip().split("\n")[-1])
    except Exception as e:
        return {"error": "hub unreachable", "detail": str(e)}

    revenue = predict_revenue(
        lane_count=data["lane_count"],
        occupied_lanes=data["occupied"],
        leads_total=data["leads_total"],
        funnel_by_state=data["funnel"],
    )

    gaps = detect_market_gaps(data["lanes"], data["leads"])
    leaks = detect_leaks(data["funnel"])
    waste = detect_waste(data["lanes"], agent_health={})

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "revenue": revenue,
        "market_gaps": gaps,
        "leaks": leaks,
        "waste": waste,
        "totals": {
            "lanes": data["lane_count"],
            "occupied": data["occupied"],
            "leads": data["leads_total"],
        },
    }


if __name__ == "__main__":
    report = generate_daily_report()
    out = Path("/root/feedback/predictive_%s.json" % datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    print("Revenue projection:")
    print("  Active seats MRR:    $%s" % report["revenue"]["active_seats_mrr"])
    print("  Projected new MRR:   $%s" % report["revenue"]["projected_new_mrr"])
    print("  Total predicted MRR: $%s" % report["revenue"]["total_predicted_mrr"])
    print("  Unrealized MRR:      $%s" % report["revenue"]["unrealized_mrr"])
    print("  Confidence:          %s" % report["revenue"]["confidence"])
    print()
    print("Market gaps:")
    print("  Hot:        %d" % report["market_gaps"]["counts"]["hot"])
    print("  Unsaturated: %d" % report["market_gaps"]["counts"]["unsaturated"])
    print("  Dead:       %d" % report["market_gaps"]["counts"]["dead"])
    print()
    print("Leaks:")
    print("  Total dropped: %d" % report["leaks"]["total_leaked"])
    print()
    print("Waste indicators: %d" % report["waste"]["total_waste_indicators"])
    print()
    print("Full report: %s" % out)


# Backward-compat aliases (must be after function definitions)
market_gaps = detect_market_gaps