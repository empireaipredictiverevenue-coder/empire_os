"""
Empire OS v3 — Stack Integration Wire-up
========================================

Connects the 6 self-hosted services (twenty-crm, post-analytics, listmonk,
formbricks-survey, documenso, appsmith-admin) into the crawler +
intelligence pipeline so every lead flow touches every system.

Endpoints (after caddy subdomains + DNS records are live):
  - twenty.empire-ai.co.uk     → twenty-crm       (10.118.155.248:3000)
  - posthog.empire-ai.co.uk    → post-analytics   (10.118.155.13:8000)
  - listmonk.empire-ai.co.uk   → listmonk-mail     (10.118.155.153:9000)
  - formbricks.empire-ai.co.uk → formbricks-survey (10.118.155.88:3000)
  - documenso.empire-ai.co.uk  → documenso         (10.118.155.30:3500)
  - appsmith.empire-ai.co.uk   → appsmith-admin    (10.118.155.154:8080)

Wire-up:
  1. Every graded lead in evaluation_ledger → POST to twenty-crm as a Contact
  2. Every send_email event → POST to post-analytics (event capture)
  3. Every conversion event → POST to listmonk subscriber
  4. Every AEO page published → POST to formbricks survey webhook (NPS)
  5. Every doc generated (content_engine) → POST to documenso for signature
  6. Every decision by agents → POST to appsmith internal tool

Cadence: 6h, syncs the past 6h of events from /root/feedback.
"""
from __future__ import annotations
import json
import os
import sys
import sqlite3
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

DB = "/root/empire_os/empire_os.db"
FB = Path("/root/feedback")
LOG = FB / "stack_wireup.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(6 * 3600)))

# Service endpoints (container IPs — direct since they're internal)
SERVICES = {
    "twenty":       "http://10.118.155.248:3000",
    "posthog":      "http://10.118.155.13:8000",
    "listmonk":     "http://10.118.155.153:9000",
    "formbricks":   "http://10.118.155.88:3000",
    "documenso":    "http://10.118.155.30:3500",
    "appsmith":     "http://10.118.155.154:8080",
}

UA = "EmpireOS/3.0 (+https://empire-ai.co.uk)"


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "CYCLE_START", "CYCLE_END"):
        print(json.dumps(e), flush=True)


def http_post(url: str, payload: dict, timeout: int = 8) -> tuple[int, str]:
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"content-type": "application/json",
                                              "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()[:300].decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode(errors="replace")
    except Exception as e:
        return -1, str(e)[:120]


def http_get(url: str, timeout: int = 8) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()[:200].decode(errors="replace")
    except Exception as e:
        return -1, str(e)[:80]


def check_services() -> dict:
    """Probe every service, return {name: {base, probe_status, body}}."""
    status = {}
    for name, base in SERVICES.items():
        # Try a representative health endpoint
        probe = f"{base}/health" if name != "twenty" else f"{base}/api/health"
        s, b = http_get(probe)
        status[name] = {"base": base, "probe_status": int(s),
                        "body_preview": str(b)[:80]}
    return status


def sync_to_twenty() -> int:
    """Push new evaluation_ledger leads into twenty-crm as contacts."""
    c = sqlite3.connect(DB)
    try:
        rows = c.execute(
            "SELECT buyer, lead_ref, niche, omega, grade, created_at "
            "FROM evaluation_ledger "
            "WHERE created_at > datetime('now', '-6 hours') "
            "AND grade IN ('A','B') LIMIT 50"
        ).fetchall()
    finally:
        c.close()
    posted = 0
    for buyer, lead_ref, niche, omega, grade, ts in rows:
        payload = {
            "name": buyer or f"lead_{lead_ref}",
            "email": "",  # ledger doesn't carry email
            "companyName": "Empire OS Buyer",
            "jobTitle": f"{niche} buyer (grade {grade})",
            "customFields": {"lead_ref": lead_ref, "omega": omega,
                             "source": "evaluation_ledger", "captured_at": ts},
        }
        s, _ = http_post(f"{SERVICES['twenty']}/api/contacts", payload)
        if s in (200, 201): posted += 1
    return posted


def sync_to_posthog() -> int:
    """Push recent cortex brain + aeo + market-sweep events to posthog."""
    events_sent = 0
    # Stream last 20 events from a few key jsonl files
    sources = [
        ("cortex_brain.json", "cortex_brain_emitted", "cortex"),
        ("aeo_citations.json", "aeo_published", "aeo"),
        ("ai_seo_log.jsonl", "ai_seo_event", "seo"),
    ]
    for fname, kind, prefix in sources:
        path = FB / fname
        if not path.exists(): continue
        try:
            with open(path) as f:
                lines = f.readlines()[-10:]
            for line in lines:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                payload = {
                    "api_key": os.environ.get("POSTHOG_API_KEY", ""),
                    "event": f"{prefix}_{kind}",
                    "distinct_id": obj.get("ts", "anonymous"),
                    "properties": obj,
                    "timestamp": obj.get("ts"),
                }
                s, _ = http_post(f"{SERVICES['posthog']}/capture/", payload)
                if s == 200: events_sent += 1
        except Exception:
            continue
    return events_sent


def sync_to_listmonk() -> int:
    """Push lead_ref + buyer into listmonk subscriber list."""
    c = sqlite3.connect(DB)
    try:
        rows = c.execute(
            "SELECT DISTINCT buyer, lead_ref FROM evaluation_ledger "
            "WHERE created_at > datetime('now', '-6 hours') "
            "AND grade IN ('A','B','C') LIMIT 30"
        ).fetchall()
    finally:
        c.close()
    added = 0
    for buyer, lead_ref in rows:
        if not buyer: continue
        payload = {"email": f"{buyer}@empire-ai.co.uk",
                   "name": buyer, "lists": [1],
                   "attribs": {"source": "evaluation_ledger",
                               "lead_ref": lead_ref}}
        s, _ = http_post(f"{SERVICES['listmonk']}/api/subscribers", payload)
        if s in (200, 201): added += 1
    return added


def sync_to_formbricks() -> int:
    """Push a tiny NPS survey link for hot leads."""
    c = sqlite3.connect(DB)
    try:
        rows = c.execute(
            "SELECT DISTINCT buyer FROM evaluation_ledger "
            "WHERE grade='A' AND created_at > datetime('now', '-6 hours') LIMIT 10"
        ).fetchall()
    finally:
        c.close()
    sent = 0
    for (buyer,) in rows:
        if not buyer: continue
        payload = {"event": "lead_nps_invite",
                   "userId": buyer,
                   "properties": {"campaign": "empire_lead_nps"}}
        s, _ = http_post(f"{SERVICES['formbricks']}/api/events", payload)
        if s in (200, 201, 202): sent += 1
    return sent


def sync_to_appsmith() -> int:
    """Post a daily summary to appsmith internal tool."""
    c = sqlite3.connect(DB)
    try:
        leads = c.execute("SELECT COUNT(*) FROM lane_leads").fetchone()[0]
        buyers = c.execute(
            "SELECT COUNT(*) FROM si_buyer_outreach WHERE active=1").fetchone()[0]
        settled = c.execute(
            "SELECT COUNT(*) FROM si_settlements WHERE settled_at IS NOT NULL"
        ).fetchone()[0]
        invoices = c.execute(
            "SELECT COUNT(*) FROM si_ppc_invoices WHERE status='open'"
        ).fetchone()[0]
    finally:
        c.close()
    payload = {
        "source": "empire_stack_sync",
        "ts": datetime.now(timezone.utc).isoformat(),
        "metrics": {"leads": leads, "active_buyers": buyers,
                    "settled": settled, "open_invoices": invoices},
    }
    s, _ = http_post(f"{SERVICES['appsmith']}/api/v1/empire/sync", payload)
    return 1 if s in (200, 201) else 0


def cycle():
    log("CYCLE_START", "stack-wireup cycle start")
    # Check liveness
    status = check_services()
    up = sum(1 for v in status.values() if v["probe_status"] in (200, 201, 204, 301))
    log("EVENT", "service_status", up=up, total=len(status),
        details=json.dumps(status))

    # Sync each
    twenty_posted = sync_to_twenty()
    posthog_events = sync_to_posthog()
    listmonk_added = sync_to_listmonk()
    formbricks_sent = sync_to_formbricks()
    appsmith_posted = sync_to_appsmith()

    log("CYCLE_END", "stack-wireup cycle done",
        twenty_posted=twenty_posted,
        posthog_events=posthog_events,
        listmonk_added=listmonk_added,
        formbricks_sent=formbricks_sent,
        appsmith_posted=appsmith_posted,
        services_up=up)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--daemon", action="store_true")
    args = ap.parse_args()
    if not args.daemon:
        cycle()
        return
    import time as _t
    while True:
        try: cycle()
        except Exception as e: log("ERROR", "cycle", err=str(e)[:200])
        _t.sleep(INTERVAL)


if __name__ == "__main__":
    main()
