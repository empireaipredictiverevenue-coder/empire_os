"""Evidence-backed market capture / domination analysis for Empire Strategy.

"Domination" is the strategic objective; this module never asserts market
control without explicit observed market-share evidence. It produces
recommendation-only strategy packets with zero execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from empire_os.quant_brain import risk_adjusted_score


CAPTURE_STAGES = (
    "DISCOVER",
    "VALIDATE",
    "ESTABLISH",
    "PROVE",
    "DEEPEN",
    "EXPAND",
)

REQUIRED_DIMENSIONS = (
    "demand_strength",
    "buyer_capacity_strength",
    "competition_inverse",
    "product_fit",
    "data_advantage",
    "search_authority",
    "ai_visibility",
    "partner_density",
    "margin_potential",
    "retention_expansion",
    "confidence",
)

DIMENSION_WEIGHTS = {
    "demand_strength": 0.14,
    "buyer_capacity_strength": 0.12,
    "competition_inverse": 0.08,
    "product_fit": 0.13,
    "data_advantage": 0.10,
    "search_authority": 0.08,
    "ai_visibility": 0.06,
    "partner_density": 0.06,
    "margin_potential": 0.11,
    "retention_expansion": 0.08,
    "confidence": 0.04,
}

MOAT_WEIGHTS = {
    "data_advantage": 0.24,
    "search_authority": 0.16,
    "ai_visibility": 0.10,
    "partner_density": 0.12,
    "product_fit": 0.14,
    "retention_expansion": 0.12,
    "buyer_capacity_strength": 0.12,
}


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
    result = _number(value)
    if result is None:
        return None
    if not 0 <= result <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return result


def _nonnegative(value: Any, name: str) -> float | None:
    result = _number(value)
    if result is None:
        return None
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


@dataclass(frozen=True)
class MarketCaptureSnapshot:
    market_key: str
    territory_key: str
    corridor_key: str
    product_key: str
    demand_strength: float | None
    buyer_capacity_strength: float | None
    competition_inverse: float | None
    product_fit: float | None
    data_advantage: float | None
    search_authority: float | None
    ai_visibility: float | None
    partner_density: float | None
    margin_potential: float | None
    retention_expansion: float | None
    confidence: float | None
    verified_buyer_count: int | None
    verified_capacity_units: float | None
    verified_outcome_count: int | None
    repeat_outcome_count: int | None
    expected_gross_profit_cents: float | None
    realized_gross_profit_cents: float | None
    time_to_revenue_days: float | None
    downside_cents: float | None
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        for name in ("market_key", "territory_key", "corridor_key", "product_key"):
            if not _text(getattr(self, name)):
                raise ValueError(f"{name} required")
        if not self.evidence_refs:
            raise ValueError("market capture snapshot requires evidence_refs")
        for name in REQUIRED_DIMENSIONS:
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        for name in (
            "verified_buyer_count",
            "verified_capacity_units",
            "verified_outcome_count",
            "repeat_outcome_count",
            "time_to_revenue_days",
            "downside_cents",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if (
            self.repeat_outcome_count is not None
            and self.verified_outcome_count is not None
            and self.repeat_outcome_count > self.verified_outcome_count
        ):
            raise ValueError("repeat_outcome_count cannot exceed verified_outcome_count")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        result = asdict(self)
        result["evidence_refs"] = list(self.evidence_refs)
        return result


def snapshot_from_mapping(raw: Mapping[str, Any]) -> MarketCaptureSnapshot:
    return MarketCaptureSnapshot(
        market_key=_text(raw.get("market_key")),
        territory_key=_text(raw.get("territory_key")),
        corridor_key=_text(raw.get("corridor_key")),
        product_key=_text(raw.get("product_key")),
        demand_strength=_bounded(raw.get("demand_strength"), "demand_strength"),
        buyer_capacity_strength=_bounded(raw.get("buyer_capacity_strength"), "buyer_capacity_strength"),
        competition_inverse=_bounded(raw.get("competition_inverse"), "competition_inverse"),
        product_fit=_bounded(raw.get("product_fit"), "product_fit"),
        data_advantage=_bounded(raw.get("data_advantage"), "data_advantage"),
        search_authority=_bounded(raw.get("search_authority"), "search_authority"),
        ai_visibility=_bounded(raw.get("ai_visibility"), "ai_visibility"),
        partner_density=_bounded(raw.get("partner_density"), "partner_density"),
        margin_potential=_bounded(raw.get("margin_potential"), "margin_potential"),
        retention_expansion=_bounded(raw.get("retention_expansion"), "retention_expansion"),
        confidence=_bounded(raw.get("confidence"), "confidence"),
        verified_buyer_count=(
            int(raw["verified_buyer_count"])
            if raw.get("verified_buyer_count") is not None else None
        ),
        verified_capacity_units=_nonnegative(raw.get("verified_capacity_units"), "verified_capacity_units"),
        verified_outcome_count=(
            int(raw["verified_outcome_count"])
            if raw.get("verified_outcome_count") is not None else None
        ),
        repeat_outcome_count=(
            int(raw["repeat_outcome_count"])
            if raw.get("repeat_outcome_count") is not None else None
        ),
        expected_gross_profit_cents=_number(raw.get("expected_gross_profit_cents")),
        realized_gross_profit_cents=_number(raw.get("realized_gross_profit_cents")),
        time_to_revenue_days=_nonnegative(raw.get("time_to_revenue_days"), "time_to_revenue_days"),
        downside_cents=_nonnegative(raw.get("downside_cents"), "downside_cents"),
        evidence_refs=tuple(_text(ref) for ref in raw.get("evidence_refs", ()) if _text(ref)),
    )


def _weighted_score(snapshot: MarketCaptureSnapshot) -> tuple[float | None, list[str]]:
    missing = [name for name in REQUIRED_DIMENSIONS if getattr(snapshot, name) is None]
    if missing:
        return None, missing
    score = sum(
        getattr(snapshot, name) * weight
        for name, weight in DIMENSION_WEIGHTS.items()
    )
    return round(score, 6), []


def _moat_score(snapshot: MarketCaptureSnapshot) -> tuple[float | None, list[str]]:
    missing = [name for name in MOAT_WEIGHTS if getattr(snapshot, name) is None]
    if missing:
        return None, missing
    score = sum(
        getattr(snapshot, name) * weight
        for name, weight in MOAT_WEIGHTS.items()
    )
    return round(score, 6), []


def determine_capture_stage(snapshot: MarketCaptureSnapshot) -> dict[str, Any]:
    """Classify observed progress; stage names are internal operating semantics."""
    snapshot.validate()

    if snapshot.demand_strength is None or snapshot.product_fit is None:
        return {
            "stage": "DISCOVER",
            "reason": "demand_or_product_fit_unverified",
            "observed_market_control": False,
        }

    if snapshot.demand_strength < 0.55 or snapshot.product_fit < 0.55:
        return {
            "stage": "VALIDATE",
            "reason": "demand_or_product_fit_below_internal_validation_threshold",
            "observed_market_control": False,
        }

    if (
        snapshot.verified_buyer_count is None
        or snapshot.verified_buyer_count < 1
        or snapshot.verified_capacity_units is None
        or snapshot.verified_capacity_units <= 0
    ):
        return {
            "stage": "VALIDATE",
            "reason": "buyer_or_capacity_not_verified",
            "observed_market_control": False,
        }

    if not snapshot.verified_outcome_count:
        return {
            "stage": "ESTABLISH",
            "reason": "verified_buyer_capacity_present_but_no_verified_outcomes",
            "observed_market_control": False,
        }

    if (
        snapshot.realized_gross_profit_cents is None
        or snapshot.realized_gross_profit_cents <= 0
    ):
        return {
            "stage": "PROVE",
            "reason": "verified_outcomes_exist_but_positive_realized_gp_not_proven",
            "observed_market_control": False,
        }

    if not snapshot.repeat_outcome_count:
        return {
            "stage": "PROVE",
            "reason": "positive_realized_gp_exists_but_repeatability_not_proven",
            "observed_market_control": False,
        }

    moat, missing = _moat_score(snapshot)
    if moat is None or missing:
        return {
            "stage": "DEEPEN",
            "reason": "repeatable_outcomes_exist_but_moat_evidence_incomplete",
            "observed_market_control": False,
        }

    if moat < 0.65:
        return {
            "stage": "DEEPEN",
            "reason": "repeatable_economics_exist_but_defensibility_needs_improvement",
            "observed_market_control": False,
        }

    return {
        "stage": "EXPAND",
        "reason": "repeatable_positive_gp_and_internal_defensibility_threshold_met",
        "observed_market_control": False,
    }


def _next_strategic_objective(stage: str) -> dict[str, Any]:
    objectives = {
        "DISCOVER": {
            "objective": "complete_market_evidence",
            "focus": [
                "validate observed demand",
                "validate product fit",
                "resolve missing market evidence",
            ],
        },
        "VALIDATE": {
            "objective": "validate_buyer_capacity_and_economics",
            "focus": [
                "verify buyer demand/capacity",
                "confirm willingness to pay",
                "validate corridor unit economics",
            ],
        },
        "ESTABLISH": {
            "objective": "produce_first_verified_commercial_outcome",
            "focus": [
                "convert one governed buyer opportunity",
                "verify payment/fulfilment/outcome",
                "measure realized gross profit",
            ],
        },
        "PROVE": {
            "objective": "prove_repeatable_positive_unit_economics",
            "focus": [
                "improve gross-profit quality",
                "produce repeat verified outcomes",
                "calibrate expected vs realized economics",
            ],
        },
        "DEEPEN": {
            "objective": "strengthen_defensibility_and_switching_cost",
            "focus": [
                "increase proprietary data advantage",
                "increase search/AI visibility authority",
                "deepen partners/buyer density and retention",
            ],
        },
        "EXPAND": {
            "objective": "review_adjacent_corridor_expansion",
            "focus": [
                "rank adjacent corridors",
                "preserve current-corridor service quality",
                "reuse proven data/search/product/partner advantages",
            ],
        },
    }
    return objectives[stage]


def _moat_gaps(snapshot: MarketCaptureSnapshot) -> list[dict[str, Any]]:
    gaps = []
    for name, weight in MOAT_WEIGHTS.items():
        value = getattr(snapshot, name)
        if value is None:
            gaps.append({
                "dimension": name,
                "observed_value": None,
                "gap_to_full_strength": None,
                "weight": weight,
                "status": "unknown",
            })
            continue
        gaps.append({
            "dimension": name,
            "observed_value": value,
            "gap_to_full_strength": round(1 - value, 6),
            "weight": weight,
            "status": "observed",
        })
    gaps.sort(
        key=lambda row: (
            row["observed_value"] is None,
            (row["gap_to_full_strength"] or 0) * row["weight"],
        ),
        reverse=True,
    )
    return gaps


def analyse_market_capture(raw: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = snapshot_from_mapping(raw)
    snapshot.validate()

    attractiveness, attractiveness_missing = _weighted_score(snapshot)
    moat, moat_missing = _moat_score(snapshot)
    stage = determine_capture_stage(snapshot)

    risk_adjusted = None
    risk_missing = []
    for field in (
        "expected_gross_profit_cents",
        "downside_cents",
        "time_to_revenue_days",
        "confidence",
    ):
        if getattr(snapshot, field) is None:
            risk_missing.append(field)

    if not risk_missing:
        uncertainty = 1 - snapshot.confidence
        risk_adjusted = risk_adjusted_score(
            expected_gross_profit_cents=snapshot.expected_gross_profit_cents,
            downside_cents=snapshot.downside_cents,
            uncertainty=uncertainty,
            time_to_revenue_days=snapshot.time_to_revenue_days,
            confidence=snapshot.confidence,
        )

    realized_status = {
        "verified_outcome_count": snapshot.verified_outcome_count,
        "repeat_outcome_count": snapshot.repeat_outcome_count,
        "realized_gross_profit_cents": snapshot.realized_gross_profit_cents,
        "realized_economics_available": (
            snapshot.verified_outcome_count is not None
            and snapshot.realized_gross_profit_cents is not None
        ),
    }

    market_share = raw.get("observed_market_share")
    market_share_value = _bounded(market_share, "observed_market_share") if market_share is not None else None
    market_control_claim_available = market_share_value is not None

    expansion_blockers: list[str] = []
    if stage["stage"] != "EXPAND":
        expansion_blockers.append("capture_stage_not_expand")
    if snapshot.realized_gross_profit_cents is None:
        expansion_blockers.append("realized_gross_profit_unknown")
    elif snapshot.realized_gross_profit_cents <= 0:
        expansion_blockers.append("positive_realized_gross_profit_required")
    if not snapshot.repeat_outcome_count:
        expansion_blockers.append("repeat_outcomes_required")
    if moat is None:
        expansion_blockers.append("defensibility_evidence_incomplete")

    return {
        "schema_version": "market_domination_analysis.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "identity": {
            "market_key": snapshot.market_key,
            "territory_key": snapshot.territory_key,
            "corridor_key": snapshot.corridor_key,
            "product_key": snapshot.product_key,
        },
        "capture_stage": stage,
        "next_strategic_objective": _next_strategic_objective(stage["stage"]),
        "moat_gaps": _moat_gaps(snapshot),
        "market_attractiveness": {
            "available": attractiveness is not None,
            "score": attractiveness,
            "missing": attractiveness_missing,
        },
        "defensibility": {
            "available": moat is not None,
            "score": moat,
            "missing": moat_missing,
        },
        "expected_economics": {
            "expected_gross_profit_cents": snapshot.expected_gross_profit_cents,
            "prediction_only": True,
            "actual_revenue": False,
            "risk_adjusted": risk_adjusted,
            "missing": risk_missing,
        },
        "realized_economics": realized_status,
        "observed_market_share": market_share_value,
        "market_control_claim_available": market_control_claim_available,
        "market_control_claimed": False,
        "expansion_review_ready": not expansion_blockers,
        "expansion_blockers": list(dict.fromkeys(expansion_blockers)),
        "evidence_refs": list(snapshot.evidence_refs),
        "market_entry_execution": False,
        "territory_allocation": False,
        "outreach_enabled": False,
        "spend_enabled": False,
        "publishing_enabled": False,
    }


def rank_market_portfolio(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    analyses: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in rows:
        analysis = analyse_market_capture(raw)
        identity = analysis["identity"]
        key = "|".join(
            (
                identity["market_key"],
                identity["territory_key"],
                identity["corridor_key"],
                identity["product_key"],
            )
        )
        if key in seen:
            raise ValueError("duplicate market/territory/corridor/product snapshot")
        seen.add(key)
        analyses.append(analysis)

    def sort_value(item: Mapping[str, Any]) -> tuple[float, float, str]:
        attraction = item["market_attractiveness"]["score"]
        moat = item["defensibility"]["score"]
        risk = item["expected_economics"]["risk_adjusted"]
        quant_score = risk["risk_adjusted_score"] if risk else float("-inf")
        return (
            attraction if attraction is not None else float("-inf"),
            quant_score,
            item["identity"]["corridor_key"],
        )

    analyses.sort(key=sort_value, reverse=True)
    for idx, item in enumerate(analyses, 1):
        item["portfolio_rank"] = idx

    return {
        "schema_version": "market_domination_portfolio.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "markets": analyses,
        "market_entry_execution": False,
        "allocation_execution": False,
    }


def compare_adjacent_corridors(
    *,
    current: Mapping[str, Any],
    candidates: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rank adjacent corridors for review without claiming expansion should occur."""
    current_analysis = analyse_market_capture(current)
    candidate_portfolio = rank_market_portfolio(candidates)

    rows = []
    for item in candidate_portfolio["markets"]:
        blockers: list[str] = []
        if current_analysis["capture_stage"]["stage"] not in {"DEEPEN", "EXPAND"}:
            blockers.append("current_corridor_not_mature_enough_for_adjacency_review")
        if (
            current_analysis["realized_economics"]["realized_gross_profit_cents"]
            is None
        ):
            blockers.append("current_realized_gp_unknown")
        if item["market_attractiveness"]["score"] is None:
            blockers.append("candidate_attractiveness_incomplete")
        rows.append({
            "candidate": item,
            "adjacency_review_ready": not blockers,
            "blockers": blockers,
        })

    return {
        "schema_version": "adjacent_corridor_review.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "current": current_analysis,
        "candidates": rows,
        "expansion_execution": False,
    }
