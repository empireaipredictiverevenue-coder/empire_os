"""Pure qualification-v2 payload builder.

No database or network access. Produces a versioned row payload that preserves
unknown dimensions as NULL and keeps evidence confidence separate from score.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from empire_os.lead_scoring_v2 import compute_lead_score_v2


class QualificationV2Error(ValueError):
    """A v2 qualification payload cannot be built safely."""


def _uuid(value: Any, *, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise QualificationV2Error(
            f"invalid {field}"
        ) from exc


def build_v2_qualification_payload(
    prospect: dict[str, Any],
    *,
    entity_id: str | None = None,
    buy_signal_observed: bool = False,
    enrichment_observed: bool = False,
    business_presence_checked: bool = False,
    scored_at: str | None = None,
) -> dict[str, Any]:
    prospect_id = _uuid(
        prospect.get("id"),
        field="prospect id",
    )
    canonical_entity_id = (
        _uuid(entity_id, field="entity id")
        if entity_id is not None
        else None
    )

    result = compute_lead_score_v2(
        prospect,
        buy_signal_observed=buy_signal_observed,
        enrichment_observed=enrichment_observed,
        business_presence_checked=business_presence_checked,
    )
    dimensions = result["dimensions"]

    if scored_at is None:
        scored_at = datetime.now(timezone.utc).isoformat()

    status = (
        "scored"
        if result["decision_tier"] != "insufficient_evidence"
        else "insufficient_evidence"
    )

    return {
        "prospect_id": prospect_id,
        "entity_id": canonical_entity_id,
        "score": result["quality_score"],
        "tier": result["decision_tier"],
        "data_completeness_score": result[
            "data_completeness_score"
        ],
        "business_presence_score": dimensions[
            "business_presence"
        ],
        "market_fit_score": dimensions["market_fit"],
        "engagement_potential_score": dimensions[
            "engagement_potential"
        ],
        "enrichment_quality_score": dimensions[
            "enrichment_quality"
        ],
        "recommended_action": result["recommended_action"],
        "scoring_engine": "empire_os.lead_scoring",
        "scoring_version": "v2",
        "input_snapshot": dict(prospect),
        "result_payload": result,
        "status": status,
        "evidence_confidence": result[
            "evidence_confidence"
        ],
        "observed_dimensions": result[
            "observed_dimensions"
        ],
        "unknown_dimensions": result[
            "unknown_dimensions"
        ],
        "scored_at": scored_at,
        "updated_at": scored_at,
    }
