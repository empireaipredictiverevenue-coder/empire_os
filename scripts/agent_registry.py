#!/usr/bin/env python3
"""
Empire OS v3 — Agent Registry
Every agent gets its own Incus container. The registry tracks:
  - container name + IP
  - role + responsibilities
  - log path + health URL
  - creation time + memory footprint
  - dependencies (which other agents it talks to)

New agents are auto-discovered when their container is created with the
right convention: /root/<role>/agent.py + /root/<role>/<role>.log
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REGISTRY_PATH = Path("/root/empire_os/config/agent_registry.json")
REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_registry():
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {"version": 1, "agents": {}}


def save_registry(reg):
    reg["last_updated"] = datetime.now(timezone.utc).isoformat()
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2))


def incus(cmd, timeout=30):
    """Run an incus command."""
    r = subprocess.run(f"incus {cmd}", shell=True, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def discover_containers():
    """List all running/stopped incus containers."""
    rc, out = incus("list -c n,s,4,a -f csv")
    containers = []
    if rc == 0:
        for line in out.split("\n"):
            if not line.strip():
                continue
            parts = line.split(",")
            name = parts[0].strip()
            state = parts[1].strip() if len(parts) > 1 else "UNKNOWN"
            ip = parts[2].strip() if len(parts) > 2 else ""
            containers.append({"name": name, "state": state, "ip": ip})
    return containers


def probe_container(name):
    """Probe a container to see if it's an agent (has /root/<role>/ pattern)."""
    rc, out = incus(f"exec {name} -- ls /root/", timeout=10)
    if rc != 0:
        return None
    candidates = []
    for line in out.split("\n"):
        line = line.strip()
        if not line or line in ("snap",):
            continue
        role_path = f"/root/{line}"
        rc2, out2 = incus(f"exec {name} -- ls {role_path}/agent.py 2>/dev/null", timeout=5)
        if rc2 == 0:
            candidates.append(line)
    return candidates


def register_agent(name, role, log_path, health_url=None, depends_on=None, description=""):
    """Register an agent in the registry."""
    reg = load_registry()
    rc, out = incus(f"list {name} -c 4 -f csv", timeout=5)
    ip = out.strip() if rc == 0 else ""
    reg["agents"][name] = {
        "role": role,
        "container": name,
        "ip": ip,
        "log_path": log_path,
        "health_url": health_url,
        "depends_on": depends_on or [],
        "description": description,
        "registered_at": reg["agents"].get(name, {}).get("registered_at", datetime.now(timezone.utc).isoformat()),
    }
    save_registry(reg)
    print(f"Registered: {name} ({role})")


def auto_discover():
    """Auto-discover agents by scanning all containers for /root/<role>/agent.py."""
    reg = load_registry()
    containers = discover_containers()
    added = 0
    for c in containers:
        if c["state"] == "RUNNING":
            roles = probe_container(c["name"]) or []
            for role in roles:
                key = c["name"]
                if key not in reg["agents"]:
                    log_path = f"/root/{role}/{role}.log"
                    rc, out = incus(f"exec {c['name']} -- ls {log_path} 2>/dev/null", timeout=5)
                    if rc != 0:
                        log_path = f"/root/{role}/agent.log"
                    register_agent(
                        name=key,
                        role=role,
                        log_path=log_path,
                        health_url=None,
                        description=f"Auto-discovered {role} agent",
                    )
                    added += 1
    print(f"Discovered {added} new agent(s)")
    return reg


def create_agent_container(name, role, python_deps="requests beautifulsoup4 lxml", port=None):
    """Create a new Incus container for an agent."""
    rc, out = incus("image list -f csv | grep -i ubuntu | head -1 | cut -d, -f2", timeout=10)
    fingerprint = out.strip().split(",")[0] if out.strip() else ""
    if not fingerprint:
        rc2, out2 = incus("image list -f csv", timeout=10)
        for line in out2.split("\n"):
            if "ubuntu" in line.lower():
                fingerprint = line.split(",")[0]
                break
    if not fingerprint:
        print("No Ubuntu image found")
        return False

    rc, out = incus(f"launch {fingerprint} {name}", timeout=120)
    if rc != 0:
        print(f"Failed to launch {name}: {out}")
        return False
    print(f"Launched {name}")

    incus(f"exec {name} -- apt-get update -qq", timeout=120)
    incus(f"exec {name} -- apt-get install -y -qq python3-venv", timeout=120)
    incus(f"exec {name} -- python3 -m venv /root/venv", timeout=60)
    if python_deps:
        incus(f"exec {name} -- /root/venv/bin/pip install -q {python_deps}", timeout=120)
    incus(f"exec {name} -- mkdir -p /root/{role}", timeout=10)

    log_path = f"/root/{role}/{role}.log"
    health_url = f"http://localhost:{port}/health" if port else None

    register_agent(
        name=name,
        role=role,
        log_path=log_path,
        health_url=health_url,
        description=f"{role} agent — auto-provisioned",
    )
    print(f"Container {name} provisioned for role '{role}'")
    return True


def list_agents():
    reg = load_registry()
    print(f"{'Container':<20} {'Role':<20} {'IP':<18} {'Log':<40}")
    print("-" * 100)
    for name, info in sorted(reg["agents"].items()):
        ip = info.get("ip", "")[:16]
        log = info.get("log_path", "")[:38]
        print(f"{name:<20} {info.get('role',''):<20} {ip:<18} {log:<40}")


def main():
    p = argparse.ArgumentParser(description="Empire OS v3 Agent Registry")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List registered agents")
    sub.add_parser("discover", help="Auto-discover new agents by scanning containers")

    c = sub.add_parser("create", help="Provision a new agent container")
    c.add_argument("name", help="Container name")
    c.add_argument("role", help="Agent role (becomes /root/<role>/)")
    c.add_argument("--port", type=int, default=None)
    c.add_argument("--deps", default="requests beautifulsoup4 lxml")

    r = sub.add_parser("register", help="Manually register an existing container")
    r.add_argument("name")
    r.add_argument("role")
    r.add_argument("--log", default=None)
    r.add_argument("--url", default=None)
    r.add_argument("--description", default="")

    args = p.parse_args()
    if args.cmd == "list":
        list_agents()
    elif args.cmd == "discover":
        auto_discover()
    elif args.cmd == "create":
        create_agent_container(args.name, args.role, args.deps, args.port)
    elif args.cmd == "register":
        register_agent(
            args.name, args.role,
            log_path=args.log or f"/root/{args.role}/{args.role}.log",
            health_url=args.url,
            description=args.description,
        )


if __name__ == "__main__":
    main()