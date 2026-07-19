#!/usr/bin/env python3
"""
Empire OS Guardian Agent — Continuous System Health Monitor

Monitors all critical Empire OS components every 5 minutes and auto-fixes common issues.
Runs as a long-lived background agent like other Empire agents.
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
DB_PATH = os.environ.get("DB_PATH", "/root/empire_os/empire_os.db")
FB_DIR = Path("/root/feedback")
GUARDIAN_LOG = FB_DIR / "guardian.jsonl"
INTERVAL = int(os.environ.get("GUARDIAN_INTERVAL_SEC", "300"))  # 5 min

# Component checks
CHECKS = [
    ("hub_health", lambda: _check_hub_health()),
    ("hub_lane_heat", lambda: _check_lane_heat_endpoint()),
    ("b2b_scraper_hot_metros", lambda: _check_b2b_hot_metros()),
    ("si_outbox_failures", lambda: _check_si_outbox_failures()),
    ("webhook_urls_valid", lambda: _check_webhook_urls()),
    ("hub_url_port", lambda: _check_hub_url_port()),
    ("ppc_router_running", lambda: _check_ppc_router()),
    ("lead_deliverer_running", lambda: _check_lead_deliverer()),
    ("outreach_runner_running", lambda: _check_outreach_runner()),
    ("b2b_scraper_running", lambda: _check_b2b_scraper()),
    ("contractor_scraper_running", lambda: _check_contractor_scraper()),
    ("db_integrity", lambda: _check_db_integrity()),
]

FB_DIR.mkdir(parents=True, exist_ok=True)


def _log(level: str, msg: str, **fields):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields
    }
    FB_DIR.mkdir(parents=True, exist_ok=True)
    with open(GUARDIAN_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    if level in ("ERROR", "WARN", "FIX"):
        print(json.dumps(entry), flush=True)


def _http_get(url: str, timeout: int = 5):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Guardian/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except Exception as e:
        return None, str(e)


def _check_hub_health():
    status, body = _http_get(f"{HUB_URL}/health")
    if status == 200:
        data = json.loads(body)
        if data.get("status") == "online":
            return True, "hub healthy"
    return False, f"hub health failed: status={status}, body={body[:100]}"


def _check_lane_heat_endpoint():
    status, body = _http_get(f"{HUB_URL}/v1/swarm/lane-heat")
    if status == 200:
        data = json.loads(body)
        if "by_lane" in data:
            return True, f"lane-heat ok: {len(data['by_lane'])} lanes"
    return False, f"lane-heat missing or failed: status={status}"


def _check_b2b_hot_metros():
    """Test that b2b_scraper hot_metros() would return lanes."""
    status, body = _http_get(f"{HUB_URL}/v1/swarm/lane-heat")
    if status == 200:
        data = json.loads(body)
        lanes = data.get("by_lane", {})
        if lanes:
            return True, f"b2b hot_metros would find {len(lanes)} lanes"
    return False, "b2b hot_metros would find 0 lanes"


def _check_si_outbox_failures():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM si_outbox WHERE status='failed'")
        failed = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM si_outbox WHERE source='buyer_delivery' AND status='failed'")
        buyer_failed = c.fetchone()[0]
        conn.close()
        if failed > 10:
            return False, f"si_outbox failed: {failed} total, {buyer_failed} buyer_delivery"
        return True, f"si_outbox ok: {failed} failed"
    except Exception as e:
        return False, f"si_outbox check failed: {e}"


def _check_webhook_urls():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM si_tenant WHERE webhook_url LIKE 'http://127.0.0.1:%' OR webhook_url LIKE 'http://localhost:%'")
        localhost_count = c.fetchone()[0]
        conn.close()
        if localhost_count > 0:
            return False, f"{localhost_count} tenants have localhost webhook URLs"
        return True, "webhook urls ok"
    except Exception as e:
        return False, f"webhook check failed: {e}"


def _check_hub_url_port():
    """Check that agents use HUB_URL=8081 not 8000."""
    # Check lane_monitor config
    issues = []
    for path in [
        "/root/empire_os/empire_os/agents/lane_monitor_agent.py",
        "/root/empire_os/empire_os/agents/b2b_scraper_agent.py",
        "/root/empire_os/empire_os/agents/lead_deliverer_agent.py",
    ]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if "8000" in content and "HUB" in content:
                    issues.append(path)
    if issues:
        return False, f"agents still using port 8000: {issues}"
    return True, "HUB_URL ports ok"


def _check_ppc_router():
    try:
        # Check process
        out = subprocess.run(["pgrep", "-f", "ppc_router.py"], capture_output=True, text=True)
        if out.returncode != 0:
            return False, "ppc_router.py not running"
        # Check health endpoint
        status, body = _http_get("http://127.0.0.1:9200/health", timeout=3)
        if status == 200:
            return True, "ppc_router healthy"
        return False, f"ppc_router health failed health failed: status={status}"
    except Exception as e:
        return False, f"ppc check failed: {e}"


def _check_lead_deliverer():
    out = subprocess.run(["pgrep", "-f", "lead_deliverer_agent.py"], capture_output=True, text=True)
    return out.returncode == 0, "lead_deliverer running" if out.returncode == 0 else "lead_deliverer not running"


def _check_outreach_runner():
    out = subprocess.run(["pgrep", "-f", "outreach_runner.py"], capture_output=True, text=True)
    return out.returncode == 0, "outreach_runner running" if out.returncode == 0 else "outreach_runner not running"


def _check_b2b_scraper():
    out = subprocess.run(["pgrep", "-f", "b2b_scraper_agent.py"], capture_output=True, text=True)
    return out.returncode == 0, "b2b_scraper running" if out.returncode == 0 else "b2b_scraper not running"


def _check_contractor_scraper():
    out = subprocess.run(["pgrep", "-f", "contractor_scraper_agent.py"], capture_output=True, text=True)
    return out.returncode == 0, "contractor_scraper running" if out.returncode == 0 else "contractor_scraper not running"


def _check_db_integrity():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("PRAGMA quick_check")
        result = c.fetchone()[0]
        conn.close()
        return result == "ok", f"db integrity: {result}"
    except Exception as e:
        return False, f"db check failed: {e}"


def _fix_lane_heat_endpoint():
    """Auto-fix: add /v1/swarm/lane-heat endpoint to hub.py if missing."""
    hub_path = "/root/empire_os/empire_os/hub.py"
    with open(hub_path) as f:
        content = f.read()
    
    if "/v1/swarm/lane-heat" not in content:
        # Add endpoint before the first @app.get after swarm section
        insert_marker = '@app.get("/v1/swarm/ledger")'
        idx = content.find(insert_marker)
        if idx != -1:
            endpoint_code = '''
@app.get("/v1/swarm/lane-heat")
def swarm_lane_heat():
    """Lane heat from lane_monitor.jsonl + lead_deliveries.jsonl."""
    from collections import Counter
    import json
    from pathlib import Path
    
    heat = Counter()
    # lane_monitor.jsonl
    p = Path("/root/feedback/lane_monitor.jsonl")
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                e = json.loads(line)
                if "lane" in e:
                    heat[e["lane"]] += 1
            except:
                pass
    
    # lead_deliveries.jsonl
    p = Path("/root/feedback/lead_deliveries.jsonl")
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                e = json.loads(line)
                if "lane" in e:
                    heat[e["lane"]] += e.get("count", 1)
            except:
                pass
    
    # si_outbox successful deliveries
    import sqlite3
    try:
        conn = sqlite3.connect("/root/empire_os/empire_os.db")
        c = conn.cursor()
        c.execute("SELECT lane, COUNT(*) FROM si_outbox WHERE status='sent' GROUP BY lane")
        for lane, cnt in c.fetchall():
            heat[lane] += cnt
        conn.close()
    except:
        pass
    
    return {"by_lane": dict(heat), "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}

'''
            content = content[:idx] + endpoint_code + "\n\n" + content[idx:]
            with open(hub_path, "w") as f:
                f.write(content)
            return True
    return False


def _fix_webhook_localhost():
    """Auto-fix: replace localhost webhook URLs with webhook.site placeholder."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE si_tenant SET webhook_url='https://webhook.site/auto-fix' WHERE webhook_url LIKE 'http://127.0.0.1:%' OR webhook_url LIKE 'http://localhost:%'")
        updated = c.rowcount
        conn.commit()
        conn.close()
        if updated:
            _log("FIX", f"Fixed {updated} localhost webhook URLs", updated=updated)
    except Exception as e:
        _log("ERROR", f"fix webhook failed: {e}")


def _fix_hub_url_port():
    """Auto-fix: replace 8000 with 8081 in agent configs."""
    for path in [
        "/root/empire_os/empire_os/agents/lane_monitor_agent.py",
        "/root/empire_os/empire_os/agents/b2b_scraper_agent.py",
        "/root/empire_os/empire_os/agents/lead_deliverer_agent.py",
    ]:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            if "8000" in content and "HUB" in content:
                content = content.replace("8000", "8081")
                with open(path, "w") as f:
                    f.write(content)
                _log("FIX", f"Fixed HUB_URL port in {path}")


def run_checks():
    """Run all checks, auto-fix where possible, return summary."""
    results = []
    
    for name, check_fn in CHECKS:
        try:
            ok, msg = check_fn()
            results.append((name, ok, msg))
            level = "OK" if ok else "WARN"
            _log(level, f"check:{name}: {msg}", ok=ok)
        except Exception as e:
            results.append((name, False, f"check error: {e}"))
            _log("ERROR", f"check:{name} exception", error=str(e))
    
    # Auto-fix logic
    # Fix lane-heat endpoint if missing
    lane_heat_ok = any(r[0] == "hub_lane_heat" and r[1] for r in results)
    if not lane_heat_ok:
        if _fix_lane_heat_endpoint():
            _log("FIX", "Added /v1/swarm/lane-heat endpoint to hub.py")
    
    # Fix localhost webhooks
    webhook_ok = any(r[0] == "webhook_urls_valid" and r[1] for r in results)
    if not webhook_ok:
        _fix_webhook_localhost()
    
    # Fix HUB_URL port
    port_ok = any(r[0] == "hub_url_port" and r[1] for r in results)
    if not port_ok:
        _fix_hub_url_port()
    
    # Restart hub if we fixed endpoints
    if not lane_heat_ok:
        subprocess.run(["pkill", "-9", "-f", "python3 -m empire_os.hub"], capture_output=True)
        time.sleep(2)
        subprocess.Popen(
            ["/root/venv/bin/python3", "-m", "empire_os.hub", "--host", "0.0.0.0", "--port", "8081"],
            cwd="/root/empire_os",
            stdout=open("/root/empire_os/logs/hub.log", "a"),
            stderr=subprocess.STDOUT,
        )
        _log("FIX", "Restarted hub after endpoint fix")
        time.sleep(3)
    
    return results


def main():
    print(f"[Guardian] Starting - interval={INTERVAL}s", flush=True)
    _log("START", "Guardian agent starting", interval=INTERVAL)
    
    while True:
        try:
            results = run_checks()
            ok_count = sum(1 for _, ok, _ in results if ok)
            total = len(results)
            _log("CYCLE", f"Check cycle complete: {ok_count}/{total} ok", ok=ok_count, total=total)
        except Exception as e:
            _log("ERROR", f"Guardian cycle failed: {e}")
        
        time.sleep(INTERVAL)


if __name__ == "__main__":
    FB_DIR.mkdir(parents=True, exist_ok=True)
    Path("/root/empire_os/logs").mkdir(parents=True, exist_ok=True)
    main()