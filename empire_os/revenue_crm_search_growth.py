"""Bridge canonical Revenue CRM context into Search Intelligence products.

Evidence-only: backlink, mention/citation and authority observations become
account-level growth opportunities. No link placement, publishing, outreach,
pricing, revenue or CRM mutation occurs here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.search_intelligence.ai_visibility import (
    AiCitationObservation,
    AiVisibilityAnalysis,
    analyse_ai_visibility,
)
from empire_os.search_intelligence.backlinks import (
    BacklinkGraphAnalysis,
    BacklinkObservation,
    analyse_backlink_graph,
)
from empire_os.search_intelligence.citation_gap import (
    CitationGapAnalysis,
    analyse_citation_gap,
)


@dataclass(frozen=True)
class CrmSearchGrowthBrief:
    prospect_id: str
    domain: str
    query: str
    engine: str
    backlink_analysis: BacklinkGraphAnalysis
    ai_visibility: AiVisibilityAnalysis
    citation_gap: CitationGapAnalysis | None
    opportunities: tuple[str, ...]
    evidence_count: int
    execution_authority: str = "none"
    crm_mutation: bool = False
    publishing_execution: bool = False
    link_building_execution: bool = False
    outreach_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["backlink_analysis"] = self.backlink_analysis.as_dict()
        data["ai_visibility"] = self.ai_visibility.as_dict()
        data["citation_gap"] = (
            self.citation_gap.as_dict()
            if self.citation_gap is not None
            else None
        )
        return data


def build_crm_search_growth_brief(
    *,
    prospect_id: str,
    domain: str,
    query: str,
    engine: str,
    backlinks: tuple[BacklinkObservation, ...],
    citations: tuple[AiCitationObservation, ...],
    competitor_domains: tuple[str, ...] = (),
) -> CrmSearchGrowthBrief:
    pid = str(prospect_id or "").strip()
    normalized_domain = (
        str(domain or "")
        .strip()
        .lower()
        .removeprefix("https://")
        .removeprefix("http://")
        .split("/", 1)[0]
        .removeprefix("www.")
    )
    if not pid:
        raise ValueError("prospect_id required")
    if not normalized_domain or "." not in normalized_domain:
        raise ValueError("valid domain required")
    if not str(query or "").strip():
        raise ValueError("query required")
    if not str(engine or "").strip():
        raise ValueError("engine required")

    empire_domains = (normalized_domain,)
    backlink_analysis = analyse_backlink_graph(
        backlinks,
        empire_domains=empire_domains,
    )
    visibility = analyse_ai_visibility(
        citations,
        empire_domains=empire_domains,
        query=query,
        engine=engine,
    )
    gap = None
    if competitor_domains:
        gap = analyse_citation_gap(
            citations,
            query=query,
            engine=engine,
            empire_domains=empire_domains,
            competitor_domains=competitor_domains,
        )

    opportunities: list[str] = []
    if not backlink_analysis.available:
        opportunities.append("establish_backlink_baseline")
    elif backlink_analysis.referring_domains < 3:
        opportunities.append("authority_gap_research")

    if visibility.available and visibility.empire_cited is False:
        opportunities.append("ai_mention_and_citation_gap")
    elif not visibility.available:
        opportunities.append("collect_ai_visibility_evidence")

    if gap is not None and gap.citation_gap_observed is True:
        opportunities.append("competitor_citation_gap")

    evidence_count = (
        backlink_analysis.evidence_count
        + visibility.evidence_count
        + (gap.evidence_count if gap is not None else 0)
    )

    return CrmSearchGrowthBrief(
        prospect_id=pid,
        domain=normalized_domain,
        query=str(query).strip(),
        engine=str(engine).strip(),
        backlink_analysis=backlink_analysis,
        ai_visibility=visibility,
        citation_gap=gap,
        opportunities=tuple(dict.fromkeys(opportunities)),
        evidence_count=evidence_count,
    )
