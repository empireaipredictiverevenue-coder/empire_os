"""Omega 2.0 deterministic intelligence baseline.

This module is intentionally isolated from the legacy Omega implementation.
It provides a versioned prediction contract that can later be backed by
learned models without changing downstream consumers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from .features import LeadFeatures, extract_features


MODEL_VERSION = "omega-2.0-baseline"


@dataclass(frozen=True)
class OmegaPrediction:
    """Canonical commercial intelligence result."""

    model_version: str = MODEL_VERSION

    quality_probability: float = 0.0
    buyer_fit_probability: float = 0.0
    engagement_probability: float = 0.0
    conversion_probability: float = 0.0
    payment_probability: float = 0.0

    expected_revenue: float | None = None
    expected_gross_profit: float | None = None
    time_to_conversion_days: float | None = None

    opportunity_score: float = 0.0
    confidence: float = 0.0

    legacy_omega_score: float = 0.0
    legacy_omega_tier: str = "bronze"

    next_best_action: str = "enrich"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation."""
        return asdict(self)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _has_any(lead: Mapping[str, Any], *fields: str) -> bool:
    return any(str(lead.get(field) or "").strip() for field in fields)


def _text_length(lead: Mapping[str, Any]) -> int:
    fields = (
        "business_name",
        "contact_name",
        "niche",
        "sub_niche",
        "notes",
        "details",
    )
    return sum(len(str(lead.get(field) or "").strip()) for field in fields)


def _quality(features: LeadFeatures) -> tuple[float, list[str]]:
    score = features.data_completeness
    reasons: list[str] = []

    if features.has_identity:
        reasons.append("identity data present")

    if features.has_phone:
        reasons.append("phone present")

    if features.has_email:
        reasons.append("email present")

    if features.has_website:
        reasons.append("website present")

    if features.has_location:
        reasons.append("location data present")

    if features.has_market:
        reasons.append("market classification present")

    if features.has_description:
        reasons.append("useful descriptive context present")

    return _clamp(score), reasons


def _buyer_fit(features: LeadFeatures) -> tuple[float, list[str]]:
    """Estimate buyer fit from current lead evidence only.

    Legacy Omega is intentionally excluded from this calculation. The
    legacy score remains available on LeadFeatures for compatibility and
    audit purposes, but it must not become an input to Omega 2.0.
    """
    score = 0.25
    reasons: list[str] = []

    if features.has_market:
        score += 0.20
        reasons.append("niche identified")

    if features.has_identity or features.has_website:
        score += 0.15
        reasons.append("business identity signal present")

    if features.has_location:
        score += 0.10
        reasons.append("target location identified")

    if features.contactability > 0:
        score += 0.15
        reasons.append("contactability signal present")

    if features.status in {"new", "qualified", "raw"}:
        score += 0.10

    if score >= 0.65:
        reasons.append("lead has commercial targeting signals")

    return _clamp(score), reasons


def _engagement(features: LeadFeatures) -> tuple[float, list[str]]:
    score = 0.15
    reasons: list[str] = []

    score += features.contactability * 0.40

    if features.has_description:
        score += 0.10

    if features.status in {"engaged", "contacted", "qualified"}:
        score += 0.20
        reasons.append("existing engagement state")

    if features.status in {"sold", "converted"}:
        score += 0.05

    if score >= 0.55:
        reasons.append("contactable")

    return _clamp(score), reasons



def _conversion(
    quality: float,
    buyer_fit: float,
    engagement: float,
) -> float:
    """Conservative deterministic baseline.

    This is deliberately not presented as trained probability.
    """
    return _clamp(
        0.10
        + (quality * 0.25)
        + (buyer_fit * 0.30)
        + (engagement * 0.25)
    )


def _legacy_score(
    quality: float,
    buyer_fit: float,
    engagement: float,
) -> float:
    """Map the new feature families onto the existing 0-100 convention."""
    return round(
        _clamp(
            quality * 0.35
            + buyer_fit * 0.35
            + engagement * 0.30
        )
        * 100.0,
        2,
    )


def _legacy_tier(score: float) -> str:
    if score >= 90:
        return "platinum"
    if score >= 70:
        return "gold"
    if score >= 40:
        return "silver"
    return "bronze"


def _positive_value(
    lead: Mapping[str, Any],
    *fields: str,
) -> float | None:
    for field in fields:
        try:
            value = float(lead.get(field))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def _expected_revenue(
    lead: Mapping[str, Any],
    conversion: float,
) -> float | None:
    """Forecast revenue only from explicit commercial value evidence."""
    value = _positive_value(
        lead,
        "expected_revenue",
        "sold_price",
        "price_usd",
    )
    if value is None:
        return None
    return round(value * conversion, 2)


def _expected_gross_profit(
    lead: Mapping[str, Any],
    conversion: float,
    expected_revenue: float | None,
) -> float | None:
    """Forecast GP only when explicit value/cost evidence exists."""
    explicit_gp = _positive_value(
        lead,
        "expected_gross_profit",
        "expected_gp",
        "gross_profit_usd",
    )
    if explicit_gp is not None:
        return round(explicit_gp * conversion, 2)

    if expected_revenue is None:
        return None

    cost = _positive_value(
        lead,
        "expected_cost",
        "cost_usd",
        "acquisition_cost",
    )
    if cost is None:
        return None

    revenue_value = _positive_value(
        lead,
        "expected_revenue",
        "sold_price",
        "price_usd",
    )
    if revenue_value is None:
        return None

    gross_profit_value = revenue_value - cost
    if gross_profit_value <= 0:
        return 0.0
    return round(gross_profit_value * conversion, 2)


def analyze(lead: Mapping[str, Any]) -> OmegaPrediction:
    """Analyze one lead without changing any persistent state."""

    features = extract_features(lead)

    quality, quality_reasons = _quality(features)
    buyer_fit, fit_reasons = _buyer_fit(features)
    engagement, engagement_reasons = _engagement(features)

    conversion = _conversion(quality, buyer_fit, engagement)

    # Payment is intentionally more conservative than conversion until
    # verified payment outcomes become available to the learning layer.
    payment = _clamp(conversion * 0.75)

    expected_revenue = _expected_revenue(lead, conversion)
    expected_gross_profit = _expected_gross_profit(
        lead,
        conversion,
        expected_revenue,
    )

    legacy_score = _legacy_score(quality, buyer_fit, engagement)
    legacy_tier = _legacy_tier(legacy_score)

    confidence = _clamp(
        0.20
        + (quality * 0.30)
        + (buyer_fit * 0.25)
        + (engagement * 0.25)
    )

    opportunity = _clamp(
        (
            conversion * 0.45
            + payment * 0.25
            + buyer_fit * 0.20
            + quality * 0.10
        )
    ) * 100.0

    if quality < 0.45:
        action = "enrich"
    elif buyer_fit < 0.50:
        action = "match_buyer"
    elif engagement < 0.50:
        action = "outreach"
    elif conversion < 0.45:
        action = "nurture"
    else:
        action = "offer"

    reasons = tuple(
        dict.fromkeys(
            quality_reasons
            + fit_reasons
            + engagement_reasons
        )
    )

    return OmegaPrediction(
        quality_probability=round(quality, 4),
        buyer_fit_probability=round(buyer_fit, 4),
        engagement_probability=round(engagement, 4),
        conversion_probability=round(conversion, 4),
        payment_probability=round(payment, 4),
        expected_revenue=expected_revenue,
        expected_gross_profit=expected_gross_profit,
        opportunity_score=round(opportunity, 2),
        confidence=round(confidence, 4),
        legacy_omega_score=legacy_score,
        legacy_omega_tier=legacy_tier,
        next_best_action=action,
        reasons=reasons,
    )



def analyze_many(leads: list[Mapping[str, Any]]) -> list[OmegaPrediction]:
    """Analyze and rank leads by commercial opportunity."""
    predictions = [analyze(lead) for lead in leads]
    return sorted(
        predictions,
        key=lambda result: (
            (result.expected_gross_profit or 0.0) * result.confidence,
            result.opportunity_score,
        ),
        reverse=True,
    )
