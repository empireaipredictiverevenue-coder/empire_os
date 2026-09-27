"""OBSERVE-only source scout proposal contract.

A source scout may propose a new public/official source, but cannot register it
as production truth. Promotion requires repository review and an explicit
source contract in source_intelligence.py.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SourceScoutProposal:
    country_code: str
    niche: str
    authority: str
    url: str
    source_type: str
    access_method: str
    freshness_evidence: str
    licence_evidence: str
    fields_observed: tuple[str, ...]
    sample_count: int
    confidence: float
    blockers: tuple[str, ...]
    state: str = "PROPOSED"
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def proposal_ready(value: SourceScoutProposal) -> bool:
    return (
        value.state == "PROPOSED"
        and value.sample_count >= 1
        and value.confidence >= 0.8
        and bool(value.authority.strip())
        and bool(value.url.strip())
        and not value.blockers
    )
