"""County building permits source — REAL (NYC DOB).

Tier: real (no key required)

NYC Open Data SODA endpoint (no auth):
  https://data.cityofnewyork.us/resource/ipu4-2q9a.json

Each permit filing = property owner actively investing in property work
= hottest possible contractor lead. We pull permits filed/issued in
the last 7 days, filter by work_type to our lane niches, and emit a
LeadCandidate per filing.

Refreshes daily via system crawler_runner (every 6h).
"""

import time
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

import requests

from empire_os.lead_sources import LeadCandidate, SourceInfo, infer_niche


# NYC DOB work_type → lane niche
WORK_TYPE_TO_NICHE = {
    "PL": "plumbing",
    "EL": "electrical",
    "MH": "general_contractor",   # Mechanical
    "AL": "general_contractor",   # Alteration
    "EW": "general_contractor",   # Equipment Work
    "BL": "general_contractor",   # Boiler
    "FB": "general_contractor",   # Fuel Burning
    "SD": "general_contractor",   # Standpipe
    "SP": "general_contractor",   # Sprinkler
}

# Job descriptions that signal specific work (override generic MH)
DESCRIPTION_NICHE_HINTS = [
    ("roof", "roofing"),
    ("hvac", "hvac"),
    ("heat", "hvac"),
    ("ac ", "hvac"),
    ("air condition", "hvac"),
    ("plumb", "plumbing"),
    ("drain", "plumbing"),
    ("sewer", "plumbing"),
    ("electric", "electrical"),
    ("wire", "electrical"),
    ("water damage", "water_damage_restoration"),
    ("mold", "mold_remediation"),
    ("asbestos", "asbestos_remediation"),
    ("lead paint", "lead_remediation"),
    ("mason", "carpentry"),
    ("carpent", "carpentry"),
    ("deck", "carpentry"),
    ("cabinet", "carpentry"),
    ("paint", "painting"),
    ("drywall", "general_contractor"),
    ("tile", "general_contractor"),
    ("window", "general_contractor"),
    ("door", "general_contractor"),
    ("bath", "general_contractor"),
    ("kitchen", "general_contractor"),
    ("addition", "general_contractor"),
    ("renovat", "general_contractor"),
    ("excavat", "general_contractor"),
    ("foundation", "structural_repair"),
    ("shoring", "structural_repair"),
    ("sidewalk", "general_contractor"),
    ("demolition", "disaster_recovery"),
    ("fence", "general_contractor"),
]


def _infer_from_description(desc: str) -> str:
    if not desc:
        return "general_contractor"
    d = desc.lower()
    for kw, niche in DESCRIPTION_NICHE_HINTS:
        if kw in d:
            return niche
    return "general_contractor"


URL = "https://data.cityofnewyork.us/resource/ipu4-2q9a.json"


def _run_nyc(lookback_days: int = 7) -> Iterator[LeadCandidate]:
    """Pull permits from last N days, NYC only.

    Uses dobrundate (run date column) since filing_date is text MM/DD/YYYY.
    """
    today = date.today()
    start = today - timedelta(days=lookback_days)
    start_iso = start.strftime("%Y-%m-%dT00:00:00.000")

    seen_jobs = set()
    offset = 0
    while True:
        try:
            r = requests.get(URL, params={
                "$where": f"dobrundate>='{start_iso}'",
                "$limit": 1000,
                "$offset": offset,
                "$order": "dobrundate DESC",
            }, timeout=30)
            if r.status_code != 200:
                return
            rows = r.json()
        except Exception:
            return

        if not rows:
            return

        for row in rows:
            job_no = row.get("job__", "")
            if not job_no or job_no in seen_jobs:
                continue
            seen_jobs.add(job_no)

            work_type = row.get("work_type", "")
            job_type = row.get("job_type", "")
            desc = row.get("job_description", "") or ""

            # Skip non-revenue types
            if job_type == "OT" or row.get("permit_status") == "DISAPPROVED":
                continue

            niche = WORK_TYPE_TO_NICHE.get(work_type)
            if not niche or niche == "general_contractor":
                # try inferring from description
                niche = _infer_from_description(desc)

            owner_biz = (row.get("owner_s_business_name") or "").strip()
            owner_first = (row.get("owner_s_first_name") or "").strip()
            owner_last = (row.get("owner_s_last_name") or "").strip()
            owner_name = owner_biz or f"{owner_first} {owner_last}".strip()

            owner_key = "".join(
                char for char in owner_name.casefold() if char.isalnum()
            )
            placeholder_owner_keys = {
                "",
                "na",
                "none",
                "unknown",
                "notavailable",
                "notapplicable",
                "owner",
                "ownerself",
                "ownerasself",
                "self",
            }
            if owner_key in placeholder_owner_keys or owner_key.isdigit():
                continue

            # IMPORTANT IDENTITY SEMANTICS:
            # NYC DOB labels this contact as the *permittee*, not the property
            # owner. Never attach the permittee phone to the owner prospect.
            permittee_biz = (
                row.get("permittee_s_business_name") or ""
            ).strip()
            permittee_first = (
                row.get("permittee_s_first_name") or ""
            ).strip()
            permittee_last = (
                row.get("permittee_s_last_name") or ""
            ).strip()
            permittee_name = (
                permittee_biz
                or f"{permittee_first} {permittee_last}".strip()
            )
            permittee_phone = (
                row.get("permittee_s_phone__") or ""
            ).strip()
            digits = "".join(c for c in permittee_phone if c.isdigit())
            if len(digits) == 10:
                permittee_phone = (
                    f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                )
            elif len(digits) == 11 and digits.startswith("1"):
                permittee_phone = (
                    f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
                )

            borough = row.get("borough", "").title()
            house = row.get("house__", "")
            street = row.get("street_name", "")
            bbl = row.get("bbl", "")

            # Do not score the owner using a permittee contact field.
            score = 60
            if row.get("residential") == "YES":
                score += 5

            evidence = dict(row)
            evidence["_empire_identity_roles"] = {
                "candidate_name_role": "property_owner",
                "candidate_phone_role": "none",
                "permittee_role": "permittee_contractor_or_professional",
                "permittee_business_name": permittee_biz,
                "permittee_name": permittee_name,
                "permittee_phone": permittee_phone,
            }

            yield LeadCandidate(
                name=f"{owner_name} ({borough})",
                # The dataset does not identify permittee_s_phone__ as an
                # owner phone. Keep owner phone unknown instead of conflating
                # two entities.
                phone="",
                niche=niche,
                metro="NYC",
                state="NY",
                details=(
                    f"{job_type}{'.' + work_type if work_type else ''} permit "
                    f"{job_no} issued {row.get('dobrundate', '')[:10]}: "
                    f"{desc[:160]}. BBL {bbl}. Address: {house} {street}, {borough}. "
                    f"Permittee: {permittee_name or 'unknown'}; "
                    f"permittee phone: {permittee_phone or 'unknown'}"
                ),
                source="permits_nyc",
                lead_score=score,
                url=f"https://a810-biswebportal.nyc.gov/bisweb/PropertyOverflowDetails.jsp?job={job_no}",
                raw=evidence,
            )

        if len(rows) < 1000:
            return
        offset += 1000
        time.sleep(0.3)


def run(metro: str = None) -> Iterator[LeadCandidate]:
    if metro and metro != "NYC":
        return
    yield from _run_nyc()


def register_source(reg):
    reg(SourceInfo(
        name="permits",
        tier="real",
        requires=[],
        description="NYC DOB permit filings (last 7 days) — public SODA, no key",
        run_fn=run,
    ))
