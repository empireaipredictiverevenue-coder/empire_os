"""Deterministic search opportunity scoring using observed inputs only."""
from __future__ import annotations

from dataclasses import replace

from .models import SearchOpportunity

_REQUIRED = (
    "intent_score",
    "commercial_intent",
    "conversion_probability",
    "relevance",
    "authority_fit",
    "freshness",
    "competition",
)


def _unit(value: float | None) -> float | None:
    if value is None:
        return None
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError("opportunity factors must be within 0..1")
    return value


def score_opportunity(opportunity: SearchOpportunity) -> SearchOpportunity:
    values = {name: _unit(getattr(opportunity, name)) for name in _REQUIRED}
    missing = [name for name, value in values.items() if value is None]
    if missing:
        return replace(
            opportunity,
            opportunity_score=None,
            score_reason="missing_required_metrics:" + ",".join(missing),
        )

    competition = max(values["competition"], 0.05)
    numerator = (
        values["intent_score"]
        * values["commercial_intent"]
        * values["conversion_probability"]
        * values["relevance"]
        * values["authority_fit"]
        * values["freshness"]
    )
    score = min(1.0, numerator / competition)
    return replace(
        opportunity,
        opportunity_score=round(score, 4),
        score_reason="observed_deterministic_formula",
    )
