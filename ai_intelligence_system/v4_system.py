#!/usr/bin/env python3
"""
v4_system.py — V4 Empire AI Intelligence System: the public facade.

Composes the four V4 engines into a single access point so any agent
(CLI, GUI, automation, MCP, hermes) can call one function and get the
union of all real status.

This module is honest: every status value is read from a real source
or labelled 'missing'. No marketing copy, no made-up numbers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ai_intelligence_system import v4_intelligence, v4_lead_scraping, v4_scoring, v4_swarm
from ai_intelligence_system.v4_config import EMPIRE_ROOT


__all__ = ["v4_system_entry_point", "get_v4_system"]


def v4_system_entry_point(agent_id: str = "default_agent",
                          probe_health: bool = False) -> dict:
    """The one-call V4 access point for any agent.

    Args:
        agent_id: Identifier for the calling agent (for logging/tracing).
        probe_health: If True, also probe systemd for each registered
                      agent's liveness. Adds ~1s per N agents.

    Returns:
        dict with real status from all 4 engines, the access endpoints,
        and honest 'live' / 'missing' flags.
    """
    intel = v4_intelligence.get_system_status()
    scraping = v4_lead_scraping.get_system_status()
    scoring = v4_scoring.get_system_status()
    swarm = v4_swarm.get_system_status(probe_health=probe_health)

    # The system is "live" if at least one engine has real backing data.
    live = (
        intel["cortex_available"]
        or scraping["lane_leads_total"] > 0
        or scoring["scored"] > 0
        or swarm["registered"] > 0
    )

    return {
        "agent_id": agent_id,
        "system": {
            "name": "Empire AI Intelligence System (V4)",
            "version": "V4.0",
            "status": "LIVE" if live else "MISSING_BACKING",
            "live": live,
        },
        "engines": {
            "intelligence_core": intel,
            "lead_scraping": scraping,
            "ai_scoring": scoring,
            "agent_swarm": swarm,
        },
        "backed_by_files": [
            "ai_intelligence_system/v4_*.py",
            "config/agent_registry.json",
            "/root/feedback/cortex_report.json (written by cortex_engine)",
        ],
        "real_data_sources": [
            str(v4_intelligence.DB_PATH) if hasattr(v4_intelligence, "DB_PATH") else
            f"{EMPIRE_ROOT}/empire_os.db",
        ],
        "grant_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_v4_system() -> dict:
    """Convenience: same as v4_system_entry_point() with default agent_id."""
    return v4_system_entry_point()
