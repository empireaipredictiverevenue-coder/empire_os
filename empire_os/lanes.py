"""Lane configuration — 42 niches across 7 categories.

Total: 7 categories × 6 sub-niches × 11 metros = 462 lane slots.

Lane occupancy: firms buy seats in specific sub-niche × metro combos.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("lanes")

# ── Geography: Top 11 US Metros ──────────────────────────────────────

METROS = {
    "NYC": "New York City Metro (NY-NJ-CT)",
    "LAX": "Los Angeles Metro (CA)",
    "CHI": "Chicago Metro (IL-IN-WI)",
    "DFW": "Dallas-Fort Worth Metro (TX)",
    "HOU": "Houston Metro (TX)",
    "WDC": "Washington DC Metro (DC-VA-MD-WV)",
    "PHL": "Philadelphia Metro (PA-NJ-DE-MD)",
    "ATL": "Atlanta Metro (GA)",
    "MIA": "Miami-Fort Lauderdale Metro (FL)",
    "BOS": "Boston Metro (MA-NH)",
    "SFO": "San Francisco Bay Area (CA)",
}

# State → preferred metro(s) mapping for routing
STATE_METRO = {
    "NY": ("NYC",), "NJ": ("NYC", "PHL"), "CT": ("NYC", "BOS"),
    "CA": ("LAX", "SFO"),
    "IL": ("CHI",), "IN": ("CHI",), "WI": ("CHI",),
    "TX": ("DFW", "HOU"),
    "DC": ("WDC",), "VA": ("WDC",), "MD": ("WDC",), "WV": ("WDC",),
    "PA": ("PHL",), "DE": ("PHL",),
    "GA": ("ATL",),
    "FL": ("MIA", "ATL"),
    "MA": ("BOS",), "NH": ("BOS",),
    # Fallback
    "AL": ("ATL",), "TN": ("ATL",), "SC": ("ATL",), "NC": ("ATL", "WDC"),
    "OH": ("CHI", "PHL"), "MI": ("CHI",), "KY": ("ATL", "CHI"),
    "MO": ("CHI",), "MN": ("CHI",), "IA": ("CHI",),
    "CO": ("DFW",), "NM": ("DFW", "HOU"), "OK": ("DFW",),
    "AZ": ("LAX",), "NV": ("LAX",), "OR": ("LAX",), "WA": ("LAX",),
    "AR": ("HOU",), "LA": ("HOU",),
    "NE": ("CHI",), "KS": ("CHI",),
    "UT": ("LAX",), "ID": ("LAX",),
    "AK": ("LAX",), "HI": ("LAX",),
    "ME": ("BOS",), "VT": ("BOS",), "RI": ("BOS",),
    "MS": ("ATL", "HOU"),
    "MT": ("CHI",), "ND": ("CHI",), "SD": ("CHI",),
    "WY": ("DFW",),
}

def state_to_metros(state: str) -> list[str]:
    """Map a US state code to primary metro(s)."""
    return list(STATE_METRO.get(state.upper(), ("DFW",)))  # default to DFW

# ── Categories × Sub-niches ─────────────────────────────────────────

CATEGORIES = {
    "mass_torts": {
        "label": "Mass Torts & Personal Injury",
        "subs": {
            "camp_lejeune": "Camp Lejeune Water Contamination",
            "roundup": "Roundup / Glyphosate Cancer",
            "paraquat": "Paraquat Parkinson's Disease",
            "afff": "AFFF Firefighting Foam Cancer",
            "zantac": "Zantac / Ranitidine Cancer",
            "ozempic": "Ozempic / Mounjaro Stomach Paralysis",
        },
    },
    "home_services": {
        "label": "Home Services",
        "subs": {
            "electrical": "Electrical Services",
            "hvac": "HVAC & Air Conditioning",
            "plumbing": "Plumbing Services",
            "residential_roofing": "Residential Roofing",
            "commercial_roofing": "Commercial Roofing",
            "roof_repair": "Roof Repair & Leak Services",
        },
    },
    "restoration": {
        "label": "Restoration & Remediation",
        "subs": {
            "water_damage": "Water Damage Restoration",
            "fire_damage": "Fire & Smoke Damage Restoration",
            "mold_remediation": "Mold Inspection & Remediation",
            "storm_damage": "Storm & Wind Damage Restoration",
            "sewage_cleanup": "Sewage Backup & Biohazard Cleanup",
            "disaster_restoration": "Large Loss Disaster Restoration",
        },
    },
    "medical_health": {
        "label": "Medical & Health",
        "subs": {
            "weight_loss": "Weight Loss & GLP-1 Programs",
            "hormone_therapy": "Hormone Replacement Therapy",
            "dental": "Dental & Orthodontics",
            "vision": "Vision & Eye Care",
            "pt_rehab": "Physical Therapy & Rehab",
            "addiction": "Addiction Treatment & Recovery",
        },
    },
    "business_services": {
        "label": "Business Services",
        "subs": {
            "marketing": "Marketing & Digital Agency",
            "web_dev": "Web Development & Design",
            "accounting": "Accounting & Bookkeeping",
            "consulting": "Business Consulting",
            "staffing": "Staffing & Recruitment",
            "legal_services": "Legal Services (Non-Tort)",
        },
    },
    "financial": {
        "label": "Financial Services",
        "subs": {
            "real_estate": "Real Estate Agents & Brokers",
            "mortgage": "Mortgage & Home Loans",
            "insurance": "Insurance Agents & Brokers",
            "investing": "Investment & Wealth Management",
            "debt_relief": "Debt Relief & Settlement",
            "tax_prep": "Tax Preparation & Planning",
        },
    },
    "technology": {
        "label": "Technology & Software",
        "subs": {
            "managed_it": "Managed IT Services",
            "cybersecurity": "Cybersecurity Services",
            "software_dev": "Software Development",
            "cloud": "Cloud Infrastructure & Migrations",
            "ai_automation": "AI, Automation & Data Science",
            "data_analytics": "Data Analytics & BI",
        },
    },
}


def all_sub_niches() -> list[dict]:
    """Return list of all sub-niches with their category."""
    result = []
    for cat_key, cat in CATEGORIES.items():
        for sub_key, sub_label in cat["subs"].items():
            result.append({
                "category": cat_key,
                "category_label": cat["label"],
                "sub_niche": sub_key,
                "label": sub_label,
            })
    return result


def build_lanes() -> list[dict]:
    """Build the full lane matrix (category:sub × metro)."""
    lanes = []
    idx = 0
    for cat_key, cat in CATEGORIES.items():
        for sub_key, sub_label in cat["subs"].items():
            for metro_id, metro_label in METROS.items():
                lane_id = f"{sub_key}:{metro_id}"
                idx += 1
                lanes.append({
                    "id": lane_id,
                    "lane_number": idx,
                    "category": cat_key,
                    "category_label": cat["label"],
                    "sub_niche": sub_key,
                    "sub_label": sub_label,
                    "metro": metro_id,
                    "metro_label": metro_label,
                })
    return lanes


# ── SQL Schema ──────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS lanes (
    id TEXT PRIMARY KEY,
    lane_number INTEGER,
    category TEXT NOT NULL,
    category_label TEXT,
    sub_niche TEXT NOT NULL,
    sub_label TEXT,
    metro TEXT NOT NULL,
    metro_label TEXT,
    occupied_by TEXT,
    firm_slug TEXT,
    firm_tier TEXT DEFAULT 'standard',
    seat_price REAL DEFAULT 0,
    seat_expires_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lane_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lane_id TEXT NOT NULL,
    prospect_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    omega_score REAL,
    omega_tier TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(lane_id) REFERENCES lanes(id)
);

CREATE INDEX IF NOT EXISTS idx_lane_leads_prospect ON lane_leads(prospect_id);
CREATE INDEX IF NOT EXISTS idx_lane_leads_status ON lane_leads(status);
"""


def ensure_schema(backend) -> None:
    """Create lane tables if they don't exist."""
    for stmt in SCHEMA.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                backend.execute(stmt)
            except Exception:
                pass  # table may already exist
    backend.commit()


def seed_lanes(backend) -> None:
    """Seed the lane matrix into the DB."""
    existing = backend.execute("SELECT COUNT(*) as c FROM lanes").fetchone()
    if existing and existing["c"] > 0:
        logger.info(f"Lanes already seeded ({existing['c']} rows), skipping")
        return

    lanes = build_lanes()
    for lane in lanes:
        backend.execute(
            "INSERT OR IGNORE INTO lanes "
            "(id, lane_number, category, category_label, sub_niche, sub_label, metro, metro_label) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                lane["id"], lane["lane_number"],
                lane["category"], lane["category_label"],
                lane["sub_niche"], lane["sub_label"],
                lane["metro"], lane["metro_label"],
            ),
        )
    backend.commit()
    logger.info(f"Seeded {len(lanes)} lanes")


def create_seat(backend, lane_id: str, firm_name: str, firm_slug: str,
                tier: str = "standard", price: float = 0, expires_in_days: int = 30) -> dict:
    """Assign a firm to a lane (buy a seat)."""
    from datetime import timedelta

    lane = backend.execute("SELECT * FROM lanes WHERE id=?", (lane_id,)).fetchone()
    if not lane:
        return {"ok": False, "error": f"Lane {lane_id} not found"}
    if lane["occupied_by"]:
        return {"ok": False, "error": f"Lane {lane_id} already occupied by {lane['occupied_by']}"}

    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    backend.execute(
        "UPDATE lanes SET occupied_by=?, firm_slug=?, firm_tier=?, seat_price=?, seat_expires_at=?, updated_at=datetime('now') "
        "WHERE id=?",
        (firm_name, firm_slug, tier, price, expires_at.isoformat(), lane_id),
    )
    backend.commit()
    return {
        "ok": True,
        "lane_id": lane_id,
        "firm": firm_name,
        "slug": firm_slug,
        "tier": tier,
        "price": price,
        "expires_at": expires_at.isoformat(),
    }


def release_seat(backend, lane_id: str) -> dict:
    """Release a firm's seat in a lane."""
    lane = backend.execute("SELECT * FROM lanes WHERE id=?", (lane_id,)).fetchone()
    if not lane:
        return {"ok": False, "error": f"Lane {lane_id} not found"}
    if not lane["occupied_by"]:
        return {"ok": False, "error": f"Lane {lane_id} is not occupied"}

    backend.execute(
        "UPDATE lanes SET occupied_by=NULL, firm_slug=NULL, firm_tier='standard', seat_price=0, seat_expires_at=NULL, updated_at=datetime('now') "
        "WHERE id=?",
        (lane_id,),
    )
    backend.commit()
    return {"ok": True, "lane_id": lane_id}
