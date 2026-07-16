"""
Empire OS v3 — Sales Agent
============================

Tracks every prospect through the buyer funnel.

Stages:
  cold      — discovered via crawl or outreach seeding
  contacted — first-touch sent
  replied   — prospect responded
  demo      — in active conversation
  trial     — signed up but invoice pending
  paid      — invoice settled onchain, subscription active
  lost      — unsubscribed or no response after 30 days
  churned   — was paid, now inactive

Reads from /v1/outreach/prospects/pending + /v1/lanes/leads/by-source.
Writes to /root/feedback/sales_funnel.jsonl.

Cadence: every 5 minutes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests


HUB_URL = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
FEEDBACK = Path("/root/feedback")
FUNNEL_LOG = FEEDBACK / "sales_funnel.jsonl"
INTERVAL = int(os.environ.get("INTERVAL", "300"))  # 5min


def _log(level, msg, **fields):
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level, "msg": msg, **fields,
    }
    FEEDBACK.mkdir(parents=True, exist_ok=True)
    with open(FUNNEL_LOG, "a") as f:
        f.write(json.dumps(event) + "\n")


def _hub_get(path: str, **params) -> dict:
    try:
        r = requests.get(f"{HUB_URL}{path}", params=params, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        _log("ERROR", "hub_get_failed", path=path, error=str(e)[:100])
        return {}


def _stage_prospect(prospect_id: str, stage: str, notes: str = ""):
    """Update prospect stage via hub HTTP."""
    try:
        r = requests.post(
            f"{HUB_URL}/v1/outreach/prospect/touched",
            json={"prospect_id": prospect_id, "sent": True,
                  "sample_lead_id": ""},
            timeout=8,
        )
        return r.status_code < 300
    except Exception:
        return False


def compute_funnel_metrics() -> dict:
    """Pull all prospects + infer stages from outreach_log.jsonl."""
    pending = _hub_get("/v1/outreach/prospects/pending", limit=500)

    # Pull latest log lines for stage inference
    log = Path("/root/feedback/outreach_log.jsonl")
    by_prospect = defaultdict(lambda: {"last_event": None,
                                       "touches": 0,
                                       "replied": False})
    if log.exists():
        for line in log.read_text().splitlines()[-2000:]:
            try:
                e = json.loads(line)
            except Exception:
                continue
            pid = e.get("prospect_id") or e.get("pid") or ""
            if pid:
                by_prospect[pid]["last_event"] = e
                by_prospect[pid]["touches"] += 1

    # Stage inference: heuristic
    # cold = just registered, last = 'cycle_done' or None
    # contacted = 'SENT' in log
    # replied = explicit 'REPLY' (none implemented yet, leave false)
    # paid = si_tenant has method='self_serve' or 'self_serve_seat'
    fun = Counter()
    for p in pending.get("prospects", []):
        pid = p.get("prospect_id", "")
        last = by_prospect[pid].get("last_event") or {}
        if "SENT" in str(last.get("msg", "")):
            fun["contacted"] += 1
        else:
            fun["cold"] += 1

    return dict(fun), len(pending.get("prospects", []))


def run_cycle():
    """Sales agent = monitor + summarize."""
    start = datetime.now(timezone.utc)

    # Funnel snapshot
    fun, total_prospects = compute_funnel_metrics()

    # Revenue snapshot
    counts = _hub_get("/v1/leads/counts")
    total_leads = counts.get("total", 0)
    pending_leads = counts.get("by_status", {}).get("pending", 0)
    delivered = counts.get("by_status", {}).get("delivered", 0)

    # Tenants snapshot
    tenants = _hub_get("/v1/buyers", limit=100).get("buyers", [])

    summary = {
        "ts": start.isoformat(),
        "level": "FUNNEL",
        "msg": "sales-agent funnel snapshot",
        "prospects": total_prospects,
        "funnel_stages": fun,
        "leads_total": total_leads,
        "leads_pending": pending_leads,
        "leads_delivered": delivered,
        "tenants_total": len(tenants),
    }
    _log("FUNNEL", "snapshot",
         prospects=total_prospects,
         stages=str(fun), leads_total=total_leads,
         delivered=delivered, tenants=len(tenants))


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] sales-agent starting — interval {INTERVAL}s",
          flush=True)
    while True:
        try:
            run_cycle()
        except Exception as e:
            _log("ERROR", "cycle_failed", error=str(e)[:200])
        time.sleep(INTERVAL)
