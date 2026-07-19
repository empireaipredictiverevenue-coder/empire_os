#!/usr/bin/env python3
"""niche_map — single source of truth for vertical normalization + per-lead amounts.

The Empire OS inventory (crm_leads) and the buyer lanes (lanes table) use
DIFFERENT vocab for the same vertical:
  - leads:  niche = 'roofing' | 'residential_roofing' | 'commercial_roofing' | 'roof_repair'
  - lanes:  sub_niche prefix = 'residential_roofing' | 'commercial_roofing' | 'roof_repair'

Without one canonical key, a buyer who applies as "roofing" never seats the
roofing lanes, and a "roofing" lead never routes to a residential_roofing buyer.
This module collapses every alias into ONE canonical vertical and exposes the
lane prefixes + the per-lead AMOUNT for each tier.

Canonical verticals are the lane sub_niche PREFIXES that actually exist, grouped
by family. A lead or buyer niche maps to exactly one canonical vertical; a buyer
seats ALL lane prefixes in that vertical's family; a lead routes to any buyer
seated in its vertical.
"""
from __future__ import annotations
import sqlite3, os

DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")

# Canonical vertical -> the lane sub_niche PREFIXES that belong to it.
# Keyed by the family; aliases below map lead/buyer niche strings -> key.
VERTICALS = {
    "roofing":            ["residential_roofing", "commercial_roofing", "roof_repair"],
    "hvac":               ["hvac"],
    "water_damage":       ["water_damage"],
    "fire_damage":        ["fire_damage"],
    "storm_damage":       ["storm_damage"],
    "mold_remediation":   ["mold_remediation"],
    "sewage_cleanup":     ["sewage_cleanup"],
    "plumbing":           ["plumbing"],
    "electrical":         ["electrical"],
    "disaster_restoration": ["disaster_restoration"],
    "legal_mass_tort":    ["camp_lejeune", "paraquat", "roundup", "zantac", "afff", "legal_services"],
    "debt_relief":        ["debt_relief"],
    "insurance":          ["insurance"],
    "real_estate":        ["real_estate"],
    "accounting":         ["accounting"],
    "consulting":         ["consulting"],
    "managed_it":         ["managed_it"],
    "cybersecurity":      ["cybersecurity"],
    "cloud":              ["cloud"],
    "data_analytics":     ["data_analytics"],
    "software_dev":       ["software_dev"],
    "ai_automation":      ["ai_automation"],
    "marketing":          ["marketing"],
    "web_dev":            ["web_dev"],
    "tax_prep":           ["tax_prep"],
    "mortgage":           ["mortgage"],
    "investing":          ["investing"],
    "staffing":           ["staffing"],
    "dental":             ["dental"],
    "vision":             ["vision"],
    "addiction":          ["addiction"],
    "hormone_therapy":    ["hormone_therapy"],
    "ozempic":            ["ozempic"],
    "weight_loss":        ["weight_loss"],
    "pt_rehab":           ["pt_rehab"],
}

# Reverse index: alias (lowercased, underscored) -> canonical vertical key.
ALIAS = {}
for _key, _prefixes in VERTICALS.items():
    ALIAS[_key] = _key
    for _p in _prefixes:
        ALIAS[_p] = _key
# common lead-side aliases not equal to any prefix
_EXTRA = {
    "roof": "roofing", "roofer": "roofing", "roofing_co": "roofing",
    "mass_tort": "legal_mass_tort", "tort": "legal_mass_tort", "legal": "legal_mass_tort",
    "restoration": "disaster_restoration", "disaster": "disaster_restoration",
    "mold": "mold_remediation", "sewage": "sewage_cleanup",
    "it": "managed_it", "msp": "managed_it",
    "lawyer": "legal_mass_tort", "attorney": "legal_mass_tort",
}
ALIAS.update(_EXTRA)

# Hybrid per-lead AMOUNT (US cents) by tier — the price the buyer pays per lead.
TIER_PER_LEAD_CENTS = {
    "bronze":   2500,   # $25
    "silver":   4900,   # $49
    "gold":     9900,   # $99
    "platinum": 19900,  # $199
}
TIER_SEAT_CENTS = {
    "bronze":   29900,
    "silver":   59900,
    "gold":     119900,
    "platinum": 239900,
}


def _norm(s: str) -> str:
    return (s or "").lower().strip().replace(" ", "_").replace("-", "_")


def canonical(niche: str) -> str:
    """Map any lead/buyer niche string to ONE canonical vertical key.

    Tries: exact alias, substring both ways against known prefixes/aliases.
    Returns the canonical key or '' if nothing matches.
    """
    n = _norm(niche)
    if not n:
        return ""
    if n in ALIAS:
        return ALIAS[n]
    # substring: 'roofing' in 'residential_roofing', 'residential' in 'residential_roofing'
    for alias, key in ALIAS.items():
        if alias and (alias in n or n in alias):
            return key
    return ""


def lane_prefixes(vertical: str) -> list[str]:
    """Return the lane sub_niche prefixes that belong to a canonical vertical."""
    return VERTICALS.get(vertical, [])


def prefixes_for_niche(niche: str) -> list[str]:
    """Given a lead/buyer niche, return the lane prefixes to seat/route against."""
    v = canonical(niche)
    return lane_prefixes(v)


def per_lead_cents(tier: str) -> int:
    return TIER_PER_LEAD_CENTS.get(_norm(tier), 0)


def seat_cents(tier: str) -> int:
    return TIER_SEAT_CENTS.get(_norm(tier), 0)


def all_prefixes() -> list[str]:
    """Every lane prefix that exists (for validation)."""
    out = []
    for ps in VERTICALS.values():
        out.extend(ps)
    return out


def db_prefixes() -> list[str]:
    """Lane prefixes that ACTUALLY exist in the DB (authoritative)."""
    try:
        c = sqlite3.connect(DB, timeout=20)
        rows = c.execute("SELECT DISTINCT substr(id,1,instr(id,':')-1) FROM lanes").fetchall()
        c.close()
        return [r[0] for r in rows]
    except Exception:
        return all_prefixes()
