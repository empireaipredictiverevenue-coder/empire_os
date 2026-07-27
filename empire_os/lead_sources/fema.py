#!/usr/bin/env python3
"""
fema.py — FEMA OpenFEMA disaster declarations + disaster-funding events.

When a federal disaster is declared for a county, every metro in that
county gets a 30-180 day window of homeowner demand surge. Surface these
as warm lead signals for restoration / roofing / water-damage niches.

Public API: https://www.fema.gov/api/open
No key required.
"""
import time
from datetime import date, timedelta
from typing import Iterator

import requests

from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche


# FEMA's public disaster declaration dataset
DISASTERS_ENDPOINT = "https://www.fema.gov/api/open/v1/FemaWebDisasterDeclarations"

# Counties we know map to our metros (extend as we add metros)
METRO_TO_COUNTIES = {
    "NYC": [("NEW YORK", "NY")],
    "HOU": [("HARRIS",   "TX")],
    "DFW": [("DALLAS",   "TX"), ("TARRANT", "TX"), ("COLLIN", "TX")],
    "CHI": [("COOK",     "IL")],
    "LAX": [("LOS ANGELES", "CA")],
    "MIA": [("MIAMI-DADE",  "FL")],
    "PHL": [("PHILADELPHIA", "PA")],
    "ATL": [("FULTON",   "GA")],
    "BOS": [("SUFFOLK",  "MA")],
    "SFO": [("SAN FRANCISCO", "CA")],
    "WDC": [("DISTRICT OF COLUMBIA", "DC")],
}

# Disaster incidentType → niche focus
DISASTER_NICHE = {
    "Hurricane":          "water_damage",
    "Flood":              "water_damage",
    "Severe Storm(s)":    "storm_damage",
    "Tornado":            "storm_damage",
    "Fire":               "fire_damage",
    "Wildfire":           "fire_damage",
    "Earthquake":         "general_contractor",
    "Severe Ice Storm":   "general_contractor",
    "Snow":               "residential_roofing",
    "Drought":            "general_contractor",
}


def _to_metro(state: str, county: str) -> str | None:
    state = (state or "").upper()
    county = (county or "").upper()
    for metro, pairs in METRO_TO_COUNTIES.items():
        for c, s in pairs:
            if s.upper() == state and county in c.upper() or c.upper() in county.upper():
                return metro
    return None


def run(metro: str = None, verticals: list = None, limit: int = 40) -> Iterator[LeadCandidate]:
    """Yield LeadCandidates from active FEMA disaster declarations.

    Filters to last 90 days (recent enough to have demand tail).
    """
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    try:
        params = {
            "$filter": f"declarationDate ge datetime'{cutoff}'",
            "$top": min(limit, 100),
        }
        # FEMA uses OData — use $orderby and limit via $top
        r = requests.get(DISASTERS_ENDPOINT, timeout=25, params=params)
        r.raise_for_status()
        rows = r.json()
    except Exception:
        return
    for row in rows:
        try:
            state = row.get("stateCode") or row.get("stateName") or ""
            county = row.get("declaredCountyArea") or row.get("designatedArea") or ""
            title = row.get("declarationTitle") or row.get("declarationNumber") or ""
            inc_type = row.get("incidentType") or row.get("incidentTypeOther") or "Severe Storm(s)"
            metro = _to_metro(state, county) if not metro else metro.upper()
            if metro and not _to_metro(state, county):
                # caller asked for a specific metro but state/county doesn't
                # match — skip
                continue
            niche = DISASTER_NICHE.get(inc_type, "general_contractor")
            # 1 lead per (metro, disaster) — operator dedupes downstream
            yield LeadCandidate(
                name=f"FEMA {title[:60]} ({state}/{county})",
                email="",
                phone="",
                metro=metro or "",
                state=str(state),
                niche=niche,
                details=f"{inc_type} - declared {row.get('declarationDate','')[:10]} - "
                        f"pa-program {row.get('paProgramDeclared','')} - "
                        f"ia-program {row.get('iaProgramDeclared','')}",
                source=f"fema:{row.get('disasterNumber','')}",
                lead_score=80,  # surge demand = hot lead
                url="https://www.fema.gov/disasters",
            )
        except Exception:
            continue


SOURCE = SourceInfo(
    name="fema",
    tier="real",
    requires=[],
    description="FEMA OpenFEMA disaster declarations - public, free.",
    run_fn=run,
)


def register_source(reg=None):
    if reg is not None:
        reg(SOURCE)


if __name__ == "__main__":
    for lead in run(limit=10):
        print(lead.metro, lead.niche, lead.name[:60])
