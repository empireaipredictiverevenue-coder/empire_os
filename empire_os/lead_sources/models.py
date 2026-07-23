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
        }
        return {k: v for k, v in d.items() if v}

@dataclass
class SourceInfo:
    name: str
    tier: str
    requires: list
    description: str
    run_fn: object = None