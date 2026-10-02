"""Predictive Revenue JEV signal-to-output composition.

JEV composes existing evidence normalization, Quant Brain economics and
Predictive Revenue value/action primitives.  It creates recommendations only;
it has no commercial, allocation, outbound, payment or revenue authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from empire_os.predictive_revenue_formula import (
    expected_revenue_value,
    next_best_action_value,
)
from empire_os.quant_brain import expected_economics, risk_adjusted_score


ALLOWED_OUTPUT_TYPES = frozenset({
    "OPPORTUNITY_CREATE",
    "BUYER_MATCH_REVIEW",
    "BID_PROPOSAL",
    "PRICING_REVIEW",
    "OUTREACH_REVIEW",
    "CAMPAIGN_REVIEW",
    "RESEARCH_REQUIRED",
    "HOLD",
    "NO_ACTION",
})

SUPPORTED_TRUTH_CLASSES = frozenset({
    "OBSERVED",
    "MODELED",
    "POLICY",
    "INFERRED",
})

QUANT_REQUIRED = (
    "probability_success",
    "conditional_revenue_cents",
    "fixed_cost_cents",
    "success_cost_cents",
    "uncertainty",
    "time_to_revenue_days",
    "confidence",
)


@dataclass(frozen=True)
class JEVSignalEnvelope:
    signal_id: str
    signal_type: str
    observed_at: str
    truth_class: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class PredictiveRevenueJEVPacket:
    signal_id: str
    signal_type: str
    signal_truth_class: str
    signal_age_seconds: float | None
    freshness: str
    opportunity_key: str | None
    opportunity_class: str | None
    output_type: str
    normalized_signals: Mapping[str, Any]
    probability_success: float | None
    conditional_revenue_cents: float | None
    expected_revenue_cents: float | None
    expected_cost_cents: float | None
    expected_gross_profit_cents: float | None
    risk_adjusted_score: float | None
    predictive_revenue_erv: Mapping[str, Any]
    next_best_action: Mapping[str, Any]
    recommended_action: Mapping[str, Any] | None
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    value_available: bool
    mode: str = "OBSERVE"
    recommendation_only: bool = True
    actual_revenue: bool = False
    execution_authority: str = "none"
    allocation_execution: bool = False
    pricing_mutation: bool = False
    outbound_action: bool = False
    terms_acceptance: bool = False
    payment_action: bool = False
    settlement_action: bool = False
    fulfilment_execution: bool = False
    revenue_recognition: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _parse_timestamp(value: Any) -> datetime | None:
    raw = _clean(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _collect_evidence_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "evidence_refs" and isinstance(item, (list, tuple, set)):
                refs.extend(_clean(ref) for ref in item if _clean(ref))
            elif isinstance(item, (Mapping, list, tuple)):
                refs.extend(_collect_evidence_refs(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            refs.extend(_collect_evidence_refs(item))
    return refs


def _signal_envelope(value: JEVSignalEnvelope | Mapping[str, Any]) -> JEVSignalEnvelope:
    if isinstance(value, JEVSignalEnvelope):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("signal must be JEVSignalEnvelope or mapping")
    return JEVSignalEnvelope(
        signal_id=_clean(value.get("signal_id")),
        signal_type=_clean(value.get("signal_type")),
        observed_at=_clean(value.get("observed_at")),
        truth_class=_clean(value.get("truth_class")).upper(),
        evidence_refs=tuple(dict.fromkeys(
            _clean(ref)
            for ref in (value.get("evidence_refs") or ())
            if _clean(ref)
        )),
    )


def _explicit_recommended_output_type(
    nba: Mapping[str, Any],
    actions: Sequence[Mapping[str, Any]],
) -> tuple[str | None, str | None]:
    recommended = nba.get("recommended_action")
    if not isinstance(recommended, Mapping):
        return None, None
    key = _clean(recommended.get("action_key"))
    if not key:
        return None, None
    source = next(
        (
            action
            for action in actions
            if _clean(action.get("action_key")) == key
        ),
        None,
    )
    if not isinstance(source, Mapping):
        return None, None
    output_type = _clean(source.get("output_type")).upper()
    if not output_type:
        return None, None
    if output_type not in ALLOWED_OUTPUT_TYPES:
        return None, "recommended_action_output_type_invalid"
    return output_type, None


def compile_predictive_revenue_jev(
    *,
    signal: JEVSignalEnvelope | Mapping[str, Any],
    normalized_opportunity: Mapping[str, Any],
    as_of: datetime,
    max_signal_age_seconds: int = 21600,
    predictive_revenue_inputs: Mapping[str, Any] | None = None,
    actions: Sequence[Mapping[str, Any]] = (),
) -> PredictiveRevenueJEVPacket:
    """Compile one evidence-backed signal to one recommendation-only packet."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if max_signal_age_seconds <= 0:
        raise ValueError("max_signal_age_seconds must be positive")

    envelope = _signal_envelope(signal)
    blockers: list[str] = []

    if not envelope.signal_id:
        blockers.append("signal_id_missing")
    if not envelope.signal_type:
        blockers.append("signal_type_missing")
    if envelope.truth_class not in SUPPORTED_TRUTH_CLASSES:
        blockers.append("signal_truth_class_invalid")
    if not envelope.evidence_refs:
        blockers.append("signal_evidence_missing")

    observed_at = _parse_timestamp(envelope.observed_at)
    age_seconds: float | None = None
    freshness = "UNKNOWN"
    if observed_at is None:
        blockers.append("signal_timestamp_invalid")
    else:
        age_seconds = round(
            (as_of.astimezone(timezone.utc) - observed_at).total_seconds(),
            6,
        )
        if age_seconds < 0:
            blockers.append("signal_from_future")
            freshness = "INVALID"
        elif age_seconds > max_signal_age_seconds:
            blockers.append("signal_stale")
            freshness = "STALE"
        else:
            freshness = "FRESH"

    row = dict(normalized_opportunity or {})
    normalized_signals = dict(row.get("normalized_signals") or {})
    quant_inputs = dict(row.get("quant_inputs") or {})

    missing_quant = [
        field for field in QUANT_REQUIRED
        if quant_inputs.get(field) is None
    ]
    blockers.extend(f"quant_input_missing:{field}" for field in missing_quant)
    if row.get("probability_modeled_from_verified_outcomes") is not True:
        blockers.append("probability_not_backed_by_verified_outcomes")

    evidence_refs = list(envelope.evidence_refs)
    evidence_refs.extend(_collect_evidence_refs(row.get("score_evidence") or {}))
    evidence_refs.extend(_collect_evidence_refs(row.get("quant_input_evidence") or {}))
    evidence_refs.extend(_collect_evidence_refs(predictive_revenue_inputs or {}))
    evidence_refs.extend(_collect_evidence_refs(actions))
    evidence_refs = list(dict.fromkeys(ref for ref in evidence_refs if ref))
    if not evidence_refs:
        blockers.append("evidence_lineage_missing")

    economics: Mapping[str, Any] | None = None
    risk: Mapping[str, Any] | None = None
    if not missing_quant and row.get("probability_modeled_from_verified_outcomes") is True:
        economics = expected_economics(
            probability_success=quant_inputs["probability_success"],
            conditional_revenue_cents=quant_inputs["conditional_revenue_cents"],
            fixed_cost_cents=quant_inputs["fixed_cost_cents"],
            success_cost_cents=quant_inputs["success_cost_cents"],
        ).as_dict()
        risk = risk_adjusted_score(
            expected_gross_profit_cents=economics[
                "expected_gross_profit_cents"
            ],
            downside_cents=economics["downside_if_failure_cents"],
            uncertainty=quant_inputs["uncertainty"],
            time_to_revenue_days=quant_inputs["time_to_revenue_days"],
            confidence=quant_inputs["confidence"],
        )

    erv = expected_revenue_value(dict(predictive_revenue_inputs or {}))
    nba = next_best_action_value(list(actions))
    explicit_output, output_blocker = _explicit_recommended_output_type(
        nba,
        actions,
    )
    if output_blocker:
        blockers.append(output_blocker)

    hard_research_block = any(
        blocker.startswith("signal_")
        or blocker.startswith("quant_input_missing:")
        or blocker in {
            "probability_not_backed_by_verified_outcomes",
            "evidence_lineage_missing",
            "recommended_action_output_type_invalid",
        }
        for blocker in blockers
    )

    if hard_research_block or economics is None:
        output_type = "RESEARCH_REQUIRED"
    elif float(economics["expected_gross_profit_cents"]) <= 0:
        output_type = "HOLD"
    elif explicit_output is not None:
        output_type = explicit_output
    elif _clean(normalized_signals.get("distribution_path")) == "approved_buyer_network":
        output_type = "BUYER_MATCH_REVIEW"
    else:
        output_type = "OPPORTUNITY_CREATE"

    recommended_action = nba.get("recommended_action")
    if not isinstance(recommended_action, Mapping):
        recommended_action = None

    return PredictiveRevenueJEVPacket(
        signal_id=envelope.signal_id,
        signal_type=envelope.signal_type,
        signal_truth_class=envelope.truth_class,
        signal_age_seconds=age_seconds,
        freshness=freshness,
        opportunity_key=_clean(row.get("opportunity_key")) or None,
        opportunity_class=_clean(row.get("opportunity_class")) or None,
        output_type=output_type,
        normalized_signals=normalized_signals,
        probability_success=(
            float(quant_inputs["probability_success"])
            if quant_inputs.get("probability_success") is not None
            else None
        ),
        conditional_revenue_cents=(
            float(quant_inputs["conditional_revenue_cents"])
            if quant_inputs.get("conditional_revenue_cents") is not None
            else None
        ),
        expected_revenue_cents=(
            float(economics["expected_revenue_cents"])
            if economics is not None
            else None
        ),
        expected_cost_cents=(
            float(economics["expected_cost_cents"])
            if economics is not None
            else None
        ),
        expected_gross_profit_cents=(
            float(economics["expected_gross_profit_cents"])
            if economics is not None
            else None
        ),
        risk_adjusted_score=(
            float(risk["risk_adjusted_score"])
            if risk is not None
            else None
        ),
        predictive_revenue_erv=erv,
        next_best_action=nba,
        recommended_action=dict(recommended_action) if recommended_action else None,
        blockers=tuple(dict.fromkeys(blockers)),
        evidence_refs=tuple(evidence_refs),
        value_available=economics is not None,
    )
