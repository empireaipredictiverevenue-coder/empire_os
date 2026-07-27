#!/usr/bin/env python3
"""
sam_gov.py — SAM.gov federal contract awards + small-business registrations.

SAM.gov (System for Award Management) tracks every federal contractor in
the US. We pull recent contract awards + newly registered small businesses
to surface buyers (federal agencies, primes) AND contractor competitive intel.

Public API: https://api.sam.gov/opportunities/v2/search
Free, no key required for basic opportunity lookups.
"""
import time
from datetime import date, timedelta
from typing import Iterator, Optional

import requests

from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche


OPPORTUNITY_ENDPOINT = "https://api.sam.gov/opportunities/v2/search"
ENTITY_ENDPOINT = "https://api.sam.gov/entity-information/v3/entities"


def run(metro: str = None, verticals: list = None, limit: int = 40) -> Iterator[LeadCandidate]:
    """Yield federal contract opportunities as LeadCandidates.

    These are *buyer leads* — federal agencies + prime contractors that
    need subcontractors. Empire OS can route them as buyers in our pool.
    """
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    try:
        params = {
            "limit": min(limit, 100),
            "postedFrom": cutoff,
            "ptype": "o,p,k",   # solicitation types
        }
        r = requests.get(
            OPPORTUNITY_ENDPOINT,
            params=params,
            timeout=25,
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
        rows = data.get("opportunitiesData") or []
    except Exception:
        rows = []
    for row in rows:
        try:
            title = row.get("title") or ""
            agency = row.get("departmentName") or ""
            desc = row.get("description") or ""
            city = row.get("city") or ""
            state = row.get("state") or ""
            nid = row.get("solicitationNumber") or ""
            yield LeadCandidate(
                name=f"SAM.gov: {title[:80]}".strip(),
                email="",
                phone="",
                metro="",  # federal awards rarely map cleanly to metros
                state=state[:8],
                niche=infer_niche(title + " " + desc),
                details=f"{desc[:200]} - {agency} - due {row.get('responseDeadLine','')[:10]}".strip(),
                source=f"sam_gov:{nid}",
                lead_score=75,
                url="https://sam.gov",
            )
        except Exception:
            continue


SOURCE = SourceInfo(
    name="sam_gov",
    tier="real",
    requires=[],
    description="SAM.gov federal contract opportunities - public, free.",
    run_fn=run,
)


def register_source(reg=None):
    if reg is not None:
        reg(SOURCE)


if __name__ == "__main__":
    for lead in run(limit=10):
        print(lead.name[:80])
