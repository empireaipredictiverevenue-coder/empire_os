#!/usr/bin/env python3
"""
Empire OS Revenue Watchdog — Self-healing Monitor
==================================================
Runs every 5 minutes via systemd timer to ensure revenue loop stays healthy.
Self-heals common failure modes:
- Dead processes → restart via systemctl
- Stuck leads → force settlement bridge
- Deadlocked DB → WAL checkpoint
- Hub down → restart hub
- Mail sender down → restart mail sender
- Stale invoices → force settlement bridge
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"
LOG_FILE = "/root/empire_os/logs/revenue_watchdog.jsonl"

def log(level, msg, **fields):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields,
    }
    Path("/root/empire_os/logs").mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    if level in ("ERROR", "WARN", "HEAL"):
        print(json.dumps(entry))

def run_cmd(cmd, check=False):
    """Run command, return (success, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)

def systemctl(action, service):
    """Run systemctl command."""
    success, out, err = run_cmd(f"systemctl {action} {service}")
    return success, out, err

def check_hub():
    """Check hub health endpoint."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8081/health", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False

def check_processes():
    """Check critical processes are running."""
    critical = {
        "hub": "hub",
        "mail_sender": "mail_sender_runner.py",
        "bsc_listener": "bsc_usdt_listener_fixed.py",
        "settlement_gateway": "settlement_gateway_daemon.py",
    }
    results = {}
    for name, pattern in critical.items():
        success, out, _ = run_cmd(f"pgrep -f {pattern}")
        results[name] = success
    return results

def check_db():
    """Check database health."""
    try:
        con = sqlite3.connect(DB, timeout=5)
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("SELECT 1")
        con.close()
        return True
    except Exception as e:
        log("ERROR", "db_check_failed", error=str(e))
        return False

def check_stuck_leads():
    """Find leads stuck in pending too long."""
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    # Leads pending > 1 hour with active buyers available
    rows = cur.execute("""
        SELECT COUNT(*) as cnt FROM lane_leads ll
        JOIN lanes l ON ll.lane_id = l.id
        WHERE ll.status = 'pending'
          AND l.occupied_by IS NOT NULL AND l.occupied_by != ''
          AND ll.created_at < datetime('now', '-1 hour')
    """).fetchone()
    con.close()
    return rows["cnt"] if rows else 0

def check_stale_invoices():
    """Find invoices not settled > 24 hours."""
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute("""
        SELECT COUNT(*) as cnt FROM si_ppc_invoices
        WHERE status = 'open'
          AND created_at < datetime('now', '-24 hour')
    """).fetchone()
    con.close()
    return rows["cnt"] if rows else 0

def check_mail_sender():
    """Check mail sender queue health."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8081/v1/outbox/pending?n=1", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False

def heal_restart_service(service):
    """Restart a systemd service."""
    log("HEAL", f"Restarting service: {service}")
    success, out, err = systemctl("restart", service)
    if success:
        log("HEAL", f"Restarted {service} successfully")
    else:
        log("ERROR", f"Failed to restart {service}", error=err)
    return success

def heal_force_settlement_bridge():
    """Force settlement bridge cycle."""
    log("HEAL", "Forcing settlement bridge cycle")
    import importlib
    import empire_os.settlement_bridge
    importlib.reload(empire_os.settlement_bridge)
    from empire_os.settlement_bridge import process_cycle
    try:
        result = process_cycle()
        log("HEAL", "Forced settlement bridge", **result)
        return True
    except Exception as e:
        log("ERROR", "force_settlement_bridge_failed", error=str(e))
        return False

def heal_wal_checkpoint():
    """Force WAL checkpoint."""
    log("HEAL", "Forcing WAL checkpoint")
    try:
        con = sqlite3.connect(DB, timeout=10)
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.close()
        log("HEAL", "WAL checkpoint completed")
        return True
    except Exception as e:
        log("ERROR", "wal_checkpoint_failed", error=str(e))
        return False

def main():
    log("INFO", "Revenue watchdog started")
    
    # 1. Check hub
    if not check_hub():
        log("WARN", "Hub health check failed, restarting hub")
        heal_restart_service("empire-hub-8081")
    else:
        log("INFO", "Hub healthy")
    
    # 2. Check critical processes
    processes = check_processes()
    for name, running in processes.items():
        if not running:
            service_map = {
                "hub": "empire-hub-8081",
                "mail_sender": "empire-mail-sender",
                "bsc_listener": "empire-bsc-listener",
                "settlement_gateway": "empire-settlement-gateway",
            }
            service = service_map.get(name)
            if service:
                heal_restart_service(service)
        else:
            log("INFO", f"Process healthy: {name}")
    
    # 3. Database health
    if not check_db():
        heal_wal_checkpoint()
    
    # 4. Stuck leads
    stuck = check_stuck_leads()
    if stuck > 0:
        log("WARN", f"Found {stuck} stuck leads, forcing settlement bridge")
        heal_force_settlement_bridge()
    
    # 5. Stale invoices
    stale = check_stale_invoices()
    if stale > 0:
        log("WARN", f"Found {stale} stale invoices, forcing settlement bridge")
        heal_force_settlement_bridge()
    
    # 6. Mail sender
    if not check_mail_sender():
        log("WARN", "Mail sender unhealthy, restarting")
        heal_restart_service("empire-mail-sender")
    
    log("INFO", "Revenue watchdog cycle complete")

if __name__ == "__main__":
    main()