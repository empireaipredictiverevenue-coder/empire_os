
"""
Empire OS v3 - self-healing supervisor.

Watches every agent container. On process crash, restarts with
exponential backoff. On container stopped/unreachable, tries to
reboot it. Logs to /root/feedback/supervisor.jsonl.

Starts DAEMONS:
  - each agent container: `incus exec $c -- python3 /root/.../<agent>.py`
  - host agent processes (this supervisor itself runs on host)

Backoff:
  restart 1:  immediate
  restart 2:  +5s
  restart 3:  +30s
  restart 4+: +120s
  after 5 quick restarts in 5 min -> mark "needs attention"

Authors: this supervisor also writes to /root/feedback/supervisor.jsonl
which the commander agent reads each cycle to inform the human.
"""
import json, os, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

LOG = Path("/root/feedback/supervisor.jsonl")
REGISTRY = Path("/root/empire_os/scripts/agent_registry.json")
AGENTS_DIR = Path("/root/empire_os/empire_os/agents")

# Map agent role -> main script. Built dynamically from agent_registry.json
ROLE_TO_SCRIPT = {
    "sales":             "sales_agent.py",
    "marketing":         "marketing_agent.py",
    "commander":         "commander_agent.py",
    "outreach":          "outreach_runner.py",
    "crawler":           None,         # uses host-side crawler_runner.py via HTTPS trigger
    "predictive":        "predictive_agent.py",
    "sim":               "synthetic_sim_agent.py",
    "scout_intel":       "scout_intel.py",
    "switchboard":       "switchboard.py",
    "ppc":               "ppc_router.py",
    "b2b_scraper":       "b2b_scraper_agent.py",
    "contractor_scraper":"contractor_scraper_agent.py",
    "satellite_strike":  "satellite_strike_agent.py",
    "data_acquisition":  "data_acq_agent.py",
    "media_buying":      "media_buyer_agent.py",
    "vault":             None,         # watcher scripts
}

# State
PID_FILES = Path("/root/feedback/supervisor_pids")
PID_FILES.mkdir(parents=True, exist_ok=True)
START_COUNT = defaultdict(int)  # role -> int
RESTART_TIMES = defaultdict(list)  # role -> [datetime]


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **fields}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    print(json.dumps(e), flush=True)


def incus(args):
    return subprocess.run(["incus"] + args, capture_output=True, text=True, timeout=20)


def container_running(name):
    r = incus(["list", name, "-c", "s", "-f", "csv"])
    return "RUNNING" in r.stdout


def container_pid(name, script):
    """Returns PID of the agent loop process, or None."""
    r = incus(["exec", name, "--", "pgrep", "-f", script])
    out = r.stdout.strip()
    return int(out.split()[0]) if out else None


def restart_agent(name, role):
    START_COUNT[role] += 1
    n = START_COUNT[role]
    script = ROLE_TO_SCRIPT.get(role)
    if not script:
        return False, "no script for role"
    if not container_running(name):
        log("WARN", "container not running, starting",
            container=name, role=role)
        incus(["start", name])
        time.sleep(8)
        if not container_running(name):
            return False, "container start failed"
    # Kill any stale procs
    incus(["exec", name, "--", "pkill", "-f", script])
    time.sleep(1)
    # Launch fresh
    log("INFO", "launching", container=name, role=role, attempt=n)
    # We cant background+exit_after from this script easily. Use nohup trick
    # via launching a wrapper that detaches.
    cmd = ("nohup /usr/bin/python3 /root/empire_os/empire_os/agents/{script} "
           "> /root/feedback/{role}.log 2>&1 &")
    incus(["exec", name, "--", "bash", "-c", cmd.format(script=script, role=role)])
    time.sleep(2)
    pid = container_pid(name, script)
    if pid is None:
        return False, "no pid after launch"
    return True, str(pid)


def container_alive(role):
    """Map role -> container name. Read from registry."""
    if not REGISTRY.exists():
        return None
    reg = json.loads(REGISTRY.read_text())
    for entry in (reg if isinstance(reg, list) else reg.get("agents", [])):
        if entry.get("role") == role:
            return entry.get("container") or entry.get("name")
    return None


def check_role(role):
    name = container_alive(role)
    if not name:
        return
    script = ROLE_TO_SCRIPT.get(role)
    if not script:
        return
    pid = container_pid(name, script)
    if pid is None:
        # Dead. Decide whether to restart.
        times = RESTART_TIMES[role]
        now = datetime.now(timezone.utc)
        recent = [t for t in times if now - t < timedelta(minutes=5)]
        if len(recent) >= 5:
            log("ERROR", "needs_attention",
                container=name, role=role,
                msg="5 restarts in 5min - investigate")
            return
        # backoff
        deltas = [0, 5, 30, 120, 120]
        wait = deltas[min(len(times), len(deltas) - 1)]
        log("WARN", "backoff_wait", container=name, role=role, wait=wait)
        time.sleep(wait)
        ok, info = restart_agent(name, role)
        if ok:
            RESTART_TIMES[role].append(now)
            log("EVENT", "auto_restarted",
                container=name, role=role, pid=info, attempt=START_COUNT[role])


def cycle():
    for role in ROLE_TO_SCRIPT.keys():
        try:
            check_role(role)
        except Exception as e:
            log("ERROR", "check_role", role=role, err=str(e)[:150])


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] supervisor online", flush=True)
    while True:
        try: cycle()
        except Exception as e: log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(60)
