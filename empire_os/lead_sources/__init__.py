"""
Empire OS v3 — Lead Source Registry
====================================
Single source of truth for all lead sources.
"""

from dataclasses import dataclass
from typing import Optional, Iterator, List, Any, Callable

# ──────────────────────────────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class LeadCandidate:
    """A potential lead found by a source. Maps to /v1/leads/direct payload."""
    name: str
    email: str = ""
    phone: str = ""
    niche: str = ""
    metro: str = ""
    state: str = ""
    details: str = ""
    source: str = ""
    lead_score: int = 50
    url: str = ""
    raw: dict = None

    def to_intake_payload(self) -> dict:
        d = {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "niche": self.niche,
            "metro": self.metro,
            "state": self.state,
            "details": self.details,
            "source": self.source,
            "lead_score": self.lead_score,
        }
        return {k: v for k, v in d.items() if v}

@dataclass
class SourceInfo:
    name: str
    tier: str
    requires: list
    description: str
    run_fn: Callable = None

# ──────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────

_REGISTRY: dict = {}

def register(info: "SourceInfo"):
    _REGISTRY[info.name] = info

def list_sources() -> list:
    _import_sources()
    return list(_REGISTRY.values())

def get_source(name: str) -> "SourceInfo":
    _import_sources()
    return _REGISTRY[name]

def run_all_sources(metro: str = None, verticals: list = None, limit: int = 40) -> Iterator["LeadCandidate"]:
    """Run all REAL sources, yield LeadCandidate."""
    _import_sources()
    for src in _REGISTRY.values():
        if src.tier != "real":
            continue
        if src.run_fn is None:
            continue
        try:
            import inspect
            sig = inspect.signature(src.run_fn)
            params = list(sig.parameters.keys())
            kwargs = {"metro": metro, "limit": limit}
            if "verticals" in params:
                kwargs["verticals"] = verticals
            yield from src.run_fn(**kwargs)
        except Exception as e:
            print(f"[lead_sources] {src.name} failed: {e}")

# ──────────────────────────────────────────────────────────────────────
# Import all sources
# ──────────────────────────────────────────────────────────────────────

def _import_sources():
    from empire_os.lead_sources import (
        permits, chicago_311, court_listener, reddit_json,
        nyc_hpd, storm_alerts, overpass, universal_scraper,
        search_api, searxng_search, solar_intelligence,
    )
    for mod in (permits, chicago_311, court_listener, reddit_json,
                nyc_hpd, storm_alerts, overpass, universal_scraper,
                search_api, searxng_search, solar_intelligence):
        if hasattr(mod, "register_source"):
            mod.register_source(register)

# ──────────────────────────────────────────────────────────────────────
# Registry Storage
# ──────────────────────────────────────────────────────────────────────

_REGISTRY: dict = {}

def register(info: "SourceInfo"):
    _REGISTRY[info.name] = info

def list_sources() -> list:
    _import_sources()
    return list(_REGISTRY.values())

def get_source(name: str) -> "SourceInfo":
    _import_sources()
    return _REGISTRY[name]

# ──────────────────────────────────────────────────────────────────────
# Import all sources
# ──────────────────────────────────────────────────────────────────────

def _import_sources():
    from empire_os.lead_sources import (
        permits, chicago_311, court_listener, reddit_json,
        nyc_hpd, storm_alerts, overpass, universal_scraper,
        search_api, searxng_search, solar_intelligence,
    )
    for mod in (permits, chicago_311, court_listener, reddit_json,
                nyc_hpd, storm_alerts, overpass, universal_scraper,
                search_api, searxng_search, solar_intelligence):
        if hasattr(mod, "register_source"):
            mod.register_source(register)