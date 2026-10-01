from __future__ import annotations

import re
from typing import Any, Mapping


_US_STATE_RE = re.compile(
    r"(?:^|,|\s)(?P<city>[A-Za-z][A-Za-z .'-]{1,60}?),\s*"
    r"(?P<state>AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)"
    r"(?:\s+\d{5}(?:-\d{4})?)?\b",
    re.I,
)


def location_from_addresses(addresses: list[str] | tuple[str, ...]) -> dict[str, Any] | None:
    for raw in addresses:
        text = " ".join(str(raw or "").split())
        match = _US_STATE_RE.search(text)
        if not match:
            continue
        city = " ".join(match.group("city").split()).strip(" ,")
        # Avoid swallowing street fragments before the last comma.
        if "," in city:
            city = city.rsplit(",", 1)[-1].strip()
        if not city or any(ch.isdigit() for ch in city):
            continue
        city_tokens = city.casefold().split()
        street_terms = {
            "street", "st", "avenue", "ave", "road", "rd", "boulevard", "blvd",
            "drive", "dr", "lane", "ln", "highway", "hwy", "suite", "ste",
        }
        if any(token.strip(".,") in street_terms for token in city_tokens):
            continue
        if len(city_tokens) > 4:
            continue
        state = match.group("state").upper()
        return {
            "metro": f"{city}, {state}",
            "city": city,
            "state": state,
            "country_code": "US",
            "evidence_address": text,
            "location_verified": True,
            "location_source": "first_party_site_address",
        }
    return None


def enrich_candidate_location(
    candidate: Mapping[str, Any],
    site_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    row = dict(candidate)
    addresses = [
        str(value)
        for value in (site_evidence.get("addresses") or [])
        if str(value).strip()
    ]
    location = location_from_addresses(addresses)
    row["site_probe_ok"] = site_evidence.get("ok") is True
    row["location_evidence_addresses"] = addresses[:10]
    if location:
        row.update(location)
    else:
        row.update({
            "metro": None,
            "city": None,
            "state": None,
            "country_code": None,
            "evidence_address": None,
            "location_verified": False,
            "location_source": None,
        })
    return row
