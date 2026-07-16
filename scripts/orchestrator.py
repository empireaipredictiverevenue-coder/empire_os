#!/usr/bin/env python3
"""
Empire OS v3 — Agentic Loop Orchestrator (no cron, no schedules).

Replaces cron jobs with a single Python process that runs ALL agents
on their natural cadence. Each agent decides when to tick based on
its own state — no global scheduler, no crontab, no `every 6 hours`.

This runs as a systemd service (`empire-orchestrator.service`) on the
host. It:
  1. Loads agent registry
  2. Spawns each agent as a long-running subprocess in its container
  3. Monitors liveness (restarts if dead)
  4. Emits unified heartbeat to feedback log

Each agent runs its OWN loop internally — its `tick()` interval is
defined in its code, not in cron. The orchestrator just keeps them alive.
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REGISTRY = Path("/root/empire_os/config/agent_registry.json")
ORCHESTRATOR_LOG = Path("/root/feedback/orchestrator.log")
ORCHESTRATOR_LOG.parent.mkdir(parents=True, exist_ok=True)


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).isoformat()
    line = "[%s] [%s] orchestrator: %s\n" % (ts, level, msg)
    with ORCHESTRATOR_LOG.open("a") as f:
        f.write(line)
    print(line.strip())


def load_agents():
    if not REGISTRY.exists():
        return {}
    return json.loads(REGISTRY.read_text()).get("agents", {})


def is_agent_running(container):
    """Check if the agent's container is RUNNING."""
    try:
        r = subprocess.run(
            ["incus", "list", container, "-c", "s", "-f", "csv"],
            capture_output=True, text=True, timeout=10
        )
        return "RUNNING" in r.stdout
    except Exception:
        return False


def agent_log_size(container, log_path):
    """Get current log line count from inside container."""
    if not log_path:
        return 0
    try:
        r = subprocess.run(
            ["incus", "exec", container, "--", "wc", "-l", log_path],
            capture_output=True, text=True, timeout=10
        )
        out = r.stdout.strip().split()
        return int(out[0]) if out and out[0].isdigit() else 0
    except Exception:
        return 0


def spawn_agent(name, info):
    """Ensure an agent's loop is running inside its container."""
    container = info.get("container", name)
    role = info.get("role", "")
    log_path = info.get("log_path", "")

    if not is_agent_running(container):
        return False, "container not running"

    # Find the agent script — check both naming conventions
    candidates = [
        f"/root/empire_os/empire_os/agents/{role}_agent.py",
        f"/root/empire_os/empire_os/agents/{role.replace('-', '_')}_agent.py",
        f"/root/empire_os/empire_os/{role}_agent.py" if role != "hub" else None,
        f"/root/empire_os/empire_os/agents/{role}.py",
    ]
    agent_script = None
    for path in candidates:
        if not path:
            continue
        try:
            r = subprocess.run(
                ["incus", "exec", container, "--", "test", "-f", path],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                agent_script = path
                break
        except Exception:
            continue

    if not agent_script:
        return True, "no agent script (external service)"

    try:
        r = subprocess.run(
            ["incus", "exec", container, "--", "pgrep", "-f", "agent.py"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0 and r.stdout.strip():
            return True, "already running"
    except Exception:
        pass

    log(f"spawning {container}: {agent_script}")
    subprocess.Popen(
        ["incus", "exec", container, "--", "/root/venv/bin/python3", agent_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True, "spawned"


def monitor_loop():
    """Main orchestrator loop — runs forever, no cron."""
    log("agentic orchestrator starting (no cron, no schedules)")
    log("each agent runs its own internal tick loop; I just keep them alive")

    while True:
        agents = load_agents()
        if not agents:
            log("no agents in registry — sleeping 30s", "WARN")
            time.sleep(30)
            continue

        for name, info in agents.items():
            container = info.get("container", name)
            role = info.get("role", "")
            if not role or role == "hub":
                continue

            log_path = info.get("log_path", "")
            size_before = agent_log_size(container, log_path)

            running, status = spawn_agent(name, info)
            if not running:
                log("%s: %s" % (container, status), "WARN")

            time.sleep(0.5)
            size_after = agent_log_size(container, log_path)
            if size_after > size_before:
                log("%s: log grew %d -> %d lines" % (container, size_before, size_after))

        time.sleep(60)


if __name__ == "__main__":
    try:
        monitor_loop()
    except KeyboardInterrupt:
        log("shutting down")
        sys.exit(0)