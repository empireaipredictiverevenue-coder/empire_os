"""UK Companies House identity seeds for buyer-evidence recovery.

Companies House establishes company/officer association. It does not by itself
prove that an officer is the commercial decision maker for an Empire offer.
Returned people are therefore search/reconciliation seeds, never outbound
authority.
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any


API_BASE = "https://api.company-information.service.gov.uk"
SOURCE_BASE = "https://find-and-update.company-information.service.gov.uk/company"


@dataclass(frozen=True)
class CompaniesHousePrincipal:
    company_name: str
    company_number: str
    company_status: str
    person_name: str
    officer_role: str
    occupation: str
    appointed_on: str
    source: str
    source_url: str
    confidence: float
    authoritative_registry: bool = True
    buyer_authority_proven: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_company(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    stop = {
        "limited", "ltd", "plc", "llp", "company", "co",
        "the", "uk", "u k",
    }
    return " ".join(token for token in text.split() if token not in stop)


def company_match_score(left: str, right: str) -> float:
    a = _normalise_company(left)
    b = _normalise_company(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    at, bt = set(a.split()), set(b.split())
    if not at or not bt:
        return 0.0

    overlap = len(at & bt) / max(len(at), len(bt))
    containment = len(at & bt) / max(1, min(len(at), len(bt)))
    sequence = SequenceMatcher(None, a, b).ratio()

    if containment == 1.0 and min(len(at), len(bt)) >= 2:
        return round(max(0.94, sequence), 4)

    return round(max(sequence * 0.85, overlap * 0.9), 4)


def _display_name(value: str) -> str:
    raw = " ".join(str(value or "").split())
    if not raw:
        return ""

    def normalise_part(part: str) -> str:
        value = " ".join(str(part or "").split())
        return value.title() if value.isupper() else value

    if "," not in raw:
        return normalise_part(raw)

    surname, given = [part.strip() for part in raw.split(",", 1)]
    return " ".join(
        part
        for part in (
            normalise_part(given),
            normalise_part(surname),
        )
        if part
    )


def _request_json(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    api_key: str,
    timeout: float = 8.0,
) -> dict[str, Any]:
    query = urllib.parse.urlencode({
        key: str(value)
        for key, value in (params or {}).items()
        if value is not None
    })
    url = API_BASE + path + (("?" + query) if query else "")
    token = base64.b64encode((api_key + ":").encode("ascii")).decode("ascii")
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "Basic " + token,
            "Accept": "application/json",
            "User-Agent": "EmpireOS-CompaniesHouse/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", "replace"))
    return payload if isinstance(payload, dict) else {}


def find_companies_house_principals(
    *,
    company_name: str,
    api_key: str | None = None,
    timeout: float = 8.0,
    minimum_match: float = 0.92,
) -> list[dict[str, Any]]:
    """Return active natural-person officers for one conservatively matched company."""
    name = str(company_name or "").strip()
    key = str(api_key or os.environ.get("COMPANIES_HOUSE_API_KEY") or "").strip()
    if not name or not key:
        return []

    try:
        search = _request_json(
            "/search/companies",
            params={"q": name, "items_per_page": 10},
            api_key=key,
            timeout=timeout,
        )
    except Exception:
        return []

    matches: list[tuple[float, dict[str, Any]]] = []
    for item in search.get("items") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        status = str(item.get("company_status") or "").strip().casefold()
        number = str(item.get("company_number") or "").strip()
        if not title or not number or status not in {"active", "open"}:
            continue
        score = company_match_score(name, title)
        if score >= minimum_match:
            matches.append((score, item))

    matches.sort(key=lambda pair: (-pair[0], str(pair[1].get("company_number") or "")))
    if not matches:
        return []

    # Fail closed when two distinct companies are essentially tied.
    if len(matches) > 1 and abs(matches[0][0] - matches[1][0]) < 0.015:
        return []

    match_score, company = matches[0]
    company_number = str(company.get("company_number") or "").strip()
    company_title = str(company.get("title") or "").strip()
    company_status = str(company.get("company_status") or "").strip()

    try:
        officers = _request_json(
            f"/company/{urllib.parse.quote(company_number)}/officers",
            params={"items_per_page": 100},
            api_key=key,
            timeout=timeout,
        )
    except Exception:
        return []

    rows: list[CompaniesHousePrincipal] = []
    for officer in officers.get("items") or []:
        if not isinstance(officer, dict):
            continue
        if officer.get("resigned_on"):
            continue
        role = str(officer.get("officer_role") or "").strip().casefold()
        if role not in {
            "director",
            "corporate-director",
            "llp-member",
            "designated-member",
        }:
            continue
        raw_name = str(officer.get("name") or "").strip()
        person_name = _display_name(raw_name)
        # Corporate officers are useful company evidence but are not a natural
        # person seed for buyer identity recovery.
        if not person_name or role == "corporate-director":
            continue

        rows.append(CompaniesHousePrincipal(
            company_name=company_title,
            company_number=company_number,
            company_status=company_status,
            person_name=person_name,
            officer_role=role,
            occupation=str(officer.get("occupation") or "").strip(),
            appointed_on=str(officer.get("appointed_on") or "").strip(),
            source="companies_house",
            source_url=f"{SOURCE_BASE}/{company_number}/officers",
            confidence=round(min(0.99, max(0.92, match_score)), 4),
        ))

    rows.sort(key=lambda row: (row.person_name.casefold(), row.appointed_on))
    return [row.as_dict() for row in rows[:8]]
