"""Empire Predictive Per Region — Empire OS v3
==============================================
Runs hourly per region to produce:
1. Revenue projection (active seats MRR + projected new MRR)
2. Market gaps (hot → raise price, unsaturated → recruit, dead → kill/pivot)
3. Leaks (funnel drop-offs with inferred cause)
4. Waste (over-resourced lanes, idle agents, error hotspots)
5. National demand forecast (cross-region aggregation)

Outputs: /root/feedback/predictive_<region>_<timestamp>.json
Feeds: cortex_brain_loop for strategic decisions
"""

from __future__ import annotations
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add empire_os to path
sys.path.insert(0, "/root/empire_os")

try:
    from empire_os.predictive import (
        predict_revenue,
        detect_market_gaps,
        detect_leaks,
        detect_waste,
    )
except ImportError:
    # Fallback inline implementations
    def predict_revenue(**kwargs):
        return {"active_seats_mrr": 0, "projected_new_mrr": 0, "total_predicted_mrr": 0, "unrealized_mrr": 0}
    def detect_market_gaps(lanes, leads):
        return {"hot_gaps": [], "unsaturated": [], "dead": [], "counts": {"hot": 0, "unsaturated": 0, "dead": 0}}
    def detect_leaks(funnel):
        return {"total_leaked": 0, "leaks": []}
    def detect_waste(lanes, agents):
        return {"total_waste_indicators": 0, "waste_lanes": []}


DB = "/root/empire_os/empire_os.db"
FEEDBACK_DIR = Path("/root/feedback")
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

# Regional hub configurations
REGIONS = {
    "usa-east": {
        "metros": ["NYC", "BOS", "PHL", "WDC", "ATL", "MIA"],
        "hub_id": "usa-east-hub",
    },
    "usa-central": {
        "metros": ["CHI", "DFW", "HOU", "DEN", "DET"],
        "hub_id": "usa-central-hub",
    },
    "usa-west": {
        "metros": ["LAX", "SFO", "SEA", "PHX", "PDX", "SAT", "AUS", "LAS"],
        "hub_id": "usa-west-hub",
    },
}

# Default region if none specified
DEFAULT_REGION = "usa-east"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def gather_region_state(region: str) -> Dict[str, Any]:
    """Pull live state from DB for a specific region."""
    metros = REGIONS[region]["metros"]
    placeholders = ",".join("?" * len(metros))
    
    con = _db()
    try:
        c = con.cursor()
        state = {"region": region, "metros": metros}
        
        # Lane counts for region
        c.execute(f"SELECT COUNT(*) FROM lanes WHERE metro IN ({placeholders})", metros)
        state["lane_count"] = c.fetchone()[0]
        
        c.execute(
            f"SELECT COUNT(*) FROM lanes WHERE occupied_by IS NOT NULL AND occupied_by != '' AND metro IN ({placeholders})",
            metros
        )
        state["occupied_lanes"] = c.fetchone()[0]
        
        # Lead counts for region - check both metro and metros columns
        metro_conditions = " OR ".join([f"(metro = ? OR metros LIKE '%' || ? || '%')" for _ in metros])
        params = []
        for m in metros:
            params.extend([m, m])
        
        c.execute(f"SELECT COUNT(*) FROM si_buyer_outreach WHERE {metro_conditions}", params)
        state["leads_total"] = c.fetchone()[0]
        
        c.execute(
            f"SELECT COUNT(*) FROM si_buyer_outreach WHERE ({metro_conditions}) AND created_at > datetime('now', '-1 day')",
            params
        )
        state["leads_today"] = c.fetchone()[0]
        
        # Funnel states
        funnel = {}
        c.execute("SELECT status, COUNT(*) FROM si_subscription GROUP BY status")
        for st, n in c.fetchall():
            funnel[st] = n
        c.execute("SELECT stage, COUNT(*) FROM crm_deals GROUP BY stage")
        for st, n in c.fetchall():
            funnel[st] = funnel.get(st, 0) + n
        state["funnel"] = funnel
        
        # Avg seat price
        avg_seat = c.execute(
            "SELECT AVG(price_cents) FROM si_subscription WHERE price_cents > 0"
        ).fetchone()[0] or 59900
        state["avg_seat_price"] = avg_seat / 100.0
        
        # Buyer pricing
        c.execute(f"SELECT COUNT(*) FROM si_buyer_outreach WHERE {metro_conditions} AND active = 1", params)
        state["buyers_total"] = c.fetchone()[0]
        c.execute(
            f"SELECT COUNT(*) FROM si_buyer_outreach WHERE {metro_conditions} AND active = 1 AND payout_per_lead > 0",
            params
        )
        state["buyers_priced"] = c.fetchone()[0]
        c.execute(
            f"SELECT COUNT(*) FROM si_buyer_outreach WHERE {metro_conditions} AND active = 1 AND endpoint_url != ''",
            params
        )
        state["buyers_with_endpoint"] = c.fetchone()[0]
        
        # Settlements - si_settlements doesn't have metro, count all for now
        c.execute("SELECT COUNT(*) FROM si_settlements")
        state["settlements_paid"] = c.fetchone()[0]
        
        # Lane data for market gaps
        state["lanes"] = c.execute(
            f"SELECT sub_niche, metro, occupied_by, seat_price FROM lanes WHERE metro IN ({placeholders})",
            metros
        ).fetchall()
        
        # Lead data for market gaps - check both metro and metros columns
        lead_metro_conditions = " OR ".join([f"(metro = ? OR metros LIKE '%' || ? || '%')" for _ in metros])
        lead_params = []
        for m in metros:
            lead_params.extend([m, m])
        state["leads"] = c.execute(
            f"SELECT niche, metro FROM si_buyer_outreach WHERE niche != '' AND ({lead_metro_conditions}) LIMIT 500",
            lead_params
        ).fetchall()
        
        return state
    finally:
        con.close()


def run_predictive_analysis(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the 4-pillar predictive analysis on region state."""
    lanes = [dict(r) for r in state.get("lanes", [])]
    leads = [dict(r) for r in state.get("leads", [])]
    
    # Pillar 1: Predictive Revenue
    revenue = predict_revenue(
        lane_count=state["lane_count"],
        occupied_lanes=state["occupied_lanes"],
        leads_total=state["leads_total"],
        funnel_by_state=state["funnel"],
        avg_seat_price=state["avg_seat_price"],
        conversion_rate=0.05,
    )
    
    # Pillar 2: Market Gaps
    gaps = detect_market_gaps(lanes, leads)
    
    # Pillar 3: Leaks
    leaks = detect_leaks(state["funnel"])
    
    # Pillar 4: Waste
    waste = detect_waste(lanes, {})
    
    return {
        "revenue": revenue,
        "market_gaps": gaps,
        "leaks": leaks,
        "waste": waste,
        "state_summary": {
            "region": state["region"],
            "metros": state["metros"],
            "lane_count": state["lane_count"],
            "occupied_lanes": state["occupied_lanes"],
            "leads_total": state["leads_total"],
            "leads_today": state["leads_today"],
            "buyers_total": state["buyers_total"],
            "buyers_priced": state["buyers_priced"],
            "settlements_paid": state["settlements_paid"],
            "avg_seat_price": state["avg_seat_price"],
        },
    }


def build_national_forecast(regional_results: List[Dict]) -> Dict[str, Any]:
    """Aggregate cross-region results into national demand forecast."""
    total_lanes = sum(r["state_summary"]["lane_count"] for r in regional_results)
    total_occupied = sum(r["state_summary"]["occupied_lanes"] for r in regional_results)
    total_leads = sum(r["state_summary"]["leads_total"] for r in regional_results)
    total_leads_today = sum(r["state_summary"]["leads_today"] for r in regional_results)
    total_buyers = sum(r["state_summary"]["buyers_total"] for r in regional_results)
    total_buyers_priced = sum(r["state_summary"]["buyers_priced"] for r in regional_results)
    total_settlements = sum(r["state_summary"]["settlements_paid"] for r in regional_results)
    total_mrr = sum(r["revenue"].get("active_seats_mrr", 0) for r in regional_results)
    total_projected_mrr = sum(r["revenue"].get("projected_new_mrr", 0) for r in regional_results)
    
    # Aggregate hot gaps across regions
    all_hot_gaps = []
    all_unsaturated = []
    all_dead = []
    for r in regional_results:
        all_hot_gaps.extend(r["market_gaps"].get("hot_gaps", []))
        all_unsaturated.extend(r["market_gaps"].get("unsaturated", []))
        all_dead.extend(r["market_gaps"].get("dead", []))
    
    # Top 10 national hot gaps
    hot_by_demand = sorted(all_hot_gaps, key=lambda x: x.get("demand_score", 0), reverse=True)[:10]
    
    # Auto-inventory new lanes from unsaturated markets
    new_lane_opportunities = []
    for gap in all_unsaturated[:10]:
        new_lane_opportunities.append({
            "niche_metro": gap.get("niche_metro"),
            "action": "open_new_lane",
            "rationale": gap.get("rationale"),
            "estimated_demand": gap.get("demand_score"),
        })
    
    # Price optimization from hot gaps
    price_pivots = []
    for gap in all_hot_gaps[:10]:
        price_pivots.append({
            "niche_metro": gap.get("niche_metro"),
            "action": "raise_price",
            "new_price_usd": int(gap.get("current_price", 10) * 1.3),
            "rationale": f"High occupancy + high demand: {gap.get('rationale')}",
        })
    
    return {
        "timestamp": now_iso(),
        "national_summary": {
            "total_lanes": total_lanes,
            "total_occupied": total_occupied,
            "occupancy_rate": total_occupied / max(total_lanes, 1),
            "total_leads": total_leads,
            "total_leads_today": total_leads_today,
            "total_buyers": total_buyers,
            "total_buyers_priced": total_buyers_priced,
            "total_settlements": total_settlements,
            "active_mrr": total_mrr,
            "projected_new_mrr": total_projected_mrr,
            "total_predicted_mrr": total_mrr + total_projected_mrr,
        },
        "top_hot_gaps": hot_by_demand,
        "new_lane_opportunities": new_lane_opportunities,
        "price_pivots": price_pivots,
        "regions_analyzed": len(regional_results),
    }


def emit_region_predictive(region: str, analysis: Dict[str, Any]) -> Path:
    """Write region predictive output."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = FEEDBACK_DIR / f"predictive_{region}_{ts}.json"
    
    output = {
        "region": region,
        "timestamp": now_iso(),
        **analysis,
    }
    
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(output, indent=2, default=str))
    tmp.replace(path)
    return path


def emit_national_forecast(forecast: Dict[str, Any]) -> Path:
    """Write national forecast output."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = FEEDBACK_DIR / f"predictive_national_{ts}.json"
    
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(forecast, indent=2, default=str))
    tmp.replace(path)
    return path


def run_region(region: str) -> Dict[str, Any]:
    """Run predictive analysis for one region."""
    print(f"[predictive] Running for region: {region}")
    
    state = gather_region_state(region)
    analysis = run_predictive_analysis(state)
    
    # Emit region output
    path = emit_region_predictive(region, analysis)
    print(f"[predictive] Region {region} output: {path}")
    
    return {"region": region, "analysis": analysis, "output_path": str(path)}


def run_all_regions() -> Dict[str, Any]:
    """Run predictive for all regions and build national forecast."""
    print(f"[predictive] Running for all {len(REGIONS)} regions")
    
    regional_results = []
    for region in REGIONS:
        try:
            result = run_region(region)
            regional_results.append(result)
        except Exception as e:
            print(f"[predictive] ERROR region {region}: {e}")
    
    # Build national forecast
    national = build_national_forecast([r["analysis"] for r in regional_results])
    path = emit_national_forecast(national)
    print(f"[predictive] National forecast: {path}")
    
    return {
        "regions": regional_results,
        "national_forecast": national,
        "national_output": str(path),
    }


def run_daemon(interval_sec: int = 3600):
    """Run as daemon, executing every interval_sec seconds."""
    print(f"[predictive] Daemon starting, interval={interval_sec}s")
    while True:
        try:
            run_all_regions()
        except Exception as e:
            print(f"[predictive] Daemon cycle failed: {e}")
        time.sleep(interval_sec)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Empire Predictive Per Region")
    parser.add_argument("--region", choices=list(REGIONS.keys()) + ["all"], default="all")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--interval", type=int, default=3600, help="Daemon interval seconds")
    args = parser.parse_args()
    
    if args.daemon:
        run_daemon(args.interval)
    elif args.region == "all":
        run_all_regions()
    else:
        run_region(args.region)