#!/usr/bin/env python3
"""
PM2 setup for Empire OS v3 — wraps every agent + the hub as a PM2 process.

Each entry runs `incus exec <container> -- python3 <agent_script>` so PM2
manages the host-side process while the agent runs inside its container.

PM2 gives us:
  - Unified `pm2 list` view of every process
  - Auto-restart on crash (already provided by orchestrator, now PM2 too)
  - Centralized logs at ~/.pm2/logs/
  - Startup scripts (`pm2 startup`, `pm2 save`)
  - Memory/CPU monitoring (`pm2 monit`)

This script is idempotent — re-run safely to refresh the process list.
"""
import json
import subprocess
from pathlib import Path

REGISTRY = Path("/root/empire_os/config/agent_registry.json")
PM2_HOME = Path("/root/.pm2")
PM2_HOME.mkdir(parents=True, exist_ok=True)

ROLE_SCRIPT = {
    "mesh": "/root/empire_os/empire_os/agents/mesh_agent.py",
    "business": "/root/empire_os/empire_os/agents/business_agent.py",
    "growth": "/root/empire_os/empire_os/agents/growth_agent.py",
    "engineering": "/root/empire_os/empire_os/agents/engineering_agent.py",
    "scheduling": "/root/empire_os/empire_os/agents/scheduling_agent.py",
    "copywriting": "/root/empire_os/empire_os/agents/copywriting_agent.py",
    "email": "/root/empire_os/empire_os/agents/email_agent.py",
    "predictive": "/root/empire_os/empire_os/agents/predictive_agent.py",
    "design": "/root/empire_os/empire_os/agents/design_agent.py",
    "funnel": "/root/empire_os/empire_os/agents/funnel_agent.py",
    "traffic": "/root/empire_os/empire_os/agents/traffic_agent.py",
    "conversion": "/root/empire_os/empire_os/agents/conversion_agent.py",
}


def run(cmd):
    """Run shell command, return (rc, stdout, stderr)."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout, r.stderr


def main():
    if not REGISTRY.exists():
        print("No agent registry at", REGISTRY)
        return

    reg = json.loads(REGISTRY.read_text())
    agents = reg.get("agents", {})

    # Stop existing empire-os processes
    run("pm2 delete all 2>/dev/null")
    print("Cleared existing PM2 processes")

    started = 0
    for name, info in agents.items():
        role = info.get("role", "")
        container = info.get("container", name)
        script = ROLE_SCRIPT.get(role)

        if not script:
            print(f"  skip {name} (no script for role '{role}')")
            continue

        # PM2 process = incus exec command
        # PM2 needs the interpreter to be 'sh' (not bash) for proper command parsing,
        # and we need to pass the full command as one string
        cmd = f'incus exec {container} -- /root/venv/bin/python3 {script}'
        proc_name = f"empire-{role}"

        # Use --no-autorestart so PM2 doesn't spam restarts; the agent's own
        # try/except loop handles its own recovery
        rc, out, err = run(
            f"pm2 start '{cmd}' --name {proc_name} "
            f"--interpreter none --no-autorestart "
            f"--log /root/feedback/{role}.pm2.log"
        )
        if rc == 0:
            started += 1
            print(f"  + {proc_name} -> {container}:{role}")
        else:
            print(f"  ! {proc_name} failed: {err[:200] or out[:200]}")

    print(f"\nStarted {started} PM2 processes")

    # Add empire-orchestrator too
    run('pm2 start /root/venv/bin/python3 --name empire-orchestrator '
        '--interpreter none -- /root/empire_os/scripts/orchestrator.py')
    print("  + empire-orchestrator")

    # Save the process list
    run("pm2 save")
    print("\nPM2 process list saved. View with: pm2 list")
    print("Monitor with: pm2 monit")
    print("Logs at: ~/.pm2/logs/")


if __name__ == "__main__":
    main()