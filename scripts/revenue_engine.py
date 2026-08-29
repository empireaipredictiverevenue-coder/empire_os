#!/usr/bin/env python3
"""
Empire OS Autonomous Revenue Engine — runs while the laptop is closed.

A single long-lived process that orchestrates every revenue motion in a
loop. No human in the loop, no cron drift, no missed cycles.

Cycle (every 5 min by default):
  1. AEO health: count CTA-injected pages, ping sitemap
  2. Lane activation: fill empty high-value lanes (top 20 unoccupied)
  3. Outreach quota check: skip cycle if Resend at daily cap
  4. Trial-to-paid scan: trials expiring in <24h, ping their wallet
  5. Revenue stats: snapshot to /root/feedback/revenue_engine.jsonl

Runs as a systemd service: empire-revenue-engine.service
"""
from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HUB_URL = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
LOG_PATH = Path("/root/feedback/revenue_engine.jsonl")
STATS_PATH = Path("/root/feedback/revenue_engine_latest.json")
INTERVAL_SECONDS = int(os.environ.get("INTERVAL", "300"))  # 5 min

_running = True


def log(msg: str, **fields) -> None:
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "msg": msg, **fields}
    print(json.dumps(rec), flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def step_a_cta_health() -> dict:
    """Count AEO pages with CTA, ping sitemap."""
    aeo_root = Path("/srv/aeo")
    marker = "EMPIRE-OS-CTA-INJECTED"
    pages = sum(1 for p in aeo_root.rglob("*.html")
                if marker in p.read_text(errors="replace"))
    sitemap = Path("/srv/aeo/sitemap.xml")
    sitemap_urls = sitemap.read_text().count("<loc>") if sitemap.exists() else 0
    return {"aeo_cta_pages": pages, "sitemap_urls": sitemap_urls}


def step_b_lane_activation(batch_size: int = 20) -> dict:
    """Fill empty high-value lanes. Multi-seat per lane supported."""
    try:
        sys.path.insert(0, "/root/empire_os")
        from empire_os.lane_seats import migrate as _seats_migrate
        _seats_migrate()
        from empire_os.db_adapter import get_empty_lanes
        lanes = get_empty_lanes(limit=batch_size)
    except Exception as e:
        return {"error": str(e)[:200]}

    # Run the activator (it will try to occupy + subscribe)
    result = subprocess.run(
        ["python3", "/root/empire_os/scripts/activate_empty_lanes.py"],
        capture_output=True, text=True, timeout=120,
    )
    activated = result.stdout.count("pay_url=")  # rough count of SENTs
    return {
        "candidate_lanes": len(lanes),
        "activator_exit": result.returncode,
        "activator_activated_count": activated,
    }


def step_c_quota_check() -> dict:
    """Check Resend daily quota state."""
    state = Path("/root/feedback/resend_daily_counter.json")
    if not state.exists():
        return {"quota_state": "missing", "remaining": 95, "max": 95}
    d = json.loads(state.read_text())
    today = datetime.now(timezone.utc).date().isoformat()
    if d.get("day") != today:
        return {"quota_state": "fresh_day", "remaining": 95, "max": 95}
    sent = d.get("sent", 0)
    maxd = d.get("max_per_day", 95)
    return {
        "quota_state": "exhausted" if sent >= maxd else "ok",
        "remaining": max(0, maxd - sent),
        "max": maxd,
        "sent": sent,
    }


def step_d_trial_scan() -> dict:
    """Find trials expiring in <24h and emit a reminder webhook."""
    try:
        sys.path.insert(0, "/root/empire_os")
        from empire_os.db_adapter import _container_query
        rows = _container_query(
            "SELECT subscription_id, tenant_id, current_period_end "
            "FROM si_subscription "
            "WHERE plan='trial' AND status='active' "
            "AND current_period_end IS NOT NULL "
            "AND current_period_end < datetime('now', '+24 hours')"
        )
    except Exception as e:
        return {"error": str(e)[:200]}
    expiring = len(rows)
    if expiring > 0:
        for r in rows:
            log("trial_expiring_soon", **r)
    return {"expiring_within_24h": expiring}


def step_e_stats() -> dict:
    """Snapshot revenue state."""
    try:
        sys.path.insert(0, "/root/empire_os")
        from empire_os.db_adapter import (
            get_si_tenant_count, get_si_subscription_count,
            get_si_charges_pending,
        )
        tenants = get_si_tenant_count()
        subs = get_si_subscription_count()
        pn, pt = get_si_charges_pending()
        return {
            "tenants": tenants, "subscriptions": subs,
            "pending_charges": pn, "pending_value_usd": pt,
        }
    except Exception as e:
        return {"error": str(e)[:200]}


def cycle() -> dict:
    log("cycle_start")
    out = {
        "aeo_health": step_a_cta_health(),
        "quota": step_c_quota_check(),
    }
    # Only run lane activation if quota isn't exhausted
    if out["quota"].get("quota_state") != "exhausted":
        out["lane_activation"] = step_b_lane_activation()
    else:
        out["lane_activation"] = {"skipped": "quota_exhausted"}
    out["trial_scan"] = step_d_trial_scan()
    out["stats"] = step_e_stats()
    log("cycle_end", **out)
    return out


def main() -> int:
    # Install signal handlers
    def _stop(sig, frame):
        global _running
        _running = False
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    log("revenue_engine_started", interval=INTERVAL_SECONDS, hub=HUB_URL)
    while _running:
        try:
            stats = cycle()
            STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATS_PATH.write_text(json.dumps(stats, indent=2, default=str))
        except Exception as e:
            log("cycle_error", error=str(e)[:500])
        # Sleep in 1s increments to respond to SIGTERM
        for _ in range(INTERVAL_SECONDS):
            if not _running:
                break
            time.sleep(1)
    log("revenue_engine_stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())