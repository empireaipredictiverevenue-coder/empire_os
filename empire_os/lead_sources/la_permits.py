#!/usr/bin/env python3
"""
la_permits.py — LA Building & Safety Permits (free, public).

LA Open Data portal (CityOfLosAngeles), LADBS dataset, last 14 days.
"""
import time
from datetime import date, timedelta
from typing import Iterator, Optional

import requests

from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche


ENDPOINT = "https://data.lacity.org/resource/pi9x-tg5x.json"

# LA uses PermitType, PermitSubType. Map roughly to our niches.
NICHE_HINTS = {
    "Bldg-New":  "general_contractor",
    "Bldg-Alteration": "general_contractor",
    "Bldg-Addition":  "general_contractor",
    "Bldg-Demolition": "general_contractor",
    "Bldg-Repair":  "general_contractor",
    "Electrical": "electrical",
    "Plumbing":    "plumbing",
    "HVAC":        "hvac",
}


def run(metro: str = None, verticals: list = None, limit: int = 40) -> Iterator[LeadCandidate]:
    if metro and metro.upper() != "LAX":
        return
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    params = {
        "$where": f"issue_date>='{cutoff}'",
        "$limit": str(min(limit, 100)),
    }
    try:
        r = requests.get(ENDPOINT, params=params, timeout=25)
        r.raise_for_status()
        rows = r.json()
    except Exception:
        return
    for row in rows:
        try:
            pn = row.get("permit_nbr", "")
            addr = (row.get("address_start") or "") + " " + (row.get("street_direction") or "") + \
                   " " + (row.get("street_name") or "") + " " + (row.get("street_suffix") or "")
            addr = " ".join(addr.split()).strip()
            desc = row.get("work_description") or ""
            ptype = row.get("permit_type") or ""
            sub = row.get("permit_sub_type") or ""
            niche = NICHE_HINTS.get(ptype) or NICHE_HINTS.get(sub) or infer_niche(desc)
            yield LeadCandidate(
                name=f"LAX Permit {pn}".strip() if pn else f"LAX Permit {addr}",
                email="",
                phone="",
                metro="LAX",
                state="CA",
                niche=niche,
                details=f"{desc[:200]} - permit #{pn} - {ptype} - issued {row.get('issue_date','')[:10]}".strip(),
                source=f"la_permits:{pn}",
                lead_score=70 if pn else 50,
                url=f"https://data.lacity.org",
            )
        except Exception:
            continue


SOURCE = SourceInfo(
    name="la_permits",
    tier="real",
    requires=[],
    description="LA Building & Safety permits — public, free.",
    run_fn=run,
)


def register_source(reg=None):
    if reg is not None:
        reg(SOURCE)


if __name__ == "__main__":
    for lead in run(limit=10):
        print(lead.name, lead.details[:80])
