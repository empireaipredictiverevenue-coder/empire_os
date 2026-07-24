from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche
from empire_os.lead_sources.utils import infer_niche
"""NYC HPD (Housing Preservation & Development) violations — REAL (free).

Tier: real

Socrata endpoint:
  https://data.cityofnewyork.us/resource/wvxf-dwi5.json

HPD violations = landlords must fix within X days or face fines.
Each violation = forced-lead for contractor. This is the highest-
quality NYC lead source because landlords are legally mandated
to remediate.

Categories map directly to our lanes:
  Lead paint → lead_remediation
  Mold → mold_remediation
  No heat/hot water → hvac / plumbing
  Plumbing → plumbing
  Vermin → pest_control
  Window broken → general_contractor
"""

import requests
import time
from datetime import date, timedelta
from typing import Iterator
from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche
from empire_os.lead_sources.utils import infer_niche
from empire_os.lead_sources.utils import infer_niche


URL = "https://data.cityofnewyork.us/resource/wvxf-dwi5.json"

CLASS_NICHE = {
    "Lead-Based Paint": "lead_remediation",
    "Mold": "mold_remediation",
    "No Heat": "hvac",
    "No Hot Water": "plumbing",
    "Plumbing": "plumbing",
    "Vermin": "pest_control",
    "Vermin - Mice/Rats": "pest_control",
    "Vermin - Roaches": "pest_control",
    "Vermin - Bedbugs": "pest_control",
    "Window Guard": "general_contractor",
    "Window/Door - Damaged": "general_contractor",
    "Peeling Paint": "painting",
    "Water Leak": "water_damage_restoration",
    "Flooring": "general_contractor",
    "Ceiling": "general_contractor",
    "Wall": "general_contractor",
    "Heat": "hvac",
    "Hot Water": "plumbing",
    "Appliance - Refrigerator": "general_contractor",
    "Appliance - Oven/Stove": "general_contractor",
}


def run(metro: str = None, verticals: list = None, limit: int = 40) -> Iterator[LeadCandidate]:
    if metro and metro != "NYC":
        return

    end = date.today()
    start = end - timedelta(days=3)

    try:
        r = requests.get(URL, params={
            "$where": f"inspectiondate>='{start}T00:00:00.000'",
            "$limit": 500,
            "$order": "inspectiondate DESC",
        }, timeout=30)
        if r.status_code != 200:
            return
        rows = r.json()
    except Exception:
        return

    for row in rows:
        classification = row.get("violationclass", "") or ""
        description = row.get("violationdescription", "") or row.get("description", "")
        # Try to find niche
        niche = None
        for key, n in CLASS_NICHE.items():
            if key.lower() in description.lower() or key.lower() in classification.lower():
                niche = n
                break
        if not niche:
            continue

        borough = row.get("borough", "").title()
        address = row.get("violationlocation", "") or row.get("violationaddress", "")
        # landlord contact info
        landlord = row.get("landlord", "") or ""

        if not address:
            continue

        score = 85  # HPD = legal mandate, landlords HAVE to fix
        if landlord:
            score += 5

        yield LeadCandidate(
            name=f"HPD Violation {borough}",
            phone="",
            niche=niche,
            metro="NYC",
            state="NY",
            details=(
                f"HPD {classification}: {description}. "
                f"Address: {address}. Landlord: {landlord[:60] or 'unknown'}"
            ),
            source="nyc_hpd",
            lead_score=score,
            url=f"https://a810-biswebportal.nyc.gov/bisweb/PropertyOverviewServlet?boro={borough.lower()}",
            raw=row,
        )
    time.sleep(0.3)


def register_source(reg):
    reg(SourceInfo(
        name="nyc_hpd",
        tier="real",
        requires=[],
        description="NYC HPD housing violations — landlords legally must fix",
        run_fn=run,
    ))
