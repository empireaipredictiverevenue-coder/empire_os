#!/usr/bin/env python3
"""
chicago_permits.py — Chicago Building Permits (free, public).

Socrata endpoint:
  https://data.cityofnewyork.us-style — for Chicago it's the City of Chicago
  Data Portal. Permits are issued by the Department of Buildings.

We pull building permits issued in the last 14 days for residential +
small commercial work — exactly the buyer intent Empire OS cares about.

Tier: real (no key required)
"""
import time
from datetime import date, timedelta
from typing import Iterator, Optional

import requests

from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche


# Chicago Data Portal — building permits
ENDPOINT = "https://data.cityofchicago.org/resource/ydr8-5enu.json"

# Permit type → niche hint (Chicago uses a permit_type code)
PERMIT_NICHE = {
    "PERMIT - NEW CONSTRUCTION":      "general_contractor",
    "PERMIT - RENOVATION/ALTERATION": "general_contractor",
    "PERMIT - WRECKING/DEMOLITION":   "general_contractor",
    "PERMIT - REPAIR":                "general_contractor",
    "PERMIT - ELECTRICAL":            "electrical",
    "PERMIT - PLUMBING":              "plumbing",
    "PERMIT - SCAFFOLD":              "general_contractor",
    "PERMIT - ELEVATOR":              "general_contractor",
    "PERMIT - SIG":                   "general_contractor",
}


def _infer_niche(work_description: str, permit_type: Optional[str]) -> str:
    if permit_type and permit_type in PERMIT_NICHE:
        return PERMIT_NICHE[permit_type]
    return infer_niche(work_description or "")


def run(metro: str = None, verticals: list = None, limit: int = 40) -> Iterator[LeadCandidate]:
    """Yield LeadCandidates from the Chicago permits dataset.

    Filters to issued (vs proposed) and within the last 14 days.
    """
    if metro and metro.upper() != "CHI":
        return  # only serves Chicago
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    params = {
        "$where": f"issue_date>='{cutoff}'",
        "$limit": str(min(limit, 100)),
    }
    try:
        r = requests.get(ENDPOINT, params=params, timeout=25)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        return
    for row in rows:
        try:
            pin = row.get("permit_") or row.get("permit_num") or ""
            desc = row.get("work_description") or row.get("permit_type") or ""
            addr = row.get("street_number", "") + " " + row.get("street_direction", "") + \
                   " " + row.get("street_name", "") + " " + row.get("suffix", "")
            addr = " ".join(addr.split()).strip()
            issue = row.get("issue_date", "")[:10]
            ptype = row.get("permit_type") or ""
            yield LeadCandidate(
                name=f"CHI Permit {pin}".strip() if pin else f"CHI Permit {addr}",
                email="",
                phone="",
                metro="CHI",
                state="IL",
                niche=_infer_niche(desc, ptype),
                details=f"{desc[:200]} - permit #{pin} issued {issue}".strip(),
                source=f"chicago_permits:{pin}",
                lead_score=72 if pin else 50,
                url=f"https://data.cityofchicago.org/d/ydr8-5enu",
            )
        except Exception:
            continue


SOURCE = SourceInfo(
    name="chicago_permits",
    tier="real",
    requires=[],
    description="Chicago building permits (issued) — public, free.",
    run_fn=run,
)


def register_source(reg=None):
    if reg is not None:
        reg(SOURCE)


if __name__ == "__main__":
    for lead in run(limit=10):
        print(lead.name, lead.details[:80])
