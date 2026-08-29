#!/usr/bin/env python3
"""
Empire OS v3 — Lead Source Data Models
======================================
Shared data classes for all lead sources.
"""

from dataclasses import dataclass
from typing import Optional, Iterator, List, Any, Callable

@dataclass
class LeadCandidate:
    """A potential lead found by a source. Maps to /v1/leads/direct payload."""
    name: str
    email: str = ""
    phone: str = ""
    niche: str = ""
    metro: str = ""
    state: str = ""
    details: str = ""
    source: str = ""
    lead_score: int = 50
    url: str = ""
    raw: dict = None

    def to_intake_payload(self) -> dict:
        d = {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "niche": self.niche,
            "metro": self.metro,
            "state": self.state,
            "details": self.details,
            "source": self.source,
            "lead_score": self.lead_score,
            "source_url": self.url,
        }
        return {k: v for k, v in d.items() if v}

@dataclass
class SourceInfo:
    name: str
    tier: str
    requires: list
    description: str
    run_fn: object = None
    # Live-probe callable: () -> bool. True iff endpoint returns >=1 real
    # row. Absent (None) => non-network source (admitted without check).
    # This is the verify-gate: a source that cannot prove live data is
    # rejected at registration and can never contribute fabricated leads.
    probe: object = None


import requests as _requests

_UA = {"User-Agent": "Mozilla/5.0 (EmpireOS-Crawler/1.0; +https://empire-ai.co.uk/bot)"}

def http_probe(url: str, params: dict = None, timeout: int = 30) -> bool:
    """Return True iff the Socrata/JSON endpoint returns >=1 real row.

    Used by source `probe` callables in the verify-gate. A 404, empty
    list, non-JSON body, or exception => False (dead/placeholder endpoint).
    """
    if params is None:
        params = {}
    try:
        r = _requests.get(url, params=params, headers=_UA, timeout=timeout)
    except Exception:
        return False
    if r.status_code != 200:
        return False
    try:
        data = r.json()
    except Exception:
        return False
    if isinstance(data, list) and len(data) >= 1:
        return True
    return False