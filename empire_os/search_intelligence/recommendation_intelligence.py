"""Observed organic + AI recommendation visibility analysis.

This module measures only captured answer evidence. It does not infer hidden
model preferences, guarantee recommendations, or turn a recommendation
observation into commercial/revenue truth.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Iterable
from urllib.parse import urlparse


def _domain(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "://" in text:
        text = urlparse(text).hostname or ""
    return text.removeprefix("www.").strip(".")


@dataclass(frozen=True)
class AiAnswerObservation:
    """One captured answer from an AI/search answer surface."""

    query: str
    engine: str
    observed_at: str
    provenance: tuple[str, ...]
    answer_ref: str | None = None
    cited_urls: tuple[str, ...] = ()
    mentioned_domains: tuple[str, ...] = ()
    recommended_domains: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.query.strip():
            raise ValueError("query required")
        if not self.engine.strip():
            raise ValueError("engine required")
        if not self.observed_at.strip():
            raise ValueError("observed_at required")
        if not self.provenance:
            raise ValueError("answer observation requires provenance")
        for url in self.cited_urls:
            parsed = urlparse(str(url or "").strip())
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("cited_urls must contain absolute http(s) URLs")
        for value in (*self.mentioned_domains, *self.recommended_domains):
            if not _domain(value):
                raise ValueError("observed domains must be non-empty")

    @property
    def cited_domains(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                domain
                for domain in (_domain(url) for url in self.cited_urls)
                if domain
            )
        )

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class RecommendationVisibilityAnalysis:
    available: bool
    observed_answers: int
    observed_queries: int
    observed_engines: tuple[str, ...]
    brand_answer_presence_count: int
    brand_answer_presence_rate: float | None
    brand_citation_count: int
    brand_citation_rate: float | None
    brand_recommendation_count: int
    brand_recommendation_rate: float | None
    monitored_recommendation_mentions: int
    share_of_observed_recommendations: float | None
    competitor_recommendation_counts: dict[str, int]
    competitor_recommended_domains: tuple[str, ...]
    citation_source_domains: tuple[str, ...]
    recommendation_gap_queries: tuple[str, ...]
    evidence_count: int
    reason: str | None = None
    market_share_claimed: bool = False
    recommendation_guaranteed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyse_recommendation_visibility(
    observations: Iterable[AiAnswerObservation],
    *,
    brand_domains: tuple[str, ...],
    competitor_domains: tuple[str, ...] = (),
    engine: str | None = None,
) -> RecommendationVisibilityAnalysis:
    """Summarize observed answer/citation/recommendation presence.

    share_of_observed_recommendations is deliberately scoped to recommendation
    mentions among the monitored brand + competitor domains in captured answers.
    It is not market share and must not be presented as such.
    """
    brand = {_domain(value) for value in brand_domains if _domain(value)}
    competitors = {
        _domain(value) for value in competitor_domains if _domain(value)
    }
    competitors -= brand
    if not brand:
        raise ValueError("at least one brand domain required")

    rows = tuple(observations)
    for row in rows:
        row.validate()

    selected = tuple(
        row for row in rows
        if engine is None or row.engine == engine
    )
    if not selected:
        return RecommendationVisibilityAnalysis(
            available=False,
            observed_answers=0,
            observed_queries=0,
            observed_engines=(),
            brand_answer_presence_count=0,
            brand_answer_presence_rate=None,
            brand_citation_count=0,
            brand_citation_rate=None,
            brand_recommendation_count=0,
            brand_recommendation_rate=None,
            monitored_recommendation_mentions=0,
            share_of_observed_recommendations=None,
            competitor_recommendation_counts={},
            competitor_recommended_domains=(),
            citation_source_domains=(),
            recommendation_gap_queries=(),
            evidence_count=0,
            reason="no_observed_ai_answer_evidence",
        )

    brand_presence = 0
    brand_citations = 0
    brand_recommendations = 0
    monitored_recommendations = 0
    competitor_counts: Counter[str] = Counter()
    source_domains: set[str] = set()
    gap_queries: set[str] = set()

    for row in selected:
        cited = set(row.cited_domains)
        mentioned = {_domain(value) for value in row.mentioned_domains}
        recommended = {_domain(value) for value in row.recommended_domains}
        mentioned.discard("")
        recommended.discard("")
        source_domains.update(cited)

        brand_cited = bool(cited & brand)
        brand_mentioned = bool(mentioned & brand)
        brand_recommended = bool(recommended & brand)
        competitor_recommended = sorted(recommended & competitors)

        if brand_cited or brand_mentioned or brand_recommended:
            brand_presence += 1
        if brand_cited:
            brand_citations += 1
        if brand_recommended:
            brand_recommendations += 1

        brand_rec_hits = len(recommended & brand)
        competitor_rec_hits = len(recommended & competitors)
        monitored_recommendations += brand_rec_hits + competitor_rec_hits

        for domain in competitor_recommended:
            competitor_counts[domain] += 1

        if competitor_recommended and not brand_recommended:
            gap_queries.add(row.query)

    total = len(selected)
    return RecommendationVisibilityAnalysis(
        available=True,
        observed_answers=total,
        observed_queries=len({row.query for row in selected}),
        observed_engines=tuple(sorted({row.engine for row in selected})),
        brand_answer_presence_count=brand_presence,
        brand_answer_presence_rate=round(brand_presence / total, 4),
        brand_citation_count=brand_citations,
        brand_citation_rate=round(brand_citations / total, 4),
        brand_recommendation_count=brand_recommendations,
        brand_recommendation_rate=round(brand_recommendations / total, 4),
        monitored_recommendation_mentions=monitored_recommendations,
        share_of_observed_recommendations=(
            round(brand_recommendations / monitored_recommendations, 4)
            if monitored_recommendations
            else None
        ),
        competitor_recommendation_counts=dict(
            sorted(competitor_counts.items())
        ),
        competitor_recommended_domains=tuple(sorted(competitor_counts)),
        citation_source_domains=tuple(sorted(source_domains)),
        recommendation_gap_queries=tuple(sorted(gap_queries)),
        evidence_count=sum(len(row.provenance) for row in selected),
    )
