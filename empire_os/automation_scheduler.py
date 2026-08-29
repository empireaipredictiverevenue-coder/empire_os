#!/usr/bin/env python3
"""
Empire Omega OS - Automation Scheduler
=======================================
Integrates 5-phase automation into Empire OS v3.
Runs via systemd timers at scheduled times.
"""

import os
import sys
import json
import sqlite3
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"
LOG_DIR = Path("/root/empire_os/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Phase schedules (24-hour format)
PHASE_SCHEDULE = {
    "discovery": "06:00",
    "scoring": "08:00", 
    "outreach": "10:00",
    "ml_loop": "18:00",
    "reporting": "20:00",
}

def log(level: str, msg: str, **fields):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields,
    }
    with open(LOG_DIR / "automation_scheduler.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    if level in ("ERROR", "WARN", "HEAL"):
        print(json.dumps(entry))

def get_conn():
    c = sqlite3.connect(DB, timeout=30, isolation_level=None)
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    return c

def run_phase(phase: str, config: Dict = None) -> Dict:
    """Run a specific automation phase."""
    log("INFO", f"Starting phase: {phase}")
    start = time.time()
    
    try:
        if phase == "discovery":
            result = run_discovery_phase()
        elif phase == "scoring":
            result = run_scoring_phase()
        elif phase == "outreach":
            result = run_outreach_phase()
        elif phase == "ml_loop":
            result = run_ml_loop_phase()
        elif phase == "reporting":
            result = run_reporting_phase()
        else:
            raise ValueError(f"Unknown phase: {phase}")
        
        duration = time.time() - start
        log("INFO", f"Phase {phase} completed", duration_seconds=round(duration, 2), **result)
        return {"success": True, "phase": phase, "duration": duration, **result}
        
    except Exception as e:
        duration = time.time() - start
        log("ERROR", f"Phase {phase} failed", duration_seconds=round(duration, 2), error=str(e))
        return {"success": False, "phase": phase, "duration": duration, "error": str(e)}

def run_discovery_phase() -> Dict:
    """Phase 1: Lead Discovery - find new leads from sources."""
    from empire_os.lead_sources import run_discovery_cycle
    return run_discovery_cycle()

def run_scoring_phase() -> Dict:
    """Phase 2: Lead Scoring - score unscored leads."""
    from empire_os.omega_scoring import run_scoring_cycle
    return run_scoring_cycle()

def run_outreach_phase() -> Dict:
    """Phase 3: Automated Outreach - Vapi calls + Resend emails."""
    from empire_os.outreach import run_outreach_cycle
    return run_outreach_cycle()

def run_ml_loop_phase() -> Dict:
    """Phase 4: ML Learning Loop - analyze conversions, update strategy."""
    from empire_os.ml_loop import run_ml_cycle
    return run_ml_cycle()

def run_reporting_phase() -> Dict:
    """Phase 5: Reporting - generate daily/weekly reports."""
    from empire_os.reporting import run_reporting_cycle
    return run_reporting_cycle()

def run_automation_now(config: Dict = None) -> Dict:
    """Run all phases immediately (manual trigger)."""
    config = config or {}
    log("INFO", "Manual automation trigger", config=config)
    
    results = {}
    for phase in ["discovery", "scoring", "outreach", "ml_loop", "reporting"]:
        results[phase] = run_phase(phase)
    
    return {"success": all(r.get("success") for r in results.values()), "phases": results}

def get_automation_status() -> Dict:
    """Get current automation status."""
    conn = get_conn()
    cur = conn.cursor()
    
    # Check last runs
    last_runs = cur.execute("""
        SELECT phase, MAX(completed_at) as last_run
        FROM automation_runs
        GROUP BY phase
    """).fetchall()
    
    # Check pending leads
    pending = cur.execute("""
        SELECT COUNT(*) as cnt FROM lane_leads WHERE status='pending'
    """).fetchone()
    
    conn.close()
    
    return {
        "is_active": True,
        "schedule": PHASE_SCHEDULE,
        "last_runs": {r["phase"]: r["last_run"] for r in last_runs},
        "pending_leads": pending["cnt"] if pending else 0,
    }

def init_automation_tables():
    """Initialize automation tracking tables."""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS automation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phase TEXT NOT NULL,
            status TEXT, -- 'running', 'completed', 'failed'
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            duration_seconds REAL,
            result_json TEXT,
            error_message TEXT
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_automation_runs_phase ON automation_runs(phase)
    """)
    
    conn.commit()
    conn.close()

def record_run(phase: str, status: str, duration: float, result: Dict = None, error: str = None):
    """Record a phase run."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO automation_runs (phase, status, completed_at, duration_seconds, result_json, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (phase, status, datetime.now(timezone.utc).isoformat(), duration, 
          json.dumps(result) if result else None, error))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_automation_tables()
    
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            print(json.dumps(get_automation_status(), indent=2))
        elif sys.argv[1] == "run":
            phase = sys.argv[2] if len(sys.argv) > 2 else None
            if phase:
                result = run_phase(phase)
            else:
                result = run_automation_now()
            print(json.dumps(result, indent=2))
        elif sys.argv[1] == "run-all":
            result = run_automation_now()
            print(json.dumps(result, indent=2))
    else:
        print("Usage: python automation_scheduler.py [status|run <phase>|run-all]")