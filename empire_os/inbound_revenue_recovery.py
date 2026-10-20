"""Deterministic, offline-first inbound revenue recovery.

This layer never places calls, confirms bookings, bills clients or claims
revenue without verified provider and recovery evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

CALL_STATUSES = frozenset({"ringing", "answered", "unanswered", "busy", "rejected", "failed", "completed"})
MISSED_STATUSES = frozenset({"unanswered", "busy", "rejected"})
ACTION_KINDS = frozenset({
    "callback_requested", "callback_connected", "booking_requested",
    "booking_confirmed", "invoice_paid", "human_transfer", "followup_opt_out",
})
VERIFIED_ORIGINS = {
    "callback_connected": "provider",
    "booking_confirmed": "calendar",
    "invoice_paid": "payments",
}


@dataclass(frozen=True)
class RecoveryEvent:
    tenant_id: str
    event_id: str
    call_id: str
    occurred_at: str
    kind: str
    origin: Literal["provider", "operator", "calendar", "payments"]
    evidence_ref: str = ""
    amount_minor: int | None = None
    currency: str = ""
    verified: bool = False
    synthetic: bool = True  # Caller must explicitly mark trusted production evidence non-synthetic.

    def __post_init__(self) -> None:
        for attr in ("tenant_id", "event_id", "call_id"):
            if not isinstance(getattr(self, attr), str) or not getattr(self, attr).strip():
                raise ValueError(f"{attr}_required")
        if not isinstance(self.verified, bool) or not isinstance(self.synthetic, bool):
            raise ValueError("evidence_flags_must_be_boolean")
        if self.kind not in CALL_STATUSES | ACTION_KINDS:
            raise ValueError("unsupported_recovery_event")
        if self.origin not in {"provider", "operator", "calendar", "payments"}:
            raise ValueError("unsupported_recovery_origin")
        try:
            stamp = datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise ValueError("invalid_event_timestamp") from exc
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("timezone_required")
        if self.kind in CALL_STATUSES and self.origin != "provider":
            raise ValueError("call_status_requires_provider")
        required_origin = VERIFIED_ORIGINS.get(self.kind)
        if required_origin and (self.origin != required_origin or not self.verified or not self.evidence_ref.strip()):
            raise ValueError(f"{self.kind}_requires_verified_{required_origin}_receipt")
        if self.kind == "invoice_paid":
            if isinstance(self.amount_minor, bool) or not isinstance(self.amount_minor, int) or self.amount_minor <= 0:
                raise ValueError("paid_amount_minor_required")
            if len(self.currency) != 3 or not self.currency.isalpha() or self.currency != self.currency.upper():
                raise ValueError("iso_currency_required")
        elif self.amount_minor is not None:
            raise ValueError("amount_only_permitted_for_verified_payment")


@dataclass(frozen=True)
class TenantReceptionProfile:
    tenant_id: str
    business_name: str
    vertical: Literal["home_services", "hospitality", "professional_services", "general"] = "general"
    services: tuple[str, ...] = ()
    booking_integration_verified: bool = False
    human_transfer_configured: bool = False
    callback_capture_allowed: bool = False
    locale: str = "en-GB"

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.business_name.strip():
            raise ValueError("tenant_and_business_required")


@dataclass(frozen=True)
class ReceptionDecision:
    action: str
    spoken_text: str
    booking_confirmed: bool = False
    outbound_authorized: bool = False
    reason: str = ""


def plan_reception_response(profile: TenantReceptionProfile, intent: str) -> ReceptionDecision:
    """Deterministic policy, no booking/availability or outbound execution."""
    normalized = intent.strip().lower()
    if normalized in {"opt_out", "stop", "privacy"}:
        return ReceptionDecision(
            "honour_opt_out",
            "Understood. I will stop this conversation. Please ask the business to record your opt-out request.",
            reason="suppression_requires_authorized_workflow",
        )
    if normalized in {"emergency", "immediate_danger"}:
        return ReceptionDecision(
            "urgent_human_escalation",
            "I am an AI assistant and cannot provide emergency help. "
            "If anyone is in immediate danger, contact local emergency services now.",
            reason="never_handle_emergency_as_sales_lead",
        )
    if normalized in {"human", "complaint", "sensitive"}:
        if profile.human_transfer_configured:
            return ReceptionDecision(
                "offer_human_transfer",
                f"I am the AI assistant for {profile.business_name}. "
                "I can try to connect you to the team. Would you like that?",
                reason="transfer_needs_separate_live_authorization",
            )
        return ReceptionDecision(
            "human_followup_needed",
            f"I am the AI assistant for {profile.business_name}. "
            "A team member will need to help with this. Would you like to request a callback?",
            reason="no_transfer_integration",
        )
    if normalized in {"book", "appointment", "reservation"}:
        if profile.booking_integration_verified:
            return ReceptionDecision(
                "check_booking_availability",
                f"I am the AI assistant for {profile.business_name}. "
                "What day suits you? Any appointment must be checked and confirmed before it is booked.",
                reason="verify_availability_before_confirmation",
            )
        return ReceptionDecision(
            "booking_request_only",
            f"I am the AI assistant for {profile.business_name}. "
            "I can help you prepare an appointment request, but cannot confirm a time yet.",
            reason="booking_not_connected",
        )
    if normalized in {"callback", "missed_call"}:
        if not profile.callback_capture_allowed:
            return ReceptionDecision(
                "request_consent_for_followup",
                f"I am the AI assistant for {profile.business_name}. "
                "Would you like someone from the team to contact you?",
                reason="no_callback_capture_permission",
            )
        return ReceptionDecision(
            "request_callback_details",
            f"I am the AI assistant for {profile.business_name}. "
            "Would you like to make a callback request for the team to review?",
            reason="request_only_no_outbound_guarantee",
        )
    return ReceptionDecision(
        "qualify_inbound_request",
        f"Hello, you have reached {profile.business_name}'s AI assistant. "
        "How can I help you today?",
        reason="disclose_ai_and_avoid_unverified_claims",
    )


@dataclass
class RecoveryLedger:
    """Idempotent in-memory ledger for proof and offline replays."""
    events: dict[tuple[str, str], RecoveryEvent] = field(default_factory=dict)

    def append(self, event: RecoveryEvent) -> bool:
        key = (event.tenant_id, event.event_id)
        prior = self.events.get(key)
        if prior is not None:
            if prior != event:
                raise ValueError("conflicting_duplicate_event_id")
            return False
        self.events[key] = event
        return True

    def report(self, tenant_id: str) -> dict:
        if not tenant_id:
            raise ValueError("tenant_id_required")
        events = sorted(
            (e for e in self.events.values() if e.tenant_id == tenant_id and not e.synthetic),
            key=lambda e: (datetime.fromisoformat(e.occurred_at.replace("Z", "+00:00")), e.event_id),
        )
        calls: dict[str, list[RecoveryEvent]] = {}
        for e in events:
            calls.setdefault(e.call_id, []).append(e)
        missed_calls = answered_calls = callback_requests = connections = bookings = recovered = 0
        paid: dict[str, int] = {}
        seen_receipts: set[tuple[str, str]] = set()
        seen_recovery_receipts: set[tuple[str, str]] = set()
        seen_booking_receipts: set[str] = set()
        seen_connection_receipts: set[str] = set()
        for call_events in calls.values():
            missed_at = min(
                (datetime.fromisoformat(e.occurred_at.replace("Z", "+00:00"))
                 for e in call_events if e.kind in MISSED_STATUSES),
                default=None,
            )
            missed_calls += int(missed_at is not None)
            answered_calls += int(any(e.kind == "answered" for e in call_events))
            callback_requests += int(any(e.kind == "callback_requested" for e in call_events))
            for e in call_events:
                if e.kind == "callback_connected" and e.evidence_ref not in seen_connection_receipts:
                    seen_connection_receipts.add(e.evidence_ref)
                    connections += 1
                if e.kind == "booking_confirmed" and e.evidence_ref not in seen_booking_receipts:
                    seen_booking_receipts.add(e.evidence_ref)
                    bookings += 1
            def later_than_missed(e: RecoveryEvent) -> bool:
                return bool(
                    missed_at is not None
                    and datetime.fromisoformat(e.occurred_at.replace("Z", "+00:00")) > missed_at
                )
            qualifying_recovery = [
                e for e in call_events
                if e.kind in {"callback_connected", "booking_confirmed"}
                and later_than_missed(e)
                and (e.kind, e.evidence_ref) not in seen_recovery_receipts
            ]
            for e in qualifying_recovery:
                seen_recovery_receipts.add((e.kind, e.evidence_ref))
            recovered += int(bool(qualifying_recovery))
            if not qualifying_recovery:
                continue
            recovery_at = min(datetime.fromisoformat(e.occurred_at.replace("Z", "+00:00")) for e in qualifying_recovery)
            for e in call_events:
                if (e.kind != "invoice_paid" or not e.verified
                    or datetime.fromisoformat(e.occurred_at.replace("Z", "+00:00")) < recovery_at):
                    continue
                receipt = (e.origin, e.evidence_ref)
                if receipt in seen_receipts:
                    continue
                seen_receipts.add(receipt)
                paid[e.currency] = paid.get(e.currency, 0) + (e.amount_minor or 0)
        return {
            "tenant_id": tenant_id,
            "mode": "offline_evidence_only",
            "calls_observed": len(calls),
            "missed_calls": missed_calls,
            "answered_calls": answered_calls,
            "callback_requests": callback_requests,
            "verified_connections": connections,
            "confirmed_bookings": bookings,
            "verified_recovered_calls": recovered,
            "verified_paid_recovery_minor_by_currency": dict(sorted(paid.items())),
            "estimated_revenue_minor_by_currency": {},
            "database_writes": False,
            "outbound_sent": False,
            "live_routing_modified": False,
        }
