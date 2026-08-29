#!/bin/env python3
"""
Simple Supervisor - ensures key Empire agents stay running.
This is the fallback supervisor that monitors and starts basic agents.
"""
import subprocess
import time
import sys
from datetime import datetime
from pathlib import Path

LOG = Path("/tmp/supervisor.log")

def log(level, msg, **fields):
    entry = {"ts": datetime.now().isoformat(), "level": level, "msg": msg, **fields}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{entry}\n")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {level}: {msg}")

def check_agent(agent_name):
    try:
        result = subprocess.run(["systemctl", "is-active", f"empire-agent-{agent_name}.service"], capture_output=True, text=True)
        return result.stdout.strip() == "active"
    except Exception:
        return False

def start_agent(agent_name):
    log("INFO", f"Starting agent {agent_name}")
    subprocess.run(["systemctl", "start", f"empire-agent-{agent_name}.service"], capture_output=True)
    time.sleep(2)
    return check_agent(agent_name)

def main():
    log("INFO", "Starting supervisor - monitoring Empire agents")
    
    agents = ["commander", "systems_engineer", "lead_deliverer", "bsc_listener"]
    
    while True:
        try:
            failed = []
            for agent in agents:
                if not check_agent(agent):
                    failed.append(agent)
                    start_agent(agent)
            
            if failed:
                log("EVENT", f"Agents down: {', '.join(failed)}")
            else:
                log("INFO", f"All agents running: {', '.join(agents)}")
            
            time.sleep(60)
        except KeyboardInterrupt:
            log("INFO", "Supervisor shutting down")
            break
        except Exception as e:
            log("ERROR", f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()