"""Official public-license identity seeds for evidence recovery.

These records are not buyer-authority claims. They provide named professionals
associated with a company so first-party evidence can be searched more precisely.
"""
from __future__ import annotations

import csv
import io
import re
import time
import urllib.request
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Any

TEXAS_RMP_CSV = "https://tsbpe.texas.gov/download-csv/RMP/"
TEXAS_RMP_SOURCE = "https://tsbpe.texas.gov/free-licensee-list/"
_CACHE_TTL_SECONDS = 6 * 60 * 60
_cache: tuple[float, str] | None = None


@dataclass(frozen=True)
class LicensePrincipalSeed:
    company_name: str
    person_name: str
    role: str
    state: str
    source: str
    source_url: str
    confidence: float
    license_status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_company(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    tokens = [
        token for token in text.split()
        if token not in {
            "llc", "ltd", "inc", "incorporated", "corp", "corporation",
            "company", "co", "pllc", "lp", "llp",
        }
    ]
    return " ".join(tokens)


def _company_match_score(left: str, right: str) -> float:
    a = _normalise_company(left)
    b = _normalise_company(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    at, bt = set(a.split()), set(b.split())
    shorter_tokens, longer_tokens = (
        (at, bt) if len(at) <= len(bt) else (bt, at)
    )
    if (
        len(shorter_tokens) >= 2
        and shorter_tokens <= longer_tokens
    ):
        return 0.96
    overlap = len(at & bt) / max(1, min(len(at), len(bt)))
    seq = SequenceMatcher(None, a, b).ratio()
    if overlap == 1.0 and min(len(at), len(bt)) >= 2:
        return max(0.94, seq)
    return max(seq, overlap * 0.92)


def _fetch_texas_rmp_csv(timeout: float = 12.0) -> str:
    global _cache
    now = time.time()
    if _cache and now - _cache[0] < _CACHE_TTL_SECONDS:
        return _cache[1]
    req = urllib.request.Request(
        TEXAS_RMP_CSV,
        headers={"User-Agent": "Mozilla/5.0 EmpireOS/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8-sig", errors="replace")
    _cache = (now, text)
    return text



def texas_rmp_seeds_from_csv(
    company_name: str,
    csv_text: str,
    *,
    minimum_match: float = 0.90,
) -> list[LicensePrincipalSeed]:
    rows: list[LicensePrincipalSeed] = []
    for raw in csv.DictReader(io.StringIO(csv_text or "")):
        if str(raw.get("LIC_STATUS") or "").strip().lower() != "current":
            continue
        listed_company = str(raw.get("PLUMB_COMPANY") or "").strip()
        score = _company_match_score(company_name, listed_company)
        if score < minimum_match:
            continue
        first = str(raw.get("FIRST_NAME") or "").strip().title()
        middle = str(raw.get("MIDDLE_NAME") or "").strip().title()
        last = str(raw.get("LAST_NAME") or "").strip().title()
        suffix = str(raw.get("SUFFIX") or "").strip()
        name = " ".join(x for x in (first, middle, last, suffix) if x)
        if not first or not last:
            continue
        rows.append(LicensePrincipalSeed(
            company_name=listed_company,
            person_name=name,
            role="Responsible Master Plumber",
            state="TX",
            source="texas_tsbpe_rmp",
            source_url=TEXAS_RMP_SOURCE,
            confidence=round(min(0.99, max(0.90, score)), 4),
            license_status="current",
        ))
    rows.sort(key=lambda row: (-row.confidence, row.person_name.casefold()))
    return rows[:3]


def find_official_license_principals(
    *,
    company_name: str,
    state: str,
    timeout: float = 12.0,
) -> list[dict[str, Any]]:
    state = str(state or "").strip().upper()
    if state != "TX" or not str(company_name or "").strip():
        return []
    try:
        text = _fetch_texas_rmp_csv(timeout=timeout)
    except Exception:
        return []
    return [
        row.as_dict()
        for row in texas_rmp_seeds_from_csv(company_name, text)
    ]
