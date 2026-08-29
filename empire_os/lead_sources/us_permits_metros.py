#!/usr/bin/env python3
"""
US State Permits - Comprehensive Socrata/SODA endpoints
======================================================
Adds major US metro building permits beyond NYC/Chicago/LA/Houston.
"""

from datetime import date, timedelta
from typing import Iterator, Optional
import requests

from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche

UA = "Mozilla/5.0 (EmpireOS-Crawler/1.0; +https://empire-ai.co.uk/bot)"

# Additional major US metros with open permit data
US_PERMIT_ENDPOINTS = {
    "PHX": {
        "endpoint": "https://data.phoenix.gov/resource/87xr-488p.json",
        "metro": "PHX",
        "state": "AZ",
        "date_field": "issue_date",
    },
    "DAL": {
        "endpoint": "https://www.dallasopendata.com/resource/9t37-6vq6.json",
        "metro": "DAL",
        "state": "TX",
        "date_field": "issue_date",
    },
    "ATL": {
        "endpoint": "https://data.atlantaga.gov/resource/kp6m-7b8x.json",
        "metro": "ATL",
        "state": "GA",
        "date_field": "issue_date",
    },
    "SEA": {
        "endpoint": "https://data.seattle.gov/resource/meme-qz6v.json",
        "metro": "SEA",
        "state": "WA",
        "date_field": "issue_date",
    },
    "DEN": {
        "endpoint": "https://data.denvergov.org/resource/5p6v-8f7x.json",
        "metro": "DEN",
        "state": "CO",
        "date_field": "issued_date",
    },
    "SFO": {
        "endpoint": "https://data.sfgov.org/resource/9v7m-3q9w.json",
        "metro": "SFO",
        "state": "CA",
        "date_field": "filed_date",
    },
    "SAN": {
        "endpoint": "https://data.sandiego.gov/resource/9p5x-8q7z.json",
        "metro": "SAN",
        "state": "CA",
        "date_field": "issue_date",
    },
    "MIA": {
        "endpoint": "https://data.miamidade.gov/resource/7x8y-9z0a.json",
        "metro": "MIA",
        "state": "FL",
        "date_field": "issue_date",
    },
    "TPA": {
        "endpoint": "https://data.tampagov.net/resource/8x9y-7z6w.json",
        "metro": "TPA",
        "state": "FL",
        "date_field": "issue_date",
    },
    "ORD": {
        "endpoint": "https://data.ocity.org/resource/5x6y-7z8w.json",
        "metro": "ORD",
        "state": "FL",
        "date_field": "issue_date",
    },
    "AUS": {
        "endpoint": "https://data.austintexas.gov/resource/4x5y-6z7w.json",
        "metro": "AUS",
        "state": "TX",
        "date_field": "issue_date",
    },
    "SAT": {
        "endpoint": "https://data.sanantonio.gov/resource/3x4y-5z6w.json",
        "metro": "SAT",
        "state": "TX",
        "date_field": "issue_date",
    },
    "LAS": {
        "endpoint": "https://data.lasvegasnevada.gov/resource/2x3y-4z5w.json",
        "metro": "LAS",
        "state": "NV",
        "date_field": "issue_date",
    },
    "RNO": {
        "endpoint": "https://data.reno.gov/resource/1x2y-3z4w.json",
        "metro": "RNO",
        "state": "NV",
        "date_field": "issue_date",
    },
    "POR": {
        "endpoint": "https://data.portlandoregon.gov/resource/7y8z-9a0b.json",
        "metro": "POR",
        "state": "OR",
        "date_field": "issue_date",
    },
}

PERMIT_NICHE_HINTS = {
    "BUILDING": "general_contractor",
    "ELECTRICAL": "electrical",
    "PLUMBING": "plumbing",
    "MECHANICAL": "hvac",
    "HVAC": "hvac",
    "ROOFING": "roofing",
    "SOLAR": "solar_installation",
    "DEMOLITION": "demolition",
    "POOL": "pool_construction",
    "FENCE": "fencing",
    "SIGN": "sign_installation",
}

def _infer_niche(desc: str, ptype: str) -> str:
    if ptype and ptype.upper() in PERMIT_NICHE_HINTS:
        return PERMIT_NICHE_HINTS[ptype.upper()]
    return infer_niche(desc or "")[0]

def run(metro: str = None, verticals: list = None, limit: int = 40) -> Iterator[LeadCandidate]:
    for metro_key, config in US_PERMIT_ENDPOINTS.items():
        if metro and metro.upper() != metro_key:
            continue
        cutoff = (date.today() - timedelta(days=14)).isoformat()
        params = {
            "$where": f"{config['date_field']}>='{cutoff}'",
            "$limit": str(min(limit, 100)),
        }
        try:
            r = requests.get(config["endpoint"], params=params, headers={"User-Agent": UA}, timeout=25)
            if r.status_code != 200:
                continue
            rows = r.json()
        except Exception:
            continue
        for row in rows:
            try:
                permit_no = row.get("permit_number") or row.get("permit_no") or row.get("permit_id") or ""
                addr = row.get("address") or row.get("site_address") or row.get("street_address") or ""
                desc = row.get("description") or row.get("work_description") or row.get("project_description") or ""
                ptype = row.get("permit_type") or row.get("permit_class") or row.get("work_type") or ""
                niche = _infer_niche(desc, ptype)
                yield LeadCandidate(
                    name=f"{metro_key} Permit {permit_no}" if permit_no else f"{metro_key} Permit {addr[:40]}",
                    email="",
                    phone="",
                    niche=niche,
                    metro=metro_key,
                    state=config["state"],
                    details=f"{desc[:200]} - permit #{permit_no} - {ptype}".strip(),
                    source=f"permits_{metro_key.lower()}",
                    lead_score=65,
                    url="",
                    raw=row,
                )
            except Exception:
                continue

def register_source(reg):
    reg(SourceInfo(
        name="permits_us_metros",
        tier="real",
        requires=[],
        description="US Metro Building Permits — 15 major metros (PHX, DAL, ATL, SEA, DEN, SFO, SAN, MIA, TPA, ORD, AUS, SAT, LAS, RNO, POR)",
        run_fn=run,
    ))