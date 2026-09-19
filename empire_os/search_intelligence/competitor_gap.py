"""Evidence-backed competitor gap analysis from observed SERP snapshots."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlsplit
from typing import Any, Iterable

from .serp import SerpSnapshot


def _domain(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    host = (urlsplit(text).hostname or "").strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


@dataclass(frozen=True)
class CompetitorDomainEvidence:
    domain: str
    result_count: int
    best_position: int
    observed_positions: tuple[int, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CompetitorGapAnalysis:
    query: str
    observed_at: str
    engine: str
    available: bool
    observed_result_count: int
    empire_result_count: int
    competitor_result_count: int
    empire_best_position: int | None
    current_empire_coverage: float | None
    competitor_presence: float | None
    content_gap: float | None
    competitor_domains: tuple[CompetitorDomainEvidence, ...]
    provenance: tuple[str, ...]
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["competitor_domains"] = [
            item.as_dict() for item in self.competitor_domains
        ]
        return data

    def opportunity_inputs(self) -> dict[str, float | None]:
        """Return only observed factors safe to project onto SearchOpportunity."""
        return {
            "competitor_presence": self.competitor_presence,
            "current_empire_coverage": self.current_empire_coverage,
            "content_gap": self.content_gap,
        }


def analyse_competitor_gap(
    snapshot: SerpSnapshot,
    *,
    empire_domains: Iterable[str],
) -> CompetitorGapAnalysis:
    canonical_empire_domains = {
        domain
        for raw in empire_domains
        if (domain := _domain(raw))
    }
    if not canonical_empire_domains:
        raise ValueError("at least one Empire domain is required")

    provenance = (
        "serp_snapshot",
        f"engine:{snapshot.engine}",
        f"observed_at:{snapshot.observed_at}",
    )

    if not snapshot.available or not snapshot.results:
        return CompetitorGapAnalysis(
            query=snapshot.query,
            observed_at=snapshot.observed_at,
            engine=snapshot.engine,
            available=False,
            observed_result_count=0,
            empire_result_count=0,
            competitor_result_count=0,
            empire_best_position=None,
            current_empire_coverage=None,
            competitor_presence=None,
            content_gap=None,
            competitor_domains=(),
            provenance=provenance,
            reason=snapshot.error or "serp_evidence_unavailable",
        )

    empire_positions: list[int] = []
    competitor_positions: dict[str, list[int]] = {}

    for result in snapshot.results:
        domain = _domain(result.url)
        if not domain:
            continue
        if domain in canonical_empire_domains:
            empire_positions.append(result.position)
            continue
        competitor_positions.setdefault(domain, []).append(
            result.position
        )

    observed = len(snapshot.results)
    empire_count = len(empire_positions)
    competitor_count = sum(
        len(positions)
        for positions in competitor_positions.values()
    )

    coverage = round(empire_count / observed, 4)
    competitor_presence = round(competitor_count / observed, 4)
    content_gap = round(max(0.0, 1.0 - coverage), 4)

    competitor_domains = tuple(
        CompetitorDomainEvidence(
            domain=domain,
            result_count=len(positions),
            best_position=min(positions),
            observed_positions=tuple(sorted(positions)),
        )
        for domain, positions in sorted(
            competitor_positions.items(),
            key=lambda item: (
                min(item[1]),
                item[0],
            ),
        )
    )

    return CompetitorGapAnalysis(
        query=snapshot.query,
        observed_at=snapshot.observed_at,
        engine=snapshot.engine,
        available=True,
        observed_result_count=observed,
        empire_result_count=empire_count,
        competitor_result_count=competitor_count,
        empire_best_position=(
            min(empire_positions)
            if empire_positions
            else None
        ),
        current_empire_coverage=coverage,
        competitor_presence=competitor_presence,
        content_gap=content_gap,
        competitor_domains=competitor_domains,
        provenance=provenance,
    )
