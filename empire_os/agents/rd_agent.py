#!/usr/bin/env python3
"""
Empire OS v3 — R&D Agent
========================

Continuous background agent that:
1. Connects north_mini_agent to northmini_realstate for truthful planning (already done)
2. Wires enterprise_campaigns to outreach_runner/lead_deliverer for execution
3. Activates whale_harvester to harvest high-value prospects
4. Reports status and revenue impact

This agent runs as a systemd service and orchestrates the revenue loop:
- Reads real state from DB via northmini_realstate
- Creates/launches enterprise campaigns on live audiences
- Triggers lead delivery to seated buyers
- Harvests whales from free sources (HN, GitHub)
- Reports KPIs to feedback loop

Architecture:
  north_mini_agent (strategy) ──reads──► northmini_realstate (truth)
                                          │
                                          ▼
  enterprise_campaigns ──creates──► outbound_campaigns (draft)
                                          │
                                          ▼
  campaigns.launch() ──activates──► lead_deliverer_agent.tick_once()
                                          │
                                          ▼
                              Deliver leads → bill buyers → revenue
                                          │
                                          ▼
  whale_harvester ──harvests──► si_prospect_consent (WHALE tier)
                                          │
                                          ▼
                              Chief of Staff dials whales
"""

import json
import os
import sqlite3
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")
FEEDBACK_DIR = Path("/root/feedback")
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
RND_LOG = FEEDBACK_DIR / "rd_agent.jsonl"
RND_REPORT = FEEDBACK_DIR / "rd_report.json"

TICK_SECONDS = int(os.environ.get("RND_TICK", "900"))  # 15 min default
MODEL = os.environ.get("RND_MODEL", "tencent/hy3:free")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(level: str, msg: str, **fields):
    event = {"ts": _now(), "level": level, "msg": msg, **fields}
    with open(RND_LOG, "a") as f:
        f.write(json.dumps(event) + "\n")
    if level in ("ERROR", "WARN", "INFO"):
        print(json.dumps(event), flush=True)


def read_real_state() -> dict:
    """Read real state using northmini_realstate for truthful counts."""
    from empire_os.northmini_realstate import real_state
    return real_state()


def run_enterprise_campaigns() -> dict:
    """Create enterprise campaigns on real audiences."""
    from empire_os.enterprise_campaigns import build
    real = read_real_state()
    _log("INFO", "enterprise_campaigns: creating from real state", real_state=real)
    try:
        created = build()
        return {"ok": True, "created": created, "real_state": real}
    except Exception as e:
        _log("ERROR", "enterprise_campaigns failed", error=str(e))
        return {"ok": False, "error": str(e)}


def launch_campaigns() -> dict:
    """Launch all draft campaigns to active, triggering lead delivery."""
    from empire_os.campaigns import list_all, launch
    try:
        all_campaigns = list_all()
        draft_campaigns = [c for c in all_campaigns if c["status"] == "draft"]
        _log("INFO", "launching campaigns", count=len(draft_campaigns))
        
        results = []
        for camp in draft_campaigns:
            result = launch(camp["id"])
            results.append(result)
            _log("INFO", "campaign launched", campaign=camp["name"], result=result)
        
        return {"ok": True, "launched": results}
    except Exception as e:
        _log("ERROR", "launch_campaigns failed", error=str(e))
        return {"ok": False, "error": str(e)}


def run_whale_harvester() -> dict:
    """Harvest high-value prospects from free sources."""
    from empire_os.agents.whale_harvester import run_once
    _log("INFO", "whale_harvester: running harvest")
    try:
        result = run_once()
        _log("INFO", "whale_harvester: harvest complete", result=result)
        return {"ok": True, "result": result}
    except Exception as e:
        _log("ERROR", "whale_harvester failed", error=str(e))
        return {"ok": False, "error": str(e)}


def get_revenue_metrics() -> dict:
    """Get current revenue metrics from DB."""
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    metrics = {}
    try:
        queries = {
            "total_settlements_usdc": "SELECT COALESCE(SUM(amount_cents),0)/100.0 FROM si_settlements",
            "evaluation_settlements_usdc": "SELECT COALESCE(SUM(amount_cents),0)/100.0 FROM evaluation_settlements",
            "ppc_invoices_open": "SELECT COALESCE(SUM(amount_cents),0)/100.0 FROM si_ppc_invoices WHERE status='open'",
            "ppc_invoices_paid": "SELECT COALESCE(SUM(amount_cents),0)/100.0 FROM si_ppc_invoices WHERE status='paid'",
            "charges_paid": "SELECT COALESCE(SUM(amount_cents),0)/100.0 FROM si_charges WHERE status='succeeded'",
            "subscriptions_active": "SELECT COUNT(*) FROM si_subscription WHERE status='active'",
            "tenants_total": "SELECT COUNT(*) FROM si_tenant",
            "lanes_occupied": "SELECT COUNT(*) FROM lanes WHERE occupied_by IS NOT NULL",
            "delivered_leads": "SELECT COUNT(*) FROM delivered_leads",
            "whales_harvested": "SELECT COUNT(*) FROM si_prospect_consent WHERE whale_tier='WHALE'",
        }
        for k, q in queries.items():
            try:
                row = c.execute(q).fetchone()
                metrics[k] = dict(row).get(list(row.keys())[0], 0) if row else 0
            except Exception:
                metrics[k] = 0
        
        # Calculate MRR
        metrics["active_seats_mrr"] = metrics.get("lanes_occupied", 0) * 999  # enterprise tier
        metrics["projected_new_mrr"] = 0  # would need funnel velocity
        metrics["total_predicted_mrr"] = metrics["active_seats_mrr"]
        
    finally:
        c.close()
    return metrics


def get_campaign_metrics() -> dict:
    """Get campaign metrics from outbound_campaigns."""
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    metrics = {}
    try:
        queries = {
            "campaigns_total": "SELECT COUNT(*) FROM outbound_campaigns",
            "campaigns_active": "SELECT COUNT(*) FROM outbound_campaigns WHERE status='active'",
            "campaigns_draft": "SELECT COUNT(*) FROM outbound_campaigns WHERE status='draft'",
            "campaigns_sent": "SELECT COALESCE(SUM(sent),0) FROM outbound_campaigns",
            "campaigns_billed": "SELECT COALESCE(SUM(billed),0) FROM outbound_campaigns",
            "campaigns_collected": "SELECT COALESCE(SUM(collected),0) FROM outbound_campaigns",
        }
        for k, q in queries.items():
            try:
                row = c.execute(q).fetchone()
                metrics[k] = dict(row).get(list(row.keys())[0], 0) if row else 0
            except Exception:
                metrics[k] = 0
    finally:
        c.close()
    return metrics


def run_cycle() -> dict:
    """One R&D agent cycle: create campaigns, launch, harvest whales, report."""
    t0 = time.time()
    _log("INFO", "rd_agent: cycle start")
    
    # 1. Read real state (truthful planning)
    real_state = read_real_state()
    
    # 2. Create enterprise campaigns from real state
    campaigns_result = run_enterprise_campaigns()
    
    # 3. Launch campaigns to active (triggers lead delivery)
    launch_result = launch_campaigns()
    
    # 4. Harvest whales
    whale_result = run_whale_harvester()
    
    # 5. Get metrics
    revenue_metrics = get_revenue_metrics()
    campaign_metrics = get_campaign_metrics()
    
    elapsed = round(time.time() - t0, 1)
    
    cycle_report = {
        "ts": _now(),
        "elapsed_seconds": elapsed,
        "real_state": real_state,
        "campaigns": campaigns_result,
        "launch": launch_result,
        "whale_harvest": whale_result,
        "revenue_metrics": revenue_metrics,
        "campaign_metrics": campaign_metrics,
    }
    
    # Write report
    with open(RND_REPORT, "w") as f:
        json.dump(cycle_report, f, indent=2, default=str)
    
    _log("INFO", "rd_agent: cycle complete", 
         elapsed=elapsed,
         campaigns_created=len(campaigns_result.get("created", [])) if campaigns_result.get("ok") else 0,
         campaigns_launched=len(launch_result.get("launched", [])) if launch_result.get("ok") else 0,
         whales_harvested=whale_result.get("result", {}).get("persisted", 0) if whale_result.get("ok") else 0,
         total_predicted_mrr=revenue_metrics.get("total_predicted_mrr", 0))
    
    return cycle_report


def main():
    print(f"[rd_agent] loop start tick={TICK_SECONDS}s model={MODEL}", flush=True)
    
    # Run once immediately on startup
    run_cycle()
    
    while True:
        try:
            run_cycle()
        except Exception as e:
            _log("ERROR", "rd_agent cycle crashed", error=str(e))
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main()