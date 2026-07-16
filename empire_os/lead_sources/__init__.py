"""
Empire OS v3 — Lead Source Registry
====================================

Lead sources that produce LeadCandidate objects, fed into /v1/leads/direct.
Each source has:
  - name: identifier
  - tier: real | stub (real means actively running, stub means wired but disabled)
  - requires: env vars needed
  - run(): async generator yielding LeadCandidate
"""

from dataclasses import dataclass, asdict
from typing import Optional, Iterator
from pathlib import Path
import json


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
        d = asdict(self)
        d.pop("raw", None)
        return {k: v for k, v in d.items() if v}


@dataclass
class SourceInfo:
    name: str
    tier: str
    requires: list
    description: str
    run_fn: Optional[callable] = None


_REGISTRY: dict = {}


def register(info: SourceInfo):
    _REGISTRY[info.name] = info


def list_sources() -> list:
    return list(_REGISTRY.values())


def get_source(name: str) -> SourceInfo:
    return _REGISTRY[name]


NICHE_KEYWORDS = {
    "plumbing": ["plumber", "plumbing", "drain", "sewer", "pipe", "water heater"],
    "electrical": ["electrician", "electrical", "wiring", "panel", "outlet"],
    "hvac": ["hvac", "furnace", "air condition", "ac repair", "heating", "cooling", "heat pump"],
    "roofing": ["roofer", "roofing", "roof repair", "shingle", "gutter"],
    "landscaping": ["landscap", "lawn", "tree service", "irrigation", "yard"],
    "painting": ["painter", "painting", "interior paint", "exterior paint"],
    "mold_remediation": ["mold", "remediation", "water damage"],
    "pest_control": ["pest", "exterminator", "termite", "rodent"],
    "carpentry": ["carpenter", "woodwork", "deck", "cabinet"],
    "general_contractor": ["contractor", "remodel", "renovation", "addition"],
    "water_damage_restoration": ["water damage", "flood", "restoration"],
    "fire_damage_restoration": ["fire damage", "smoke damage"],
    "disaster_recovery": ["disaster", "storm damage", "cleanup"],
    "sewage_cleanup": ["sewage", "septic"],
    "emergency_plumbing": ["emergency", "burst pipe", "flooding"],
    "lead_remediation": ["lead paint", "lead abatement"],
    "asbestos_remediation": ["asbestos"],
    "structural_repair": ["foundation", "structural", "support beam"],
}


def infer_niche(text: str) -> str:
    text_l = text.lower()
    best, score = "", 0
    for niche, kws in NICHE_KEYWORDS.items():
        hits = sum(1 for kw in kws if kw in text_l)
        if hits > score:
            best, score = niche, hits
    return best or "general_contractor"


def _import_sources():
    from empire_os.lead_sources import (
        permits, chicago_311, court_listener, reddit_json,
        nyc_hpd, storm_alerts,
    )
    for mod in (permits, chicago_311, court_listener, reddit_json,
                nyc_hpd, storm_alerts):
        if hasattr(mod, "register_source"):
            mod.register_source(register)


def run_all_sources(metro_filter: str = None) -> Iterator[LeadCandidate]:
    """Run all REAL sources, yield candidates."""
    _import_sources()
    for src in _REGISTRY.values():
        if src.tier != "real":
            continue
        if src.run_fn is None:
            continue
        try:
            yield from src.run_fn(metro=metro_filter)
        except Exception as e:
            print(f"source {src.name} failed: {e}")
