#!/usr/bin/env python3
"""
Simple Supervisor - keeps key Empire agents running.
"""
import subprocess
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path("/tmp/supervisor.log")

def log(level, msg, **fields):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"{entry}\n")
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {level}: {msg}")

def is_agent_running(agent_name):
    try:
        result = subprocess.run(
            ["systemctl", "is-active", f"empire-agent-{agent_name}.service"],
            capture_output=True,
            text=True
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False

def start_agent(agent_name):
    log("INFO", f"Starting agent {agent_name}")
    try:
        subprocess.run(
            ["systemctl", "start", f"empire-agent-{agent_name}.service"],
            check=True,
            capture_output=True
        )
        time.sleep(1)
        return is_agent_running(agent_name)
    except Exception as e:
        log("ERROR", f"Failed to start {agent_name}: {e}")
        return False

def main():
    log("INFO", "Supervisor starting")
    
    agents = ["commander", "systems_engineer", "lead_deliverer", "solana_listener"]
    
    while True:
        try:
            restarted = []
            for agent in agents:
                if not is_agent_running(agent):
                    restarted.append(agent)
                    start_agent(agent)
            
            if restarted:
                log("EVENT", f"Agents restarted: {', '.join(restarted)}")
            else:
                log("INFO", f"All agents running: {', '.join(agents)}")
            
            time.sleep(60)
            
        except KeyboardInterrupt:
            log("INFO", "Supervisor shutting down")
            break
        except Exception as e:
            log("ERROR", f"Supervisor error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
