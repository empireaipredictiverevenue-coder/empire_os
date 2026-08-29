"""
Empire OS v3 — Lead Source Registry
====================================
Single source of truth for all lead sources.

VERIFY-GATE (2026-08-24):
  Every source MUST prove its endpoint returns real rows before it can
  register. A source whose probe returns 0 rows (404 / dead ID / blocked)
  is REJECTED at import time — it never enters the registry, so a fake
  placeholder endpoint can never silently look alive in the crawler.

  Add a `probe` callable to SourceInfo that hits the live endpoint and
  returns True iff >=1 real row came back. No probe => source is treated
  as non-network (scraper/agent) and admitted without network check.
"""

from typing import Optional, Iterator, List, Any, Callable, Dict
from empire_os.lead_sources.models import LeadCandidate, SourceInfo, http_probe

# NOTE: LeadCandidate / SourceInfo / http_probe are canonical in
# empire_os.lead_sources.models — imported here, NOT redefined, so the
# verify-gate `probe` field is the single shared definition.

# ──────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────

_REGISTRY: Dict[str, "SourceInfo"] = {}
_REJECTED: Dict[str, str] = {}   # name -> reason it failed the verify-gate

def register(info: "SourceInfo"):
    """Register a source. Runs the verify-gate if a probe is supplied.

    A source whose probe fails (dead/placeholder endpoint) is REJECTED and
    recorded in _REJECTED so it can never contribute leads. This is the
    hard stop against fabricated endpoints.
    """
    if info.probe is not None:
        try:
            ok = bool(info.probe())
        except Exception as e:
            _REJECTED[info.name] = f"probe error: {e}"
            print(f"[verify-gate] REJECTED {info.name}: probe error: {e}")
            return
        if not ok:
            _REJECTED[info.name] = "probe returned 0 real rows"
            print(f"[verify-gate] REJECTED {info.name}: endpoint returned 0 real rows (dead/placeholder)")
            return
    _REGISTRY[info.name] = info

def list_sources() -> list:
    _import_sources()
    return list(_REGISTRY.values())

def list_rejected() -> dict:
    _import_sources()
    return dict(_REJECTED)

def get_source(name: str) -> "SourceInfo":
    _import_sources()
    return _REGISTRY[name]

def run_all_sources(metro: str = None, verticals: list = None, limit: int = 40) -> Iterator["LeadCandidate"]:
    """Run all REAL, verify-gated sources, yield LeadCandidate."""
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

def verify_sources() -> int:
    """Probe every registered + rejected source. Return count of failures."""
    _import_sources()
    print("=== Empire OS lead source verify-gate ===")
    fails = 0
    for name, info in _REGISTRY.items():
        if info.probe is None:
            print(f"  [SKIP]  {name:28s} non-network source (no probe)")
            continue
        try:
            ok = bool(info.probe())
        except Exception as e:
            print(f"  [RED]   {name:28s} probe error: {e}")
            fails += 1
            continue
        if ok:
            print(f"  [GREEN] {name:28s} endpoint live, rows returned")
        else:
            print(f"  [RED]   {name:28s} endpoint returned 0 rows")
            fails += 1
    for name, reason in _REJECTED.items():
        print(f"  [REJ]   {name:28s} {reason}")
        fails += 1
    print(f"=== {fails} source(s) failing verify-gate ===")
    return fails

# ──────────────────────────────────────────────────────────────────────
# Import all sources
# ──────────────────────────────────────────────────────────────────────

def _import_sources():
    from empire_os.lead_sources import (
        permits, chicago_311, chicago_permits, la_permits,
        court_listener, reddit_json, nyc_hpd, storm_alerts, overpass,
        universal_scraper, search_api, searxng_search, solar_intelligence,
        sam_gov, fema, uk_planning,
        gmaps_scraper, yelp_scraper, reddit_scraper, enhanced_universal_scraper,
        google_news, usaspending, bing_local,
    )
    for mod in (permits, chicago_311, chicago_permits, la_permits,
                court_listener, reddit_json, nyc_hpd, storm_alerts, overpass,
                universal_scraper, search_api, searxng_search, solar_intelligence,
                sam_gov, fema, uk_planning,
                gmaps_scraper, yelp_scraper, reddit_scraper, enhanced_universal_scraper,
                google_news, usaspending, bing_local):
        if hasattr(mod, "register_source"):
            mod.register_source(register)
