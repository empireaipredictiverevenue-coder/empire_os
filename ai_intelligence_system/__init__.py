"""
Empire AI Intelligence System (V4) — public package.

This package is a thin facade over the v3 Empire OS intelligence surfaces.
It does not replace the underlying work — it composes real, already-running
v3 systems (cortex_engine, lead_sniper_agent, crawler_agent, scout_intel,
agent_registry.json) under one stable interface for any agent.

Honest status:
  - V4 Intelligence Core backed by cortex_engine (predictive 4 pillars)
  - V4 Lead Scraping backed by crawler_agent + b2b_scraper_agent
  - V4 AI Scoring backed by lead_sniper_agent omega scores
  - V4 Agent Swarm backed by config/agent_registry.json

No marketing copy. No fabricated numbers. If a backing source is missing,
the status says so.

The public entry point is `v4_system_entry_point(agent_id)`.
"""
from ai_intelligence_system.v4_system import v4_system_entry_point, get_v4_system

__all__ = ["v4_system_entry_point", "get_v4_system"]
__version__ = "V4.0"
