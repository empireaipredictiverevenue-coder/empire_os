#!/usr/bin/env python3
"""sandbox.py — Incus-backed agent sandbox.

Each coding agent runs in its own Incus container (or container+workdir
isolation) so a bad worker cannot wedge the shared SQLite or host. Reuses
the exact `incus exec` pattern Empire OS already uses for remote control.
"""
from __future__ import annotations
import subprocess, uuid, os, time

HUB = "empire-hub"  # reuse existing hub container as the agent runtime base


def run_in_sandbox(script_path: str, container: str = HUB, timeout: int = 300) -> str:
    """Execute a worker script. If incus is available (host context) run inside
    the hub container; otherwise (already inside the container) run locally.
    Process isolation is sufficient — the shared SQLite is gated by db_writer.
    """
    import shutil
    if shutil.which("incus"):
        cmd = ["incus", "exec", container, "--", "bash", "-c",
               f"timeout {timeout} /root/venv/bin/python3 /root/{os.path.basename(script_path)}"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
        return r.stdout + r.stderr
    # local fallback (inside container)
    r = subprocess.run([f"/root/venv/bin/python3", script_path],
                       capture_output=True, text=True, timeout=timeout + 30)
    return r.stdout + r.stderr


def spawn_agent_container(base: str = HUB) -> str:
    """Clone a fresh agent container from base for true isolation."""
    name = f"agent-{uuid.uuid4().hex[:8]}"
    subprocess.run(["incus", "copy", base, name], check=True)
    subprocess.run(["incus", "start", name], check=True)
    # wait for boot
    for _ in range(20):
        if subprocess.run(["incus", "info", name], capture_output=True).returncode == 0:
            break
        time.sleep(1)
    return name


def kill_agent_container(name: str):
    subprocess.run(["incus", "delete", name, "--force"], check=False)


if __name__ == "__main__":
    print(run_in_sandbox("/root/factory/_probe.py") or "no probe")
