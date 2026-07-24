from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche
from empire_os.lead_sources.utils import infer_niche
"""NWS Weather Alerts — REAL (free).

Tier: real (no key)

NWS API: https://api.weather.gov/alerts/active
Public, free, no auth (User-Agent header required).

When storm alerts (hurricane warning, tornado watch, severe
thunderstorm, blizzard, flood) hit a region, the zip codes
within that region become leads for restoration contractors
(roofing, mold, water damage restoration, emergency plumbing).

We pull active alerts, extract affected state/county, scan
our lane ownership table for those zips, emit LeadCandidate
for each lane in the affected area.
"""

import requests
import time
from datetime import datetime, timezone
from typing import Iterator
from pathlib import Path

from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche
from empire_os.lead_sources.utils import infer_niche
from empire_os.lead_sources.utils import infer_niche


URL = "https://api.weather.gov/alerts/active"

EVENT_NICHE = {
    "Hurricane": ["roofing", "water_damage_restoration", "emergency_plumbing",
                 "flood_damage", "disaster_recovery"],
    "Tornado": ["roofing", "disaster_recovery", "general_contractor"],
    "Severe Thunderstorm": ["roofing", "general_contractor"],
    "Flood": ["water_damage_restoration", "mold_remediation",
              "emergency_plumbing", "flood_damage"],
    "Flash Flood": ["water_damage_restoration", "emergency_plumbing"],
    "Coastal Flood": ["water_damage_restoration", "general_contractor"],
    "Blizzard": ["roofing", "general_contractor"],
    "Ice Storm": ["general_contractor", "hvac"],
    "Wildfire": ["fire_damage_restoration", "general_contractor",
                "mold_remediation", "structural_repair"],
    "Fire Weather": ["general_contractor", "fire_damage_restoration"],
    "Extreme Heat": ["hvac", "electrical"],
    "Wind": ["roofing", "general_contractor"],
    "Hail": ["roofing", "general_contractor"],
    "Winter Storm": ["roofing", "general_contractor", "hvac"],
}

UA = "(EmpireOS/1.0, contact@empire-ai.co.uk)"


def run(metro: str = None, verticals: list = None, limit: int = 40) -> Iterator[LeadCandidate]:
    try:
        r = requests.get(URL, headers={"User-Agent": UA}, timeout=15)
        if r.status_code != 200:
            return
        data = r.json()
    except Exception:
        return

    features = data.get("features", [])
    for feature in features:
        props = feature.get("properties", {})
        event = props.get("event", "")
        headline = props.get("headline", "")
        area_desc = props.get("areaDesc", "")  # e.g., "Bronx; Kings (Brooklyn); New York"
        state = props.get("senderName", "") or ""
        effective = props.get("effective", "")
        ends = props.get("ends", "")
        severity = props.get("severity", "")

        niches = EVENT_NICHE.get(event)
        if not niches:
            continue

        # Map area desc to our metros
        affects = []
        area_lower = area_desc.lower()
        if "new york" in area_lower or "kings" in area_lower or "queens" in area_lower or "bronx" in area_lower:
            affects.append("NYC")
        if "los angeles" in area_lower:
            affects.append("LAX")
        if "cook" in area_lower or "chicago" in area_lower:
            affects.append("CHI")
        if "dallas" in area_lower or "tarrant" in area_lower:
            affects.append("DFW")
        if "boston" in area_lower or "suffolk" in area_lower:
            affects.append("BOS")
        if "district of columbia" in area_lower or "arlington" in area_lower:
            affects.append("WDC")
        if "maricopa" in area_lower or "phoenix" in area_lower:
            affects.append("PHX")
        if "king" in area_lower and "wa" in area_lower or "seattle" in area_lower:
            affects.append("SEA")
        if "hennepin" in area_lower or "minneapolis" in area_lower:
            affects.append("MIN")
        if "dekalb" in area_lower or "fulton" in area_lower or "atlanta" in area_lower:
            affects.append("ATL")

        if metro and metro not in affects:
            continue

        score = 80 + (10 if severity in ("Extreme", "Severe") else 0)

        for m in (affects or [None]):
            for niche in niches:
                yield LeadCandidate(
                    name=f"Storm Alert {event} ({m or 'regional'})",
                    phone="",
                    niche=niche,
                    metro=m or "",
                    state="",
                    details=(
                        f"NWS alert {event}: {headline}. "
                        f"Affecting {area_desc}. Effective {effective} → {ends}"
                    ),
                    source="nws_alerts",
                    lead_score=score,
                    url=feature.get("id", ""),
                    raw=props,
                )

    time.sleep(0.3)


def register_source(reg):
    reg(SourceInfo(
        name="nws_alerts",
        tier="real",
        requires=[],
        description="NWS active weather alerts — storm-restoration leads by region",
        run_fn=run,
    ))
