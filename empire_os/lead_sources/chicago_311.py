"""Chicago 311 Service Requests source — REAL (free).

Tier: real (no key required)

Socrata endpoint:
  https://data.cityofchicago.org/resource/v6f7-df3a.json
  https://data.cityofchicago.org/resource/xmx7-a2hh.json (Building Permits)

Most-requested categories map to our lanes:
  Pot Hole in Street → paving (general)
  Sanitation Code Violation → cleanup
  Building Permit → general_contractor
  Rodent Baiting → pest_control
  Graffiti Removal → painting
  Water Leak → plumbing / water_damage_restoration
  Heat Not Working → hvac
  Sewer Trouble → emergency_plumbing
"""
import requests
import time
from datetime import date, timedelta
from typing import Iterator
from empire_os.lead_sources import LeadCandidate, SourceInfo


URL_311 = "https://data.cityofchicago.org/resource/v6f7-df3a.json"
URL_PERMITS = "https://data.cityofchicago.org/resource/ydr8-5uwp.json"

CATEGORY_NICHE = {
    "Water Leak": "plumbing",
    "Sewer Trouble": "emergency_plumbing",
    "Rodent Baiting": "pest_control",
    "Pot Hole in Street": "general_contractor",
    "Graffiti Removal": "painting",
    "Heat Not Working": "hvac",
    "No Heat": "hvac",
    "Air Conditioner Problem": "hvac",
    "Electric": "electrical",
    "Plumbing": "plumbing",
    "Sanitation Code Violation": "disaster_recovery",
    "Abandoned Vehicle Complaint": "general_contractor",
    "Building Permit": "general_contractor",
    "Construction Site Debris": "disaster_recovery",
    "Tree Removal": "landscaping",
    "Tree Trim Request": "landscaping",
    "Tree Planting Request": "landscaping",
    "Pavement Cave-In/Sink Hole": "structural_repair",
}


def run(metro: str = None) -> Iterator[LeadCandidate]:
    if metro and metro != "CHI":
        return

    end = date.today()
    start = end - timedelta(days=1)

    for url, src_name in [(URL_311, "chicago_311"),
                          (URL_PERMITS, "chicago_permits")]:
        try:
            r = requests.get(url, params={
                "$where": f"created_date>='{start}T00:00:00.000'",
                "$limit": 500,
                "$order": "created_date DESC",
            }, timeout=30)
            if r.status_code != 200:
                continue
            rows = r.json()
        except Exception:
            continue

        for row in rows:
            niche = None
            if src_name == "chicago_311":
                sr_type = row.get("sr_type", "")
                for k, v in CATEGORY_NICHE.items():
                    if k.lower() in sr_type.lower():
                        niche = v
                        break
                if not niche:
                    continue
                addr = row.get("street_address", "")
                lat = row.get("latitude", "")
                lon = row.get("longitude", "")
                details = f"311 request {row.get('sr_number', '')}: {sr_type}. Status: {row.get('status', '')}"
            else:  # permits
                desc = (row.get("permit_description", "") or "").lower()
                niche = "general_contractor"
                if "plumb" in desc:
                    niche = "plumbing"
                elif "electric" in desc or "wire" in desc:
                    niche = "electrical"
                elif "hvac" in desc or "heat" in desc or "cool" in desc:
                    niche = "hvac"
                elif "roof" in desc:
                    niche = "roofing"
                elif "renovat" in desc or "alter" in desc or "repair" in desc:
                    niche = "general_contractor"
                addr = row.get("address", "")
                lat, lon = row.get("latitude", ""), row.get("longitude", "")
                details = f"Permit {row.get('permit_', '')}: {row.get('permit_description', '')}"

            if not niche:
                continue

            score = 75  # 311/permits = high-intent, owner must respond
            yield LeadCandidate(
                name=f"Chicago {src_name} #{row.get('sr_number', row.get('permit_', ''))}",
                phone="",
                niche=niche,
                metro="CHI",
                state="IL",
                details=f"{details}. Address: {addr}",
                source=src_name,
                lead_score=score,
                url=f"https://data.cityofchicago.org" if lat else "",
                raw=row,
            )
        time.sleep(0.5)


def register_source(reg):
    reg(SourceInfo(
        name="chicago_311",
        tier="real",
        requires=[],
        description="Chicago 311 + building permits (Socrata, no key)",
        run_fn=run,
    ))
