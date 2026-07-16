#!/usr/bin/env python3
"""
Supervisor agent - self-healing restart loop.

Per SOUL:
- 60s cadence
- probe every RoleToScript pair
- restart on absence
- backoff 0/5/30/120s
- cap 5 quick restarts per 5min
- page commander on needs_attention
"""
import json, os, shutil, subprocess, time, sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
from empire_os import funnel_closeout as _fc

FB = Path("/root/feedback")
REGISTRY_PATH = Path("/root/empire_os/config/agent_registry.json")
LOG = FB / "supervisor.jsonl"
PID_DIR = FB / "supervisor_pids"
PID_DIR.mkdir(parents=True, exist_ok=True)
INTERVAL = 60
MAX_RESTARTS_PER_5MIN = 5

restart_history = defaultdict(lambda: deque(maxlen=20))


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(e) + "\n")
    print(json.dumps(e), flush=True)


def load_registry():
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text()).get("agents", {})
    except Exception as e:
        log("ERROR", "registry_load_failed", err=str(e)[:200])
        return {}


def get_container_pid(container: str) -> str:
    try:
        r = subprocess.run(
            ["incus", "exec", container, "--", "pgrep", "-f", "agents/"],
            capture_output=True, text=True, timeout=5)
        out = (r.stdout or "").strip().split("\n")
        return out[0] if out and out[0] else ""
    except Exception:
        return ""


_INCUS = shutil.which("incus") or "/usr/bin/incus"
_PM2   = shutil.which("pm2")   or "/usr/local/bin/pm2"


def _run(cmd: list, timeout: int = 10) -> bool:
    """Run a shell command without throwing. Returns True on exit 0."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0
    except Exception:
        return False


def container_running(container: str) -> bool:
    try:
        r = subprocess.run(
            [_INCUS, "list", container, "-c", "s", "-f", "csv"],
            capture_output=True, text=True, timeout=5)
        return "RUNNING" in (r.stdout or "")
    except Exception:
        return False


def restart_role(role: str, container: str, pm2_name: str):
    now = time.time()
    history = restart_history[role]
    history.append(now)
    recent = [t for t in history if now - t < 300]
    n_recent = len(recent)
    if n_recent > 1:
        backoff = [0, 5, 30, 120][min(n_recent - 1, 3)]
        time.sleep(backoff)
    if not container_running(container):
        _run([_INCUS, "start", container])
        time.sleep(8)
        log("EVENT", "container_started", role=role, container=container)
    _run([_PM2, "restart", pm2_name])
    log("EVENT", "agent_restarted", role=role,
        pm2=pm2_name, restarts_5min=n_recent)
    if n_recent >= MAX_RESTARTS_PER_5MIN:
        log("ALERT", "needs_attention", role=role,
            reason="5_restarts_in_5min", pm2=pm2_name)


def cycle():
    registry = load_registry()
    if not registry:
        log("WARN", "empty_registry")
        return
    healthy = 0
    for cname, info in registry.items():
        if not isinstance(info, dict):
            continue
        role = info.get("role", cname)
        pm2_name = f"empire-{role.replace(chr(95), chr(45))}"
        pid = get_container_pid(cname)
        if pid:
            (PID_DIR / f"{role}.pid").write_text(pid)
            healthy += 1
            continue
        log("WARN", "no_pid", role=role, container=cname)
        restart_role(role, cname, pm2_name)
    # auto-unstick funnel: advance SETTLED leads -> billed (idempotent)
    try:
        n = _fc.run()
        if n:
            log("FUNNEL", "closeout_ran", billed=n)
    except Exception as e:
        log("ERROR", "funnel_closeout_failed", err=str(e)[:200])
    log("CYCLE", "completed", total=len(registry), healthy=healthy)


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"supervisor online - 60s cadence", flush=True)
    while True:
        try:
            cycle()
        except Exception as e:
            log("ERROR", "cycle_failed", err=str(e)[:200])
        time.sleep(INTERVAL)
