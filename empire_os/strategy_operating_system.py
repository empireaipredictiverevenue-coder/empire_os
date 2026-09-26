"""Empire Strategy Department operating primitives.

Pure review/analysis only. No publishing, spend, market entry, model promotion,
commercial mutation or authority expansion.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


MARKET_RECOMMENDATIONS = {"ENTER", "TEST", "WATCH", "AVOID"}
BET_TYPES = {
    "core_optimization",
    "adjacent_product",
    "new_market",
    "new_channel",
    "new_data_source",
    "new_ai_capability",
    "new_monetization",
    "strategic_partnership",
    "frontier_research",
}
AI_BUILD_MODES = {"BUILD", "BUY", "OPEN_SOURCE", "HYBRID", "WATCH"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded(value: Any, name: str) -> float | None:
    x = _number(value)
    if x is None:
        return None
    if not 0 <= x <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return x


@dataclass(frozen=True)
class MarketThesis:
    market_key: str
    customer_problem: float | None
    willingness_to_pay: float | None
    demand_supply_imbalance: float | None
    buyer_capacity: float | None
    competition_inverse: float | None
    data_advantage: float | None
    product_fit: float | None
    gtm_accessibility: float | None
    margin_potential: float | None
    retention_expansion: float | None
    moat_potential: float | None
    confidence: float | None
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not _text(self.market_key):
            raise ValueError("market_key required")
        if not self.evidence_refs:
            raise ValueError("market thesis requires evidence_refs")
        for name in (
            "customer_problem",
            "willingness_to_pay",
            "demand_supply_imbalance",
            "buyer_capacity",
            "competition_inverse",
            "data_advantage",
            "product_fit",
            "gtm_accessibility",
            "margin_potential",
            "retention_expansion",
            "moat_potential",
            "confidence",
        ):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


def review_market_thesis(raw: Mapping[str, Any]) -> dict[str, Any]:
    thesis = MarketThesis(
        market_key=_text(raw.get("market_key")),
        customer_problem=_bounded(raw.get("customer_problem"), "customer_problem"),
        willingness_to_pay=_bounded(raw.get("willingness_to_pay"), "willingness_to_pay"),
        demand_supply_imbalance=_bounded(raw.get("demand_supply_imbalance"), "demand_supply_imbalance"),
        buyer_capacity=_bounded(raw.get("buyer_capacity"), "buyer_capacity"),
        competition_inverse=_bounded(raw.get("competition_inverse"), "competition_inverse"),
        data_advantage=_bounded(raw.get("data_advantage"), "data_advantage"),
        product_fit=_bounded(raw.get("product_fit"), "product_fit"),
        gtm_accessibility=_bounded(raw.get("gtm_accessibility"), "gtm_accessibility"),
        margin_potential=_bounded(raw.get("margin_potential"), "margin_potential"),
        retention_expansion=_bounded(raw.get("retention_expansion"), "retention_expansion"),
        moat_potential=_bounded(raw.get("moat_potential"), "moat_potential"),
        confidence=_bounded(raw.get("confidence"), "confidence"),
        evidence_refs=tuple(_text(x) for x in raw.get("evidence_refs", ()) if _text(x)),
    )
    thesis.validate()

    dimensions = {
        name: getattr(thesis, name)
        for name in (
            "customer_problem",
            "willingness_to_pay",
            "demand_supply_imbalance",
            "buyer_capacity",
            "competition_inverse",
            "data_advantage",
            "product_fit",
            "gtm_accessibility",
            "margin_potential",
            "retention_expansion",
            "moat_potential",
        )
    }
    missing = [name for name, value in dimensions.items() if value is None]
    if thesis.confidence is None:
        missing.append("confidence")

    if missing:
        return {
            "schema_version": "market_thesis_review.v1",
            "market_key": thesis.market_key,
            "available": False,
            "score": None,
            "recommendation": None,
            "missing": missing,
            "execution_authority": "none",
        }

    raw_score = sum(dimensions.values()) / len(dimensions)
    score = raw_score * thesis.confidence

    if score >= 0.72:
        recommendation = "ENTER"
    elif score >= 0.55:
        recommendation = "TEST"
    elif score >= 0.38:
        recommendation = "WATCH"
    else:
        recommendation = "AVOID"

    return {
        "schema_version": "market_thesis_review.v1",
        "market_key": thesis.market_key,
        "available": True,
        "score": round(score, 6),
        "recommendation": recommendation,
        "missing": [],
        "evidence_refs": list(thesis.evidence_refs),
        "recommendation_only": True,
        "execution_authority": "none",
        "market_entry_execution": False,
    }


def review_strategic_bet(raw: Mapping[str, Any]) -> dict[str, Any]:
    bet_id = _text(raw.get("bet_id"))
    bet_type = _text(raw.get("bet_type")).lower()
    blockers: list[str] = []

    if not bet_id:
        blockers.append("bet_id_required")
    if bet_type not in BET_TYPES:
        blockers.append("unsupported_bet_type")
    if not _text(raw.get("thesis")):
        blockers.append("thesis_required")
    if not raw.get("evidence_refs"):
        blockers.append("evidence_refs_required")
    if not _text(raw.get("owner")):
        blockers.append("owner_required")
    if not _text(raw.get("kill_criteria")):
        blockers.append("kill_criteria_required")
    if not _text(raw.get("learning_objective")):
        blockers.append("learning_objective_required")

    upside = _number(raw.get("expected_upside_cents"))
    investment = _number(raw.get("investment_cents"))
    downside = _number(raw.get("downside_cents"))
    confidence = _bounded(raw.get("confidence"), "confidence")
    reversibility = _bounded(raw.get("reversibility"), "reversibility")

    if upside is not None and upside < 0:
        blockers.append("expected_upside_must_be_nonnegative")
    if investment is not None and investment < 0:
        blockers.append("investment_must_be_nonnegative")
    if downside is not None and downside < 0:
        blockers.append("downside_must_be_nonnegative")

    economics_available = None not in (upside, investment, downside, confidence, reversibility)
    strategic_score = None
    if economics_available:
        net = upside - investment
        penalty = downside * (1 - reversibility)
        strategic_score = (net - penalty) * confidence

    return {
        "schema_version": "strategic_bet_review.v1",
        "bet_id": bet_id or None,
        "bet_type": bet_type or None,
        "review_ready": not blockers,
        "blockers": blockers,
        "economics_available": economics_available,
        "strategic_value_cents": round(strategic_score, 2) if strategic_score is not None else None,
        "recommendation_only": True,
        "execution_authority": "none",
        "capital_commitment": False,
        "market_entry_execution": False,
    }


def score_keyword_opportunity(raw: Mapping[str, Any]) -> dict[str, Any]:
    keyword = _text(raw.get("keyword"))
    if not keyword:
        raise ValueError("keyword required")
    evidence_refs = [_text(x) for x in raw.get("evidence_refs", ()) if _text(x)]
    if not evidence_refs:
        raise ValueError("keyword opportunity requires evidence_refs")

    fields = {
        "observed_demand": _bounded(raw.get("observed_demand"), "observed_demand"),
        "commercial_intent": _bounded(raw.get("commercial_intent"), "commercial_intent"),
        "product_fit": _bounded(raw.get("product_fit"), "product_fit"),
        "buyer_fit": _bounded(raw.get("buyer_fit"), "buyer_fit"),
        "coverage_gap": _bounded(raw.get("coverage_gap"), "coverage_gap"),
        "competitor_gap": _bounded(raw.get("competitor_gap"), "competitor_gap"),
        "ai_citation_gap": _bounded(raw.get("ai_citation_gap"), "ai_citation_gap"),
        "conversion_evidence": _bounded(raw.get("conversion_evidence"), "conversion_evidence"),
        "strategic_category_value": _bounded(raw.get("strategic_category_value"), "strategic_category_value"),
        "confidence": _bounded(raw.get("confidence"), "confidence"),
    }
    missing = [k for k, v in fields.items() if v is None]
    if missing:
        return {
            "keyword": keyword,
            "available": False,
            "score": None,
            "missing": missing,
            "evidence_refs": evidence_refs,
        }

    weights = {
        "observed_demand": 0.13,
        "commercial_intent": 0.16,
        "product_fit": 0.14,
        "buyer_fit": 0.10,
        "coverage_gap": 0.09,
        "competitor_gap": 0.08,
        "ai_citation_gap": 0.07,
        "conversion_evidence": 0.11,
        "strategic_category_value": 0.12,
    }
    base = sum(fields[k] * w for k, w in weights.items())
    score = base * fields["confidence"]
    return {
        "keyword": keyword,
        "available": True,
        "score": round(score, 6),
        "missing": [],
        "evidence_refs": evidence_refs,
        "recommendation_only": True,
    }


def rank_keyword_portfolio(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    available = []
    unavailable = []
    seen: set[str] = set()

    for raw in rows:
        scored = score_keyword_opportunity(raw)
        key = scored["keyword"].lower()
        if key in seen:
            raise ValueError("duplicate keyword")
        seen.add(key)
        (available if scored["available"] else unavailable).append(scored)

    available.sort(key=lambda x: (x["score"], x["keyword"]), reverse=True)
    for idx, item in enumerate(available, 1):
        item["rank"] = idx

    return {
        "schema_version": "keyword_strategy_portfolio.v1",
        "mode": "OBSERVE",
        "ranked": available,
        "unscored": unavailable,
        "publishing_enabled": False,
        "indexation_enabled": False,
        "execution_authority": "none",
    }


def review_ai_capability(raw: Mapping[str, Any]) -> dict[str, Any]:
    capability_key = _text(raw.get("capability_key"))
    blockers: list[str] = []

    if not capability_key:
        blockers.append("capability_key_required")
    if not _text(raw.get("problem")):
        blockers.append("problem_required")
    if not _text(raw.get("strategic_advantage")):
        blockers.append("strategic_advantage_required")
    if not raw.get("evidence_refs"):
        blockers.append("evidence_refs_required")

    value = _bounded(raw.get("strategic_value"), "strategic_value")
    uniqueness = _bounded(raw.get("proprietary_data_advantage"), "proprietary_data_advantage")
    performance = _bounded(raw.get("expected_quality_gain"), "expected_quality_gain")
    privacy = _bounded(raw.get("privacy_importance"), "privacy_importance")
    cost_sensitivity = _bounded(raw.get("cost_sensitivity"), "cost_sensitivity")
    switching = _bounded(raw.get("switching_flexibility"), "switching_flexibility")
    confidence = _bounded(raw.get("confidence"), "confidence")

    inputs = (value, uniqueness, performance, privacy, cost_sensitivity, switching, confidence)
    if any(x is None for x in inputs):
        blockers.append("complete_quantified_review_required")

    build_mode = None
    if not blockers:
        own_score = (0.30 * uniqueness + 0.20 * privacy + 0.20 * strategic_value_safe(value)
                     + 0.15 * cost_sensitivity + 0.15 * (1 - switching))
        buy_score = (0.35 * performance + 0.25 * switching + 0.20 * (1 - privacy)
                     + 0.20 * (1 - uniqueness))
        if own_score >= 0.68:
            build_mode = "BUILD"
        elif buy_score >= 0.68:
            build_mode = "BUY"
        elif max(own_score, buy_score) >= 0.52:
            build_mode = "HYBRID"
        else:
            build_mode = "WATCH"

    return {
        "schema_version": "ai_capability_strategy.v1",
        "capability_key": capability_key or None,
        "review_ready": not blockers,
        "blockers": blockers,
        "recommended_mode": build_mode,
        "recommendation_only": True,
        "provider_activation": False,
        "model_promotion": False,
        "authority_expansion": False,
        "execution_authority": "none",
    }


def strategic_value_safe(value: float | None) -> float:
    return 0.0 if value is None else value
