"""Evidence-first commercial usage/value metering.

Recovered concepts:
- evaluation per-score / outcome billing
- hourly intelligence retainers
- PPL / PPS / PPC
- hybrid upfront / backend

This module creates billable observations only. It does not charge, settle,
recognize revenue, or mutate production state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from typing import Any


class UsageMode(str, Enum):
    EVALUATION_SCORE = "evaluation_score"
    EVALUATION_OUTCOME = "evaluation_outcome"
    HOURLY_INTELLIGENCE = "hourly_intelligence"
    PAY_PER_LEAD = "pay_per_lead"
    PAY_PER_APPOINTMENT = "pay_per_appointment"
    PAY_PER_CALL = "pay_per_call"
    HYBRID_UPFRONT = "hybrid_upfront"
    HYBRID_BACKEND = "hybrid_backend"


UNIT_BY_MODE = {
    UsageMode.EVALUATION_SCORE: "evaluation",
    UsageMode.EVALUATION_OUTCOME: "verified_outcome",
    UsageMode.HOURLY_INTELLIGENCE: "hour",
    UsageMode.PAY_PER_LEAD: "verified_lead",
    UsageMode.PAY_PER_APPOINTMENT: "verified_appointment",
    UsageMode.PAY_PER_CALL: "verified_call",
    UsageMode.HYBRID_UPFRONT: "upfront_entitlement",
    UsageMode.HYBRID_BACKEND: "verified_backend_outcome",
}


@dataclass(frozen=True)
class CommercialTermsEvidence:
    verified: bool
    source: str | None
    reference: str | None
    verified_at: str | None
    unit_price_cents: int | None = None
    currency: str = "USD"
    settlement_asset: str = "USDT"
    settlement_chain: str = "BSC"

    def blockers(self) -> tuple[str, ...]:
        blockers: list[str] = []
        if not self.verified:
            blockers.append("commercial_terms_unverified")
        if not str(self.source or "").strip():
            blockers.append("commercial_terms_source_missing")
        if not str(self.reference or "").strip():
            blockers.append("commercial_terms_reference_missing")
        if not str(self.verified_at or "").strip():
            blockers.append("commercial_terms_verified_at_missing")
        if self.unit_price_cents is None:
            blockers.append("unit_price_unknown")
        elif self.unit_price_cents < 0:
            blockers.append("unit_price_invalid")
        return tuple(blockers)


@dataclass(frozen=True)
class BillableObservation:
    mode: UsageMode
    unit: str
    quantity: str
    observed_at: str
    evidence_refs: tuple[str, ...]
    terms_verified: bool
    billing_ready: bool
    commercial_terms_source: str | None
    commercial_terms_reference: str | None
    commercial_terms_verified_at: str | None
    unit_price_cents: int | None
    calculated_amount_cents: int | None
    currency: str
    settlement_asset: str
    settlement_chain: str
    blockers: tuple[str, ...]
    event_type: str = "billable_usage_observed"
    actual_revenue: bool = False
    charge_executed: bool = False
    payment_execution: bool = False
    settlement_execution: bool = False
    revenue_recognition: bool = False
    execution_authority: str = "none"
    mode_state: str = "OBSERVE"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        return data

    def to_commercial_event(self, **ids: Any) -> dict[str, Any]:
        allowed_ids = {
            "opportunity_id",
            "job_id",
            "fulfilment_order_id",
            "prospect_id",
            "entity_id",
            "buyer_id",
            "product_id",
        }
        unknown = set(ids) - allowed_ids
        if unknown:
            raise ValueError(
                "unsupported commercial event id(s): "
                + ", ".join(sorted(unknown))
            )
        return {
            "event_type": self.event_type,
            **{key: value for key, value in ids.items() if value},
            "channel": "usage_metering",
            "actor": "empire_commercial_meter",
            "amount_cents": self.calculated_amount_cents,
            "cost_cents": None,
            "margin_cents": None,
            "payload": self.as_dict(),
            "occurred_at": self.observed_at,
        }


def _quantity(value: int | float | str | Decimal) -> Decimal:
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("quantity must be numeric") from exc
    if not quantity.is_finite() or quantity <= 0:
        raise ValueError("quantity must be positive")
    return quantity


def build_billable_observation(
    *,
    mode: UsageMode | str,
    quantity: int | float | str | Decimal,
    observed_at: str,
    evidence_refs: tuple[str, ...] | list[str],
    terms: CommercialTermsEvidence,
) -> BillableObservation:
    usage_mode = UsageMode(mode)
    qty = _quantity(quantity)
    observed = str(observed_at or "").strip()
    if not observed:
        raise ValueError("observed_at required")

    refs = tuple(
        dict.fromkeys(
            str(ref).strip()
            for ref in evidence_refs
            if str(ref).strip()
        )
    )
    if not refs:
        raise ValueError("billable observation requires evidence refs")

    blockers = list(terms.blockers())
    amount_cents: int | None = None
    billing_ready = not blockers

    if billing_ready and terms.unit_price_cents is not None:
        raw = qty * Decimal(terms.unit_price_cents)
        rounded = raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        amount_cents = int(rounded)

    return BillableObservation(
        mode=usage_mode,
        unit=UNIT_BY_MODE[usage_mode],
        quantity=format(qty.normalize(), "f"),
        observed_at=observed,
        evidence_refs=refs,
        terms_verified=terms.verified,
        billing_ready=billing_ready,
        commercial_terms_source=terms.source,
        commercial_terms_reference=terms.reference,
        commercial_terms_verified_at=terms.verified_at,
        unit_price_cents=terms.unit_price_cents,
        calculated_amount_cents=amount_cents,
        currency=str(terms.currency or "USD").upper(),
        settlement_asset=str(terms.settlement_asset or "USDT").upper(),
        settlement_chain=str(terms.settlement_chain or "BSC").upper(),
        blockers=tuple(blockers),
    )
