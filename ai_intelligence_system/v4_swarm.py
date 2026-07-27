#!/usr/bin/env python3
"""
v4_swarm.py — V4 Autonomous Agent Swarm: live status from agent_registry.json.

Backed by the v3 agent_registry.json. This is a read-side facade — it
does NOT spawn agents or call systemd. The orchestrator does that.

What it gives V4 callers:
  - a stable list of registered agents with role + version
  - honest liveness status (no fake 'OPERATIONAL' — only what we can prove)
  - aggregate counts so dashboards can render "X active, Y dormant"
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ai_intelligence_system.v4_config import AGENT_REGISTRY


@dataclass(frozen=True)
class AgentInfo:
    name: str
    role: str
    version: str
    path: str
    healthy: Optional[bool] = None  # None = not probed

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "version": self.version,
            "path": self.path,
            "healthy": self.healthy,
        }


def _load_registry() -> list[AgentInfo]:
    """agent_registry.json is a dict keyed by agent name, with the agent
    config as the value. Each value has 'role', 'container', 'ip', 'log_path',
    'health_url', etc. — but not 'path' or 'version'."""
    if not AGENT_REGISTRY.exists():
        return []
    try:
        doc = json.loads(AGENT_REGISTRY.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    agents_map = doc.get("agents", {})
    out: list[AgentInfo] = []
    for name, cfg in agents_map.items():
        if not isinstance(cfg, dict):
            continue
        out.append(AgentInfo(
            name=name,
            role=cfg.get("role", "?"),
            version=str(doc.get("version", "?")),
            path=cfg.get("container", cfg.get("log_path", "?")),
        ))
    return out


def _is_healthy_unit(unit: str) -> bool:
    """Check `systemctl is-active` for a unit. Returns False on any error."""
    try:
        r = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True, text=True, timeout=3,
        )
        return r.stdout.strip() == "active"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def list_agents(probe_health: bool = False) -> list[dict]:
    """List all registered agents. If probe_health=True, check systemd."""
    agents = _load_registry()
    out = []
    for a in agents:
        if probe_health:
            unit = f"empire-{a.name}.service"
            healthy = _is_healthy_unit(unit)
            out.append(AgentInfo(a.name, a.role, a.version, a.path, healthy).to_dict())
        else:
            out.append(a.to_dict())
    return out


def get_agent(name: str) -> Optional[dict]:
    """Return one agent by name, or None."""
    for a in list_agents(probe_health=False):
        if a["name"] == name:
            return a
    return None


def get_system_status(probe_health: bool = False) -> dict:
    """V4 Agent Swarm status. Real registry count + optional health probe."""
    agents = list_agents(probe_health=probe_health)
    healthy = sum(1 for a in agents if a["healthy"] is True)
    unhealthy = sum(1 for a in agents if a["healthy"] is False)
    not_probed = sum(1 for a in agents if a["healthy"] is None)
    return {
        "component": "agent_swarm",
        "version": "V4.0",
        "backed_by": ["config/agent_registry.json", "systemctl (optional)"],
        "registered": len(agents),
        "healthy": healthy,
        "unhealthy": unhealthy,
        "not_probed": not_probed,
        "probed_health": probe_health,
    }
