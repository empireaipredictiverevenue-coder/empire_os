"""Evidence-aware Lead Scoring v2.

v1 treated missing evidence as zero. v2 keeps quality and evidence confidence
separate so unknown data cannot silently become a negative commercial signal.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from empire_os.lead_scoring import (
    score_business_presence,
    score_data_completeness,
    score_market_fit,
)
from empire_os.search_fabric.verification import classify_result


QUALITY_WEIGHTS = {
    "business_presence": 0.25,
    "market_fit": 0.50,
    "engagement_potential": 0.15,
    "enrichment_quality": 0.10,
}

MIN_DECISION_CONFIDENCE = 0.50


class LeadScoringV2Error(ValueError):
    """Evidence-aware scoring inputs are invalid."""


def _bounded_100(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise LeadScoringV2Error(
            f"{field} must be numeric"
        ) from exc
    if not 0.0 <= number <= 100.0:
        raise LeadScoringV2Error(
            f"{field} must be between 0 and 100"
        )
    return number


def is_first_party_website(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return classify_result(title="", url=text) == "direct_business"


def _has_presence_evidence(lead: Mapping[str, Any]) -> bool:
    if is_first_party_website(lead.get("website")):
        return True
    for key in ("email", "phone", "bbb_rating"):
        if lead.get(key):
            return True

    social = lead.get("social_links")
    if isinstance(social, (list, tuple, set)) and social:
        return True
    if isinstance(social, str) and social.strip() not in ("", "[]"):
        return True
    return False


def _quality_band(score: float) -> str:
    if score >= 75:
        return "hot"
    if score >= 50:
        return "warm"
    if score >= 25:
        return "cold"
    return "dead"


def _action(decision_tier: str) -> str:
    if decision_tier == "insufficient_evidence":
        return "Collect evidence before commercial action"
    if decision_tier == "hot":
        return "Review for immediate governed contact"
    if decision_tier == "warm":
        return "Review for nurture or targeted enrichment"
    if decision_tier == "cold":
        return "Enrich before contact"
    return "Archive only after evidence review"


def compute_lead_score_v2(
    lead: Mapping[str, Any],
    *,
    buy_signal_observed: bool = False,
    enrichment_observed: bool = False,
    business_presence_checked: bool = False,
) -> dict[str, Any]:
    """Score observed evidence without coercing unknown dimensions to zero."""

    dimensions: dict[str, float | None] = {
        "business_presence": None,
        "market_fit": None,
        "engagement_potential": None,
        "enrichment_quality": None,
    }

    if lead.get("niche") or lead.get("business_name"):
        dimensions["market_fit"] = float(
            score_market_fit(dict(lead))
        )

    scoring_input = dict(lead)
    if not is_first_party_website(scoring_input.get("website")):
        scoring_input["website"] = None

    if business_presence_checked or _has_presence_evidence(lead):
        dimensions["business_presence"] = float(
            score_business_presence(scoring_input)
        )

    if buy_signal_observed:
        value = lead.get("buy_signal_score")
        if value is None:
            raise LeadScoringV2Error(
                "observed buy_signal_score is missing"
            )
        dimensions["engagement_potential"] = _bounded_100(
            value,
            field="buy_signal_score",
        )

    if enrichment_observed:
        value = lead.get("enrichment_score")
        if value is None:
            raise LeadScoringV2Error(
                "observed enrichment_score is missing"
            )
        dimensions["enrichment_quality"] = _bounded_100(
            value,
            field="enrichment_score",
        )

    observed = [
        key for key, value in dimensions.items()
        if value is not None
    ]
    unknown = [
        key for key, value in dimensions.items()
        if value is None
    ]

    observed_weight = sum(
        QUALITY_WEIGHTS[key] for key in observed
    )
    if observed_weight <= 0:
        quality_score = None
    else:
        weighted = sum(
            float(dimensions[key]) * QUALITY_WEIGHTS[key]
            for key in observed
        )
        quality_score = round(weighted / observed_weight, 1)

    completeness_input = dict(scoring_input)
    if (
        not completeness_input.get("street")
        and completeness_input.get("address")
    ):
        # Canonical address evidence satisfies the scorer street field.
        completeness_input["street"] = completeness_input["address"]

    completeness = float(
        score_data_completeness(completeness_input)
    )
    evidence_coverage = round(observed_weight, 4)
    evidence_confidence = round(
        min(completeness / 100.0, evidence_coverage),
        4,
    )

    quality_band = (
        _quality_band(quality_score)
        if quality_score is not None
        else "unknown"
    )
    decision_tier = (
        quality_band
        if (
            quality_score is not None
            and evidence_confidence >= MIN_DECISION_CONFIDENCE
        )
        else "insufficient_evidence"
    )

    return {
        "scoring_version": "v2",
        "quality_score": quality_score,
        "quality_band": quality_band,
        "decision_tier": decision_tier,
        "evidence_confidence": evidence_confidence,
        "evidence_coverage": evidence_coverage,
        "data_completeness_score": round(completeness, 1),
        "dimensions": dimensions,
        "observed_dimensions": observed,
        "unknown_dimensions": unknown,
        "recommended_action": _action(decision_tier),
    }
