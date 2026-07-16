"""
Empire OS v3 - Predictive Cloud Agent
=======================================

THE BRAIN. Runs every 6h, queries hub + SQLite + feedback, emits
4 multi-axis forecasts:

  1. predict_revenue()      -> 30/90/365-day MRR scenarios
  2. detect_market_gaps()          -> underserved (niche, metro) opportunities
  3. detect_leaks()         -> drop-off + vacancy alarms
  4. detect_waste()         -> over-resourced / under-utilized

Writes /root/feedback/predictive_cloud.jsonl + posts to
/v1/swarm/audit-log as kind="predictive_cloud".
"""
from __future__ import annotations
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB    = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
DB     = os.environ.get("HUB_DB_PATH", "/root/empire_os/empire_os.db")
FB     = Path("/root/feedback")
LOG    = FB / "predictive_cloud.jsonl"
RESEARCH_PROGRAM = Path("/tmp/repo_AutoReSeArch/program.md")
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(6 * 3600)))


def load_research_spec() -> str:
    """Read karpathy/AutoReSeArch program.md as the brain's research org spec."""
    if RESEARCH_PROGRAM.exists():
        return RESEARCH_PROGRAM.read_text()[:4000]
    return ""


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


def call_predictive(name: str, *args) -> dict:
    try:
        from empire_os.predictive import (
            predict_revenue, detect_market_gaps, detect_leaks, detect_waste)
        fn = locals()[name]
        return fn(*args)
    except Exception as e:
        log("ERROR", "predictive_fail", name=name, err=str(e)[:150])
        return {}


def gather_input():
    cnx = {}
    try:
        import sqlite3
        c = sqlite3.connect(DB)
        try:
            cnx["leads_total"] = c.execute(
                "SELECT COUNT(*) FROM lane_leads").fetchone()[0]
            cnx["leads_pending"] = c.execute(
                "SELECT COUNT(*) FROM lane_leads WHERE status='pending'"
            ).fetchone()[0]
            cnx["lanes_total"] = c.execute(
                "SELECT COUNT(*) FROM lanes").fetchone()[0]
            cnx["lanes_occupied"] = c.execute(
                "SELECT COUNT(*) FROM lanes WHERE occupied_by IS NOT NULL"
            ).fetchone()[0]
            cnx["paid_subscriptions"] = c.execute(
                "SELECT COUNT(*) FROM si_subscription WHERE status='paid'"
            ).fetchone()[0]
            cnx["pending_invoices"] = c.execute(
                "SELECT COALESCE(SUM(amount_cents), 0) FROM si_invoice "
                "WHERE status='pending'").fetchone()[0]
            vault_row = c.execute(
                "SELECT value FROM app_kv WHERE key='vault_balance_usdc'"
            ).fetchone()
            cnx["vault_usdc"] = float(vault_row[0]) if vault_row else 0.0
        finally:
            c.close()
    except Exception as e:
        log("ERROR", "gather_input", err=str(e)[:150])
    return cnx


def cycle():
    inp = gather_input()
    rev     = call_predictive("predict_revenue", inp)
    gaps    = call_predictive("detect_market_gaps")
    leaks   = call_predictive("detect_leaks")
    waste   = call_predictive("detect_waste")
    out = {
        "input":    inp,
        "revenue":  rev,
        "gaps":     gaps,
        "leaks":    leaks,
        "waste":    waste,
        "ts":       datetime.now(timezone.utc).isoformat(),
    }
    log("EVENT", "predictive_cloud_emitted", **{
        "vault_usdc": inp.get("vault_usdc"),
        "lanes_occupied": inp.get("lanes_occupied"),
        "leads_pending": inp.get("leads_pending"),
    })
    try:
        requests.post(f"{HUB}/v1/swarm/audit-log",
                       json={"kind": "predictive_cloud",
                             "ts": out["ts"],
                             "data": out}, timeout=15)
    except Exception as e:
        log("WARN", "audit_post_fail", err=str(e)[:120])


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] predictive-cloud online - {INTERVAL}s",
          flush=True)
    while True:
        try:
            cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
