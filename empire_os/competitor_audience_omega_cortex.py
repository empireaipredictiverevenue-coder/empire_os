"""Competitor evidence adapter for Omega/Cortex research context.

The adapter deliberately does not write intelligence_scores, mutate buyer
state, create prospects, or authorize outreach. It exposes observed competitive
evidence as bounded model context and internal research recommendations only.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def _bounded(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(number, 1.0))


def _priority_fraction(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(number / 100.0, 1.0))


def _research_action(
    *,
    stack_state: str,
    evidence_count: int,
    source_count: int,
) -> str:
    if stack_state == "STACKED" and evidence_count >= 3 and source_count >= 3:
        return "deep_account_research"
    if stack_state == "MULTI_EVIDENCE":
        return "corroborate_account_evidence"
    if stack_state == "SINGLE_EVIDENCE":
        return "collect_additional_public_evidence"
    return "no_action"


def build_competitor_omega_cortex_context(
    priorities: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build model context without converting evidence into factual intent."""
    rows: list[dict[str, Any]] = []

    for priority in priorities:
        if not isinstance(priority, Mapping):
            continue

        entity_id = str(priority.get("entity_id") or "").strip()
        company_name = str(priority.get("company_name") or "").strip()
        if not entity_id:
            continue

        dimensions = priority.get("dimensions")
        if not isinstance(dimensions, Mapping):
            dimensions = {}

        evidence_count = int(priority.get("evidence_count") or 0)
        source_count = int(priority.get("source_count") or 0)
        competitor_count = int(priority.get("competitor_count") or 0)
        stack_state = str(priority.get("stack_state") or "NO_EVIDENCE")

        features = {
            "research_priority": _priority_fraction(
                priority.get("research_priority_score")
            ),
            "evidence_depth": _bounded(dimensions.get("evidence_depth")),
            "source_diversity": _bounded(
                dimensions.get("source_diversity")
            ),
            "competitor_diversity": _bounded(
                dimensions.get("competitor_diversity")
            ),
            "evidence_type_diversity": _bounded(
                dimensions.get("evidence_type_diversity")
            ),
            "confidence": _bounded(priority.get("confidence")),
            "evidence_count": evidence_count,
            "source_count": source_count,
            "competitor_count": competitor_count,
        }

        rows.append(
            {
                "schema_version": (
                    "empire.competitor_omega_cortex_context.v1"
                ),
                "entity_id": entity_id,
                "company_name": company_name,
                "feature_namespace": "competitive_intelligence",
                "features": features,
                "stack_state": stack_state,
                "omega": {
                    "context_available": evidence_count > 0,
                    "lead_qualification_mutation": False,
                    "score_persistence_authorized": False,
                    "factual_buyer_state_change": False,
                },
                "cortex": {
                    "learning_context_available": evidence_count > 0,
                    "verified_outcome": False,
                    "training_label": None,
                    "outcome_update_authorized": False,
                },
                "next_best_research_action": _research_action(
                    stack_state=stack_state,
                    evidence_count=evidence_count,
                    source_count=source_count,
                ),
                "recommendation_only": True,
                "research_candidate": evidence_count > 0,
                "buyer_intent": False,
                "commercial_intent": False,
                "outreach_enabled": False,
                "execution_authority": "none",
            }
        )

    rows.sort(
        key=lambda row: (
            row["features"]["research_priority"],
            row["features"]["evidence_count"],
            row["company_name"].casefold(),
        ),
        reverse=True,
    )

    for index, row in enumerate(rows, 1):
        row["research_rank"] = index

    return rows
