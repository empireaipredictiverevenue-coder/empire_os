"""Evidence-only AEO/GEO/citation visibility analysis."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlparse
from typing import Any


@dataclass(frozen=True)
class AiCitationObservation:
    query: str
    engine: str
    observed_at: str
    cited_url: str
    source_url: str | None = None
    citation_position: int | None = None
    mention_text: str | None = None
    provenance: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.query.strip() or not self.engine.strip():
            raise ValueError("query and engine are required")
        if not self.observed_at.strip():
            raise ValueError("observed_at required")
        parsed = urlparse(self.cited_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("cited_url must be absolute http(s)")
        if self.citation_position is not None and self.citation_position < 1:
            raise ValueError("citation_position must be positive")
        if not self.provenance:
            raise ValueError("citation observation requires provenance")

    @property
    def cited_domain(self) -> str:
        return (urlparse(self.cited_url).hostname or "").lower()

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class AiVisibilityAnalysis:
    query: str
    engine: str
    available: bool
    observed_citations: int
    empire_citations: int
    empire_cited: bool | None
    empire_positions: tuple[int, ...]
    cited_domains: tuple[str, ...]
    evidence_count: int
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyse_ai_visibility(
    observations: tuple[AiCitationObservation, ...],
    *,
    empire_domains: tuple[str, ...],
    query: str,
    engine: str,
) -> AiVisibilityAnalysis:
    normalized_domains = {
        d.strip().lower().removeprefix("www.")
        for d in empire_domains
        if d.strip()
    }
    if not normalized_domains:
        raise ValueError("at least one Empire domain required")

    for observation in observations:
        observation.validate()

    matching = tuple(
        item
        for item in observations
        if item.query == query and item.engine == engine
    )
    if not matching:
        return AiVisibilityAnalysis(
            query=query,
            engine=engine,
            available=False,
            observed_citations=0,
            empire_citations=0,
            empire_cited=None,
            empire_positions=(),
            cited_domains=(),
            evidence_count=0,
            reason="no_observed_ai_citation_evidence",
        )

    def normalized(domain: str) -> str:
        return domain.removeprefix("www.")

    empire_rows = tuple(
        item
        for item in matching
        if normalized(item.cited_domain) in normalized_domains
    )
    positions = tuple(sorted(
        item.citation_position
        for item in empire_rows
        if item.citation_position is not None
    ))
    domains = tuple(sorted({normalized(item.cited_domain) for item in matching}))
    return AiVisibilityAnalysis(
        query=query,
        engine=engine,
        available=True,
        observed_citations=len(matching),
        empire_citations=len(empire_rows),
        empire_cited=bool(empire_rows),
        empire_positions=positions,
        cited_domains=domains,
        evidence_count=sum(len(item.provenance) for item in matching),
    )
