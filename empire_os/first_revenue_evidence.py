"""Compile Phase 3 first-revenue readiness from canonical evidence records."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from empire_os.first_revenue_proof import FirstRevenueEvidence


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _has_time(record: Mapping[str, Any], *keys: str) -> bool:
    return any(_text(record.get(key)) for key in keys)


def _ref(kind: str, record: Mapping[str, Any], *id_keys: str) -> str | None:
    for key in id_keys:
        value = _text(record.get(key))
        if value:
            return f"{kind}:{value}"
    return None


def compile_first_revenue_evidence(
    *,
    buyer: Mapping[str, Any] | None = None,
    outbound_intent: Mapping[str, Any] | None = None,
    provider_events: Sequence[Mapping[str, Any]] = (),
    agreement: Mapping[str, Any] | None = None,
    payment: Mapping[str, Any] | None = None,
    fulfilment: Mapping[str, Any] | None = None,
    outcome: Mapping[str, Any] | None = None,
    revenue_event: Mapping[str, Any] | None = None,
) -> FirstRevenueEvidence:
    """Derive proof flags from explicit canonical records only.

    Missing, ambiguous, or merely inferred evidence remains false.
    """
    buyer = dict(buyer or {})
    intent = dict(outbound_intent or {})
    agreement = dict(agreement or {})
    payment = dict(payment or {})
    fulfilment = dict(fulfilment or {})
    outcome = dict(outcome or {})
    revenue = dict(revenue_event or {})
    events = [dict(item) for item in provider_events]

    buyer_id = _text(buyer.get("buyer_id") or buyer.get("id"))
    buyer_identity_verified = bool(
        buyer_id
        and (
            _has_time(
                buyer,
                "identity_verified_at",
                "capacity_verified_at",
                "commercial_terms_verified_at",
            )
            or _bool(buyer.get("identity_verified"))
        )
    )
    commercial_terms_verified = bool(
        buyer_id
        and (
            _has_time(buyer, "commercial_terms_verified_at")
            or _bool(buyer.get("commercial_terms_verified"))
        )
    )

    intent_id = _text(intent.get("intent_id") or intent.get("id"))
    intent_status = _text(intent.get("status")).lower()
    human_approval_recorded = bool(
        intent_id
        and intent_status == "approved"
        and (
            _has_time(intent, "approved_at", "reviewed_at")
            or _text(intent.get("approved_by"))
        )
    )
    outbound_intent_approved = bool(
        intent_id
        and intent_status == "approved"
        and human_approval_recorded
    )

    verified_provider_events = [
        event
        for event in events
        if _bool(event.get("signature_verified"))
        or _bool(event.get("provider_verified"))
        or _text(event.get("verification_state")).lower() == "verified"
    ]
    event_types = {
        _text(event.get("event_type")).lower()
        for event in verified_provider_events
    }
    send_evidence_verified = bool(
        event_types.intersection({"sent", "send_attempt", "delivered"})
    )
    delivery_evidence_verified = "delivered" in event_types

    agreement_state = _text(
        agreement.get("state") or agreement.get("status")
    ).lower()
    agreement_evidence_verified = bool(
        _ref("agreement", agreement, "agreement_id", "id")
        and agreement_state in {
            "accepted",
            "agreed",
            "signed",
            "approved",
            "confirmed",
        }
        and (
            _has_time(
                agreement,
                "accepted_at",
                "signed_at",
                "verified_at",
                "updated_at",
            )
            or _bool(agreement.get("evidence_verified"))
        )
    )

    payment_state = _text(
        payment.get("verification_state")
        or payment.get("status")
        or payment.get("decision")
    ).lower()
    payment_chain = _text(
        payment.get("chain") or payment.get("network")
    ).lower()
    payment_asset = _text(
        payment.get("asset") or payment.get("token")
    ).upper()
    usdt_bsc_payment_verified = bool(
        _ref("payment", payment, "payment_id", "request_id", "id")
        and payment_state in {"verified", "confirmed"}
        and payment_chain in {
            "bsc",
            "bnb smart chain",
            "binance smart chain",
            "56",
        }
        and payment_asset == "USDT"
        and (
            _has_time(payment, "verified_at", "confirmed_at")
            or _bool(payment.get("onchain_verified"))
        )
    )

    fulfilment_state = _text(
        fulfilment.get("state") or fulfilment.get("status")
    ).lower()
    fulfilment_delivery_verified = bool(
        _ref("fulfilment", fulfilment, "fulfilment_order_id", "id")
        and fulfilment_state in {"delivered", "confirmed", "completed"}
        and (
            _has_time(
                fulfilment,
                "delivered_at",
                "confirmed_at",
                "updated_at",
            )
            or _bool(fulfilment.get("delivery_verified"))
        )
    )

    outcome_evidence_verified = bool(
        _ref("outcome", outcome, "outcome_id", "id")
        and (
            _has_time(outcome, "recorded_at", "observed_at")
            or _bool(outcome.get("evidence_verified"))
        )
    )

    revenue_recognized = bool(
        _ref("revenue", revenue, "event_id", "id")
        and _text(revenue.get("event_type")).lower() == "revenue_recognized"
        and revenue.get("actual_revenue") is True
        and int(revenue.get("amount_cents") or revenue.get("actual_revenue_cents") or 0) > 0
    )

    refs: list[str] = []
    for ref in (
        _ref("buyer", buyer, "buyer_id", "id"),
        _ref("outbound", intent, "intent_id", "id"),
        *(
            _ref("provider_event", event, "event_id", "id", "provider_message_id")
            for event in verified_provider_events
        ),
        _ref("agreement", agreement, "agreement_id", "id"),
        _ref("payment", payment, "payment_id", "request_id", "id"),
        _ref("fulfilment", fulfilment, "fulfilment_order_id", "id"),
        _ref("outcome", outcome, "outcome_id", "id"),
        _ref("revenue", revenue, "event_id", "id"),
    ):
        if ref and ref not in refs:
            refs.append(ref)

    if not refs:
        refs.append("evidence:none")

    return FirstRevenueEvidence(
        buyer_identity_verified=buyer_identity_verified,
        commercial_terms_verified=commercial_terms_verified,
        human_approval_recorded=human_approval_recorded,
        outbound_intent_approved=outbound_intent_approved,
        send_evidence_verified=send_evidence_verified,
        delivery_evidence_verified=delivery_evidence_verified,
        agreement_evidence_verified=agreement_evidence_verified,
        usdt_bsc_payment_verified=usdt_bsc_payment_verified,
        fulfilment_delivery_verified=fulfilment_delivery_verified,
        outcome_evidence_verified=outcome_evidence_verified,
        revenue_recognized=revenue_recognized,
        evidence_refs=tuple(refs),
    )
