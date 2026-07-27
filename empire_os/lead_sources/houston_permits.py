#!/usr/bin/env python3
"""
houston_permits.py — City of Houston Construction Permits.

Houston Permitting Center data on Houston's Open Data Portal.
"""
import time
from datetime import date, timedelta
from typing import Iterator, Optional

import requests

from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche


ENDPOINT = "https://data.houstontx.gov/resource/27ie-2itu.json"

# Houston permit classes map roughly to:
NICHE_HINTS = {
    "Residential":     "residential_roofing",
    "Commercial":      "general_contractor",
    "New":             "general_contractor",
    "Remodel":         "general_contractor",
    "Repair":          "general_contractor",
    "Plumbing":        "plumbing",
    "Electrical":      "electrical",
    "Mechanical (HVAC)": "hvac",
}


def run(metro: str = None, verticals: list = None, limit: int = 40) -> Iterator[LeadCandidate]:
    if metro and metro.upper() != "HOU":
        return
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    params = {
        "$where": f"issued_date>='{cutoff}'",
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
            pn = row.get("permit_no") or row.get("permit_number") or row.get("permit_id") or ""
            addr = row.get("address") or row.get("street_address") or ""
            desc = row.get("description") or row.get("project_description") or ""
            pclass = row.get("permit_class") or ""
            niche = NICHE_HINTS.get(pclass) or infer_niche(desc)
            yield LeadCandidate(
                name=f"HOU Permit {pn}".strip() if pn else f"HOU Permit {addr[:40]}",
                email="",
                phone="",
                metro="HOU",
                state="TX",
                niche=niche,
                details=f"{desc[:200]} - permit #{pn} - {pclass} - issued {row.get('issued_date','')[:10]}".strip(),
                source=f"houston_permits:{pn}",
                lead_score=68 if pn else 48,
                url=f"https://www.houstonpermittingcenter.org",
            )
        except Exception:
            continue


SOURCE = SourceInfo(
    name="houston_permits",
    tier="real",
    requires=[],
    description="Houston construction permits — public, free.",
    run_fn=run,
)


def register_source(reg=None):
    if reg is not None:
        reg(SOURCE)


if __name__ == "__main__":
    for lead in run(limit=10):
        print(lead.name, lead.details[:80])
