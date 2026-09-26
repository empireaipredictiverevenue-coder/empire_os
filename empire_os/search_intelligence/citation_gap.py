"""Observed competitor citation-gap analysis for Search Intelligence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.search_intelligence.ai_visibility import (
    AiCitationObservation,
)


@dataclass(frozen=True)
class CitationGapAnalysis:
    query: str
    engine: str
    available: bool
    empire_cited: bool | None
    competitor_cited_domains: tuple[str, ...]
    citation_gap_observed: bool | None
    evidence_count: int
    reason: str | None = None
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(domain: str) -> str:
    return str(domain or "").strip().lower().removeprefix("www.")


def analyse_citation_gap(
    observations: tuple[AiCitationObservation, ...],
    *,
    query: str,
    engine: str,
    empire_domains: tuple[str, ...],
    competitor_domains: tuple[str, ...],
) -> CitationGapAnalysis:
    empire = {_norm(item) for item in empire_domains if _norm(item)}
    competitors = {
        _norm(item) for item in competitor_domains if _norm(item)
    }
    if not empire:
        raise ValueError("at least one Empire domain required")
    if not competitors:
        raise ValueError("at least one competitor domain required")

    for observation in observations:
        observation.validate()
    matching = tuple(
        item
        for item in observations
        if item.query == query and item.engine == engine
    )
    if not matching:
        return CitationGapAnalysis(
            query=query,
            engine=engine,
            available=False,
            empire_cited=None,
            competitor_cited_domains=(),
            citation_gap_observed=None,
            evidence_count=0,
            reason="no_observed_ai_citation_evidence",
        )

    cited = {
        _norm(item.cited_domain)
        for item in matching
        if _norm(item.cited_domain)
    }
    empire_cited = bool(cited & empire)
    competitor_hits = tuple(sorted(cited & competitors))
    gap = bool(competitor_hits) and not empire_cited
    return CitationGapAnalysis(
        query=query,
        engine=engine,
        available=True,
        empire_cited=empire_cited,
        competitor_cited_domains=competitor_hits,
        citation_gap_observed=gap,
        evidence_count=sum(len(item.provenance) for item in matching),
    )
