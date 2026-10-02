"""Typed proactive strategy/portfolio intelligence for EmpireOS.

Pure decision support. No outbound, spend, commercial, deploy, payment or revenue
recognition authority is granted by this module.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


STRATEGY_TYPES = frozenset({
    "market_entry",
    "product_packaging",
    "pricing_hypothesis",
    "offer_demo",
    "buyer_acquisition",
    "zero_paid_acquisition",
    "partnership_affiliate",
    "seo_aeo_geo",
    "media_content",
    "geo_territory",
    "icp_account",
    "persona_buying_committee",
    "retention_expansion",
    "marketplace_liquidity",
    "supply_acquisition",
    "operational_leverage",
    "data_product",
    "strategic_moat",
})

SCORE_WEIGHTS = {
    "strategic_fit": 0.14,
    "product_market_fit": 0.12,
    "buyer_accessibility": 0.10,
    "distribution_advantage": 0.10,
    "data_advantage": 0.09,
    "competitive_gap": 0.08,
    "speed_to_signal": 0.08,
    "reversibility": 0.07,
    "learning_value": 0.08,
    "moat_contribution": 0.06,
    "operational_simplicity": 0.04,
    "external_cost_efficiency": 0.04,
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bounded(value: Any, name: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not 0 <= number <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _nonnegative_int(value: Any, name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if number < 0:
        raise ValueError(f"{name} must be nonnegative")
    return number


def _tuple_text(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(_text(item) for item in value if _text(item))


@dataclass(frozen=True)
class StrategyCandidate:
    strategy_id: str
    strategy_type: str
    thesis: str
    target_market: str
    territory: str | None
    target_icp: str
    target_roles: tuple[str, ...]
    channel: str
    offer_key: str | None
    evidence_refs: tuple[str, ...]
    evidence_confidence: float | None
    expected_upside_cents: int | None
    estimated_external_cost_cents: int | None
    time_to_signal_days: int | None
    speed_to_signal: float | None
    reversibility: float | None
    strategic_fit: float | None
    product_market_fit: float | None
    buyer_accessibility: float | None
    data_advantage: float | None
    distribution_advantage: float | None
    competitive_gap: float | None
    learning_value: float | None
    moat_contribution: float | None
    operational_simplicity: float | None
    external_cost_efficiency: float | None
    dependencies: tuple[str, ...]
    risks: tuple[str, ...]
    experiment: Mapping[str, Any]
    kill_criteria: tuple[str, ...]
    owner_department: str
    authority_required: str

    def validate(self) -> None:
        if not self.strategy_id:
            raise ValueError("strategy_id required")
        if self.strategy_type not in STRATEGY_TYPES:
            raise ValueError("unsupported strategy_type")
        if not self.thesis:
            raise ValueError("thesis required")
        if not self.target_market:
            raise ValueError("target_market required")
        if not self.target_icp:
            raise ValueError("target_icp required")
        if not self.channel:
            raise ValueError("channel required")
        if not self.evidence_refs:
            raise ValueError("strategy candidate requires evidence_refs")
        if not self.owner_department:
            raise ValueError("owner_department required")
        if not self.authority_required:
            raise ValueError("authority_required required")
        if not self.kill_criteria:
            raise ValueError("kill_criteria required")
        if not isinstance(self.experiment, Mapping) or not self.experiment:
            raise ValueError("experiment required")


def candidate_from_mapping(raw: Mapping[str, Any]) -> StrategyCandidate:
    candidate = StrategyCandidate(
        strategy_id=_text(raw.get("strategy_id")),
        strategy_type=_text(raw.get("strategy_type")).lower(),
        thesis=_text(raw.get("thesis")),
        target_market=_text(raw.get("target_market")),
        territory=_text(raw.get("territory")) or None,
        target_icp=_text(raw.get("target_icp")),
        target_roles=_tuple_text(raw.get("target_roles")),
        channel=_text(raw.get("channel")).lower(),
        offer_key=_text(raw.get("offer_key")) or None,
        evidence_refs=_tuple_text(raw.get("evidence_refs")),
        evidence_confidence=_bounded(raw.get("evidence_confidence"), "evidence_confidence"),
        expected_upside_cents=_nonnegative_int(raw.get("expected_upside_cents"), "expected_upside_cents"),
        estimated_external_cost_cents=_nonnegative_int(raw.get("estimated_external_cost_cents"), "estimated_external_cost_cents"),
        time_to_signal_days=_nonnegative_int(raw.get("time_to_signal_days"), "time_to_signal_days"),
        speed_to_signal=_bounded(raw.get("speed_to_signal"), "speed_to_signal"),
        reversibility=_bounded(raw.get("reversibility"), "reversibility"),
        strategic_fit=_bounded(raw.get("strategic_fit"), "strategic_fit"),
        product_market_fit=_bounded(raw.get("product_market_fit"), "product_market_fit"),
        buyer_accessibility=_bounded(raw.get("buyer_accessibility"), "buyer_accessibility"),
        data_advantage=_bounded(raw.get("data_advantage"), "data_advantage"),
        distribution_advantage=_bounded(raw.get("distribution_advantage"), "distribution_advantage"),
        competitive_gap=_bounded(raw.get("competitive_gap"), "competitive_gap"),
        learning_value=_bounded(raw.get("learning_value"), "learning_value"),
        moat_contribution=_bounded(raw.get("moat_contribution"), "moat_contribution"),
        operational_simplicity=_bounded(raw.get("operational_simplicity"), "operational_simplicity"),
        external_cost_efficiency=_bounded(raw.get("external_cost_efficiency"), "external_cost_efficiency"),
        dependencies=_tuple_text(raw.get("dependencies")),
        risks=_tuple_text(raw.get("risks")),
        experiment=dict(raw.get("experiment") or {}),
        kill_criteria=_tuple_text(raw.get("kill_criteria")),
        owner_department=_text(raw.get("owner_department")).lower(),
        authority_required=_text(raw.get("authority_required")).lower(),
    )
    candidate.validate()
    return candidate


def _fingerprint(candidate: StrategyCandidate) -> str:
    payload = {
        "strategy_type": candidate.strategy_type,
        "target_market": candidate.target_market.lower(),
        "territory": (candidate.territory or "").lower(),
        "target_icp": candidate.target_icp.lower(),
        "channel": candidate.channel,
        "offer_key": (candidate.offer_key or "").lower(),
        "thesis": " ".join(candidate.thesis.lower().split()),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def score_strategy_candidate(raw: Mapping[str, Any] | StrategyCandidate) -> dict[str, Any]:
    candidate = raw if isinstance(raw, StrategyCandidate) else candidate_from_mapping(raw)
    dimensions = {name: getattr(candidate, name) for name in SCORE_WEIGHTS}
    observed = {name: value for name, value in dimensions.items() if value is not None}
    missing = [name for name, value in dimensions.items() if value is None]
    weighted = sum(observed[name] * SCORE_WEIGHTS[name] for name in observed)
    available_weight = sum(SCORE_WEIGHTS[name] for name in observed)
    normalized = weighted / available_weight if available_weight else None
    score = None
    if normalized is not None and candidate.evidence_confidence is not None:
        score = normalized * candidate.evidence_confidence

    return {
        "schema_version": "empire.strategic-growth-candidate.v2",
        "candidate": asdict(candidate),
        "fingerprint": _fingerprint(candidate),
        "score": round(score, 6) if score is not None else None,
        "dimension_score": round(normalized, 6) if normalized is not None else None,
        "observed_dimensions": sorted(observed),
        "missing_dimensions": missing,
        "evidence_complete_for_ranking": score is not None,
        "economics_observed": candidate.expected_upside_cents is not None,
        "external_cost_observed": candidate.estimated_external_cost_cents is not None,
        "recommendation_only": True,
        "execution_authority": "none",
        "outreach_enabled": False,
        "spend_enabled": False,
        "commercial_terms_enabled": False,
        "payment_enabled": False,
        "revenue_recognition_enabled": False,
    }


def strategy_experiment_contract(raw: Mapping[str, Any] | StrategyCandidate) -> dict[str, Any]:
    candidate = raw if isinstance(raw, StrategyCandidate) else candidate_from_mapping(raw)
    experiment = dict(candidate.experiment)
    blockers: list[str] = []
    for key in ("hypothesis", "target_metric", "measurement_window", "minimum_evidence_threshold"):
        if not _text(experiment.get(key)):
            blockers.append(f"experiment_{key}_required")
    if not candidate.kill_criteria:
        blockers.append("kill_criteria_required")
    return {
        "schema_version": "empire.strategy-experiment.v2",
        "strategy_id": candidate.strategy_id,
        "strategy_type": candidate.strategy_type,
        "owner_department": candidate.owner_department,
        "hypothesis": _text(experiment.get("hypothesis")) or None,
        "baseline": experiment.get("baseline"),
        "intervention": experiment.get("intervention"),
        "target_metric": _text(experiment.get("target_metric")) or None,
        "measurement_window": _text(experiment.get("measurement_window")) or None,
        "minimum_evidence_threshold": _text(experiment.get("minimum_evidence_threshold")) or None,
        "kill_criteria": list(candidate.kill_criteria),
        "expected_learning": _text(experiment.get("expected_learning")) or None,
        "evidence_refs": list(candidate.evidence_refs),
        "review_ready": not blockers,
        "blockers": blockers,
        "authority_required": candidate.authority_required,
        "execution_authority": "none",
        "automatic_external_execution": False,
    }


def build_strategy_portfolio(
    rows: Iterable[Mapping[str, Any] | StrategyCandidate],
    *,
    limit: int = 12,
    max_per_strategy_type: int = 2,
    max_per_channel: int = 3,
) -> dict[str, Any]:
    scored: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    for raw in rows:
        item = score_strategy_candidate(raw)
        fingerprint = item["fingerprint"]
        strategy_id = item["candidate"]["strategy_id"]
        if fingerprint in seen:
            duplicates.append(strategy_id)
            continue
        seen.add(fingerprint)
        scored.append(item)

    max_upside = max(
        (
            int(item["candidate"]["expected_upside_cents"])
            for item in scored
            if item["candidate"]["expected_upside_cents"] is not None
        ),
        default=0,
    )
    for item in scored:
        upside = item["candidate"]["expected_upside_cents"]
        relative_upside = (float(upside) / max_upside) if upside is not None and max_upside else None
        base = item["score"]
        if base is None:
            adjusted = None
        elif relative_upside is None:
            adjusted = base
        else:
            adjusted = (base * 0.88) + (relative_upside * item["candidate"]["evidence_confidence"] * 0.12)
        item["relative_upside_score"] = round(relative_upside, 6) if relative_upside is not None else None
        item["portfolio_score"] = round(adjusted, 6) if adjusted is not None else None

    scored.sort(
        key=lambda item: (
            item["portfolio_score"] is not None,
            item["portfolio_score"] or -1.0,
            item["candidate"]["learning_value"] or -1.0,
            item["candidate"]["strategy_id"],
        ),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    type_counts: dict[str, int] = {}
    channel_counts: dict[str, int] = {}
    for item in scored:
        strategy_type = item["candidate"]["strategy_type"]
        channel = item["candidate"]["channel"]
        blockers: list[str] = []
        if item["portfolio_score"] is None:
            blockers.append("insufficient_scoring_evidence")
        if type_counts.get(strategy_type, 0) >= max(1, int(max_per_strategy_type)):
            blockers.append("strategy_type_concentration_limit")
        if channel_counts.get(channel, 0) >= max(1, int(max_per_channel)):
            blockers.append("channel_concentration_limit")
        if len(selected) >= max(1, int(limit)):
            blockers.append("portfolio_limit")
        item["portfolio_blockers"] = blockers
        if blockers:
            deferred.append(item)
            continue
        item["portfolio_rank"] = len(selected) + 1
        selected.append(item)
        type_counts[strategy_type] = type_counts.get(strategy_type, 0) + 1
        channel_counts[channel] = channel_counts.get(channel, 0) + 1

    return {
        "schema_version": "empire.strategic-growth-portfolio.v2",
        "mode": "OBSERVE",
        "candidate_count": len(scored),
        "selected_count": len(selected),
        "deferred_count": len(deferred),
        "duplicate_strategy_ids": duplicates,
        "selected": selected,
        "deferred": deferred,
        "strategy_type_counts": type_counts,
        "channel_counts": channel_counts,
        "portfolio_limit": max(1, int(limit)),
        "execution_authority": "none",
        "automatic_external_execution": False,
        "outreach_enabled": False,
        "spend_enabled": False,
        "commercial_terms_enabled": False,
        "payment_enabled": False,
        "revenue_recognition_enabled": False,
    }
