from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche
from empire_os.lead_sources.utils import infer_niche
"""CourtListener / RECAP source — REAL (free, 5K calls/day).

Tier: real

CourtListener is the largest free US court database, RECAP project.
Includes:
  - Federal + state court dockets
  - Eviction filings → tenant needs landlord-fix OR move-out-cleaning
  - Foreclosures → property restoration
  - Debt judgments → "settle debt" outreach

API: https://www.courtlistener.com/api/rest/v4/
Auth: free API token (signup), 5K queries/day

For Empire OS: queries recent evictions + property/landlord-tenant
cases in target metros. Each filing = warm lead (someone in legal
distress about their property).

We use the RECAP search API which doesn't always need auth, but the
full search endpoint needs token. Auth token optional — falls back to
public search.
"""

import os
import time
import requests
from datetime import date, timedelta
from typing import Iterator
from pathlib import Path

from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche
from empire_os.lead_sources.utils import infer_niche
from empire_os.lead_sources.utils import infer_niche


COURTLISTENER_URL = "https://www.courtlistener.com/api/rest/v4/search/"


def _read_token() -> str:
    env_path = Path("/root/empire_os/.env")
    try:
        with open(env_path) as f:
            for line in f:
                if line.startswith("COURTLISTENER_TOKEN="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


# Public RECAP search (no auth required for some endpoints)
PUBLIC_RECAP_URLS = [
    "https://www.courtlistener.com/api/rest/v4/recap/",
]


# Target metro counties → CourtListener FIPS (for re-using later)
METRO_FIPS = {
    "NYC": ("36005", "Bronx"),         # Bronx County (NY)
    "LAX": ("06037", "Los Angeles"),
    "CHI": ("17031", "Cook"),
    "DFW": ("48113", "Dallas"),
    "BOS": ("25025", "Suffolk"),
    "WDC": ("11001", "DC"),
    "PHX": ("04013", "Maricopa"),
    "SEA": ("53033", "King"),
    "MIN": ("27053", "Hennepin"),
    "ATL": ("13089", "DeKalb"),
}

CASES = [
    ("landlord tenant", "general_contractor"),
    ("eviction", "general_contractor"),
    ("foreclosure", "water_damage_restoration"),
    ("property damage", "general_contractor"),
    ("home repair", "general_contractor"),
    ("slumlord", "general_contractor"),
    ("habitability", "general_contractor"),
]


def run(metro: str = None, verticals: list = None, limit: int = 40) -> Iterator[LeadCandidate]:
    token = _read_token()
    end = date.today()
    start = end - timedelta(days=7)

    for case_term, niche in CASES:
        try:
            params = {
                "q": case_term,
                "filed_after": start.strftime("%Y-%m-%d"),
                "filed_before": end.strftime("%Y-%m-%d"),
                "type": "d",
            }
            if metro and metro in METRO_FIPS:
                params["court"] = METRO_FIPS[metro][0]

            headers = {}
            if token:
                headers["Authorization"] = f"Token {token}"

            r = requests.get(COURTLISTENER_URL, params=params,
                             headers=headers, timeout=15)
            if r.status_code != 200:
                continue

            data = r.json()
            results = data.get("results", [])
            for row in results[:10]:
                case_name = row.get("caseName", "") or row.get("case_name", "")
                court = row.get("court", "") or row.get("court_id", "")
                filed = row.get("dateFiled", "") or row.get("date_filed", "")
                docket = row.get("docketNumber", "") or row.get("docketNumber", "")
                url = row.get("absolute_url", "")
                if isinstance(url, str) and not url.startswith("http"):
                    url = "https://www.courtlistener.com" + url

                yield LeadCandidate(
                    name=f"{case_name[:60]} ({court})",
                    phone="",
                    niche=niche,
                    metro=metro or "USA",
                    state="",
                    details=f"Court case docket {docket} filed {filed}: {case_term}",
                    source="courtlistener",
                    lead_score=55,
                    url=url if isinstance(url, str) else "",
                    raw=row,
                )
        except Exception:
            continue
        time.sleep(1)


def register_source(reg):
    reg(SourceInfo(
        name="courtlistener",
        tier="real",
        requires=[],  # public search works without token
        description="CourtListener/RECAP — federal+state court dockets (free)",
        run_fn=run,
    ))
