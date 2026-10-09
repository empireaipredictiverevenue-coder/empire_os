"""Read-only Omega 2 evaluation and evidence-bound value meter.

The historical eight-domain framework is retained as an *evidence coverage*
view, not a second prediction model or a source of invented commercial value.
"""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.intelligence.omega import analyze


EVIDENCE_DOMAINS = (
    "lead_quality", "speed_scale", "ai_intelligence", "revenue_optimization",
    "automation", "analytics_insight", "integration", "self_learning",
)


def _present(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _coverage(lead: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    groups = {
        "lead_quality": ("business_name", "contact_name", "email", "phone", "niche"),
        "speed_scale": ("source", "observed_at", "response_time_seconds"),
        "ai_intelligence": ("notes", "details", "enrichment_evidence"),
        "revenue_optimization": ("expected_revenue", "expected_cost", "expected_gross_profit"),
        "automation": ("workflow_state", "handoff_evidence"),
        "analytics_insight": ("campaign_id", "attribution_id", "outcome_id"),
        "integration": ("crm_id", "tenant_id", "external_ref"),
        "self_learning": ("verified_outcome_id", "feedback_event_id"),
    }
    return {
        domain: {
            "evidence_present": sum(_present(lead.get(field)) for field in fields),
            "evidence_possible": len(fields),
            "status": "evidenced" if any(_present(lead.get(field)) for field in fields) else "missing",
        }
        for domain, fields in groups.items()
    }


def evaluate(lead: Mapping[str, Any]) -> dict[str, Any]:
    """Present Omega 2 predictions; do not authorize billing or execution."""
    prediction = analyze(lead)
    score = round(prediction.opportunity_score, 2)
    grade = "A" if score >= 90 else "B" if score >= 70 else "C" if score >= 40 else "D"
    return {
        "schema_version": "empire.omega-evaluation.v2",
        "model_version": prediction.model_version,
        "grade": grade,
        "score": score,
        "confidence": prediction.confidence,
        "dimensions": {
            "lead_quality": prediction.quality_probability,
            "buyer_fit": prediction.buyer_fit_probability,
            "engagement": prediction.engagement_probability,
            "conversion": prediction.conversion_probability,
            "payment": prediction.payment_probability,
        },
        "legacy_eight_domain_evidence": _coverage(lead),
        "value_meter": {
            "expected_revenue": prediction.expected_revenue,
            "expected_gross_profit": prediction.expected_gross_profit,
            "revenue_evidence_available": prediction.expected_revenue is not None,
            "gross_profit_evidence_available": prediction.expected_gross_profit is not None,
            "verified_realized_revenue": None,
            "verified_realized_gross_profit": None,
        },
        "expected_revenue": prediction.expected_revenue,
        "expected_gross_profit": prediction.expected_gross_profit,
        "next_best_action": prediction.next_best_action,
        "reasons": list(prediction.reasons),
        "evaluation_only": True,
        "billable": False,
        "execution_authority": "none",
    }
