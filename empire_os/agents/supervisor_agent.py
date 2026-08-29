#!/usr/bin/env python3
"""
Empire OS Supervisor Agent - deprecated, replaced by supervisor_daemon.py.

This script exists for backward compatibility but does not run the main supervisor loop.
The actual supervisor daemon runs via: python3 /root/empire_os/scripts/supervisor_daemon.py

The legacy supervisor_agent.py was replaced because:
- The system was using 35+ broken supervisor processes in crashes
- A proper systemd-based supervisor was needed
- The new supervisor_daemon.py monitors all empire-agent-* systemd services
- The simple supervisor only checks a limited set of agents (commander, systems_engineer, etc.)

For production use, run the supervisor_daemon.py script.
"""
import json
import subprocess
import time
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path("/root/feedback/supervisor_legacy.log")

def log(level, msg, **fields):
    """Log message with timestamp."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"{json.dumps(entry)}\n")
    print(f"[LOG {datetime.now(timezone.utc).strftime('%H:%M:%S')}] {level}: {msg}")

def check_agent(agent_name):
    """Check if an agent is currently running."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", f"empire-agent-{agent_name}.service"],
            capture_output=True,
            text=True
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False

def main():
    """Main supervisor loop - DEPRECATED.
    
    This script is kept for backward compatibility but should not be used in production.
    The new supervisor_daemon.py provides more robust supervisor functionality.
    
    If you need to use this legacy supervisor, ensure that:
    1. The required agents (commander, systems_engineer, lead_deliverer, bsc_listener) are installed
    2. This script has proper systemd supervision (not recommended)
    """
    log("WARN", "Legacy supervisor_agent.py is deprecated", 
        note="Use python3 /root/empire_os/scripts/supervisor_daemon.py instead",
        timestamp=time.time())
    
    log("INFO", "Starting legacy supervisor (limited functionality)", 
        agents=["commander", "systems_engineer", "lead_deliverer", "bsc_listener"])
    
    # Check key agents
    agents_to_monitor = ["commander", "systems_engineer", "lead_deliverer", "bsc_listener"]
    
    while True:
        try:
            failed = []
            
            for agent in agents_to_monitor:
                if not check_agent(agent):
                    failed.append(agent)
                    log("WARN", "Agent is down", agent=agent)
            
            if failed:
                log("EVENT", "Agents down", agents=", ".join(failed))
            else:
                log("INFO", "All monitored agents running", agents=", ".join(agents_to_monitor))
            
            time.sleep(60)  # Check every 60 seconds
            
        except KeyboardInterrupt:
            log("INFO", "Legacy supervisor shutting down")
            break
        except Exception as e:
            log("ERROR", "Unexpected error in legacy supervisor", error=str(e))
            time.sleep(60)

if __name__ == "__main__":
    # Validate environment
    if not LOG_FILE.parent.exists():
        print("Creating log directory...")
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        main()
    except KeyboardInterrupt:
        log("INFO", "Legacy supervisor interrupted by user")
        sys.exit(0)
    except Exception as e:
        log("CRITICAL", "Legacy supervisor failed", error=str(e))
        sys.exit(1)