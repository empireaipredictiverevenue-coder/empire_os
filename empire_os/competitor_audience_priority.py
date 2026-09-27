"""Evidence-only stacking for competitor audience intelligence.

This layer prioritizes research from observed public evidence. It never changes
factual buyer state, never creates commercial intent, and never authorizes
outreach. Scores are recommendation-only overlays for Founder/Omega/Cortex
consumption.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def _bounded(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(number, 1.0))


def score_competitor_audience_company(
    company: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = [
        item
        for item in (company.get("evidence") or [])
        if isinstance(item, Mapping)
    ]

    unique_sources = {
        str(item.get("source_ref") or "").strip()
        for item in evidence
        if str(item.get("source_ref") or "").strip()
    }
    unique_competitors = {
        str(item.get("competitor_key") or "").strip()
        for item in evidence
        if str(item.get("competitor_key") or "").strip()
    }
    evidence_types = {
        str(item.get("evidence_type") or "").strip()
        for item in evidence
        if str(item.get("evidence_type") or "").strip()
    }

    confidences = [
        _bounded(item.get("confidence"))
        for item in evidence
        if item.get("confidence") is not None
    ]

    evidence_depth = min(len(evidence) / 3.0, 1.0)
    source_diversity = min(len(unique_sources) / 3.0, 1.0)
    competitor_diversity = min(len(unique_competitors) / 2.0, 1.0)
    evidence_type_diversity = min(len(evidence_types) / 3.0, 1.0)
    confidence = (
        sum(confidences) / len(confidences)
        if confidences
        else 0.0
    )

    score = (
        evidence_depth * 0.35
        + source_diversity * 0.25
        + competitor_diversity * 0.15
        + evidence_type_diversity * 0.10
        + confidence * 0.15
    )

    if len(evidence) >= 3 and len(unique_sources) >= 3:
        stack_state = "STACKED"
    elif len(evidence) >= 2:
        stack_state = "MULTI_EVIDENCE"
    elif len(evidence) == 1:
        stack_state = "SINGLE_EVIDENCE"
    else:
        stack_state = "NO_EVIDENCE"

    return {
        "schema_version": "empire.competitor_audience_priority.v1",
        "entity_id": str(company.get("entity_id") or "").strip(),
        "company_name": str(company.get("company_name") or "").strip(),
        "research_priority_score": round(score * 100.0, 2),
        "stack_state": stack_state,
        "evidence_count": len(evidence),
        "source_count": len(unique_sources),
        "competitor_count": len(unique_competitors),
        "evidence_type_count": len(evidence_types),
        "confidence": round(confidence, 6),
        "dimensions": {
            "evidence_depth": round(evidence_depth, 6),
            "source_diversity": round(source_diversity, 6),
            "competitor_diversity": round(competitor_diversity, 6),
            "evidence_type_diversity": round(
                evidence_type_diversity,
                6,
            ),
            "confidence": round(confidence, 6),
        },
        "recommendation_only": True,
        "research_candidate": len(evidence) > 0,
        "buyer_intent": False,
        "commercial_intent": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def rank_competitor_audience_companies(
    companies: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        score_competitor_audience_company(company)
        for company in companies
        if isinstance(company, Mapping)
    ]
    rows.sort(
        key=lambda row: (
            row["research_priority_score"],
            row["evidence_count"],
            row["company_name"].casefold(),
        ),
        reverse=True,
    )
    for index, row in enumerate(rows, 1):
        row["research_priority_rank"] = index
    return rows
