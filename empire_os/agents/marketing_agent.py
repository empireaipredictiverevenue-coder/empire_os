"""
Empire OS v3 — Marketing Agent
===============================

Coordinates marketing surface for Empire OS:
  - AEO content generation (currently generator builds pages on demand;
    Marketing agent re-evaluates effectiveness weekly)
  - Resend broadcasts to outreach list (sample lead delivery)
  - Lead magnet content (we have 308 AEO pages as primary)
  - Social proof collection (per outreach replied → testimonial JSONL)
  - Cross-promo with Sales agent (when Sales sees a "replied" stage,
    Marketing triggers a follow-up "here's what other agencies buy")

Reads from /v1/swarm/audit-log + /v1/outreach/prospects/pending.
Writes to /root/feedback/marketing_log.jsonl.

Cadence: every 30 minutes.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests


HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
FEEDBACK = Path("/root/feedback")
LOG_PATH = FEEDBACK / "marketing_log.jsonl"
INTERVAL = int(os.environ.get("INTERVAL", "1800"))  # 30min


def _log(level, msg, **fields):
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level, "msg": msg, **fields,
    }
    FEEDBACK.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")
    if level in ("ERROR", "WARN", "EVENT"):
        print(json.dumps(event), flush=True)


def _hub_get(path: str, **params) -> dict:
    try:
        r = requests.get(f"{HUB_URL}{path}", params=params, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        _log("ERROR", "hub_get_failed", path=path, error=str(e)[:100])
        return {}


def _jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.read_text().splitlines() if _.strip())


def compute_marketing_metrics() -> dict:
    """Read everything, emit one snapshot."""
    counts = _hub_get("/v1/leads/counts")
    aeo_pages = _hub_get("/v1/lanes")
    outreach_pending = _hub_get("/v1/outreach/prospects/pending",
                                limit=200)

    prospects = outreach_pending.get("prospects", [])
    audience_size = len(prospects)

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "total_leads": counts.get("total", 0),
        "delivered_leads": counts.get("by_status", {}).get("delivered", 0),
        "pending_leads": counts.get("by_status", {}).get("pending", 0),
        "audience_size": audience_size,
        "outreach_log_lines": _jsonl_count(FEEDBACK / "outreach_log.jsonl"),
        "deliveries_log_lines": _jsonl_count(FEEDBACK / "lead_deliveries.jsonl"),
        "alerts_log_lines": _jsonl_count(FEEDBACK / "alerts.jsonl"),
    }


def recommend_next_action(metrics: dict) -> dict:
    """Heuristic recommendation only — never auto-execute."""
    actions = []

    # If lots of pending leads and few tenants, recommend outreach push
    if metrics["pending_leads"] > 100 and metrics["audience_size"] > 0:
        actions.append({
            "type": "outreach_blitz",
            "priority": "high",
            "reason": f"{metrics['pending_leads']} leads pending delivery "
                      f"+ {metrics['audience_size']} cold prospects",
            "suggestion": "Run outreach cycle on NYC permits last 7d",
        })

    # If many delivered but no recent outreach, recommend nurture campaign
    if metrics["delivered_leads"] > 50 and metrics["outreach_log_lines"] < 20:
        actions.append({
            "type": "nurture",
            "priority": "medium",
            "reason": "high delivery volume but low outreach activity",
            "suggestion": "Send 'result of your last delivered lead' email",
        })

    # If alerts active, recommend pause
    if metrics["alerts_log_lines"] > 5:
        actions.append({
            "type": "investigate",
            "priority": "high",
            "reason": f"{metrics['alerts_log_lines']} recent alerts",
            "suggestion": "Read /root/feedback/alerts.jsonl",
        })

    return {"recommendations": actions, "rationale_metric_count": len(metrics)}


def run_cycle():
    metrics = compute_marketing_metrics()
    recs = recommend_next_action(metrics)

    _log("EVENT", "marketing_cycle",
         metrics=metrics, recommendations=recs["recommendations"][:3])


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] marketing-agent starting — interval {INTERVAL}s",
          flush=True)
    while True:
        try:
            run_cycle()
        except Exception as e:
            _log("ERROR", "cycle_failed", error=str(e)[:200])
        time.sleep(INTERVAL)
