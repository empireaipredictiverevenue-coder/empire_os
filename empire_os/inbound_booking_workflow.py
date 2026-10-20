"""Tenant-scoped appointment and callback lifecycle, offline evidence only.

This module is not a provider adapter. A 'verified' flag is an offline claim:
production callers must authenticate provider receipts independently.
Never authorises customer calls, messages, calendar writes or revenue claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Literal

KINDS = frozenset({
    "appointment_requested", "callback_requested",
    "callback_consent_granted", "callback_consent_revoked",
    "followup_opt_out", "calendar_booking_confirmed",
    "calendar_booking_cancelled", "callback_connected",
})
ORIGINS = {
    "appointment_requested": {"verified_inbound", "operator_review"},
    "callback_requested": {"verified_inbound", "operator_review"},
    "callback_consent_granted": {"verified_inbound", "operator_review"},
    "callback_consent_revoked": {"verified_inbound", "operator_review"},
    "followup_opt_out": {"verified_inbound", "operator_review"},
    "calendar_booking_confirmed": {"calendar_adapter"},
    "calendar_booking_cancelled": {"calendar_adapter"},
    "callback_connected": {"voice_provider"},
}
BOOKING_KINDS = frozenset({"calendar_booking_confirmed", "calendar_booking_cancelled"})


def _aware(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("invalid_workflow_timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("workflow_timestamp_timezone_required")
    return dt


@dataclass(frozen=True)
class InboundWorkflowEvent:
    tenant_id: str
    event_id: str
    call_id: str
    contact_key: str
    kind: str
    occurred_at: str
    origin: Literal["verified_inbound", "operator_review", "calendar_adapter", "voice_provider"]
    evidence_ref: str
    verified: bool = False
    synthetic: bool = True
    consent_expires_at: str | None = None
    appointment_id: str | None = None
    calendar_ref: str | None = None
    appointment_starts_at: str | None = None
    appointment_ends_at: str | None = None

    def __post_init__(self) -> None:
        for field in ("tenant_id", "event_id", "call_id", "evidence_ref"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip() or len(value) > 250:
                raise ValueError(f"{field}_required")
        # HMAC-SHA256 contact pseudonyms from the trusted intake adapter;
        # never store plaintext phone/email in this event contract.
        if not isinstance(self.contact_key, str) or not re.fullmatch(r"[a-f0-9]{64}", self.contact_key):
            raise ValueError("pseudonymous_contact_key_required")
        if self.kind not in KINDS or self.origin not in ORIGINS.get(self.kind, set()):
            raise ValueError("invalid_workflow_event_origin_or_kind")
        if not isinstance(self.verified, bool) or not isinstance(self.synthetic, bool):
            raise ValueError("invalid_workflow_evidence_flags")
        when = _aware(self.occurred_at)
        if self.kind == "callback_consent_granted":
            if not self.consent_expires_at or _aware(self.consent_expires_at) <= when:
                raise ValueError("unexpired_callback_consent_required")
            if _aware(self.consent_expires_at) - when > timedelta(days=30):
                raise ValueError("callback_consent_duration_exceeded")
        elif self.consent_expires_at is not None:
            raise ValueError("consent_expiry_only_allowed_on_grant")
        if self.kind in BOOKING_KINDS:
            if not all((self.appointment_id, self.calendar_ref,
                        self.appointment_starts_at, self.appointment_ends_at)):
                raise ValueError("calendar_booking_receipt_fields_required")
            starts = _aware(self.appointment_starts_at)
            ends = _aware(self.appointment_ends_at)
            if ends <= starts or (ends - starts).total_seconds() > 24 * 3600:
                raise ValueError("invalid_calendar_booking_window")
        elif any((self.appointment_id, self.calendar_ref, self.appointment_starts_at,
                  self.appointment_ends_at)):
            raise ValueError("booking_fields_not_allowed_on_nonbooking_event")


@dataclass(frozen=True)
class WorkflowPolicy:
    tenant_id: str
    max_age_days: int = 90
    max_calls: int = 2000

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, str) or not self.tenant_id.strip():
            raise ValueError("tenant_id_required")
        for field, max_value in (("max_age_days", 365), ("max_calls", 10000)):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or not (1 <= value <= max_value):
                raise ValueError("invalid_workflow_policy")


def summarise_inbound_workflow(
    events: list[InboundWorkflowEvent] | tuple[InboundWorkflowEvent, ...],
    *,
    policy: WorkflowPolicy,
    as_of: datetime,
) -> dict:
    """Read-only, evidence-conservative lifecycle reconciliation.

    All outputs are call-level, not distinct people. No raw contact keys are
    returned. 'review_eligible' is NOT permission to contact the person.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("workflow_as_of_timezone_required")

    distinct: dict[str, InboundWorkflowEvent] = {}
    unverified_excluded = stale_excluded = future_excluded = 0
    for e in events:
        if not isinstance(e, InboundWorkflowEvent):
            raise ValueError("invalid_workflow_event")
        if e.tenant_id != policy.tenant_id:
            continue
        if e.event_id in distinct and distinct[e.event_id] != e:
            raise ValueError("conflicting_workflow_event_id")
        distinct[e.event_id] = e

    relevant: list[InboundWorkflowEvent] = []
    historical_opt_out_keys: set[str] = set()
    for e in distinct.values():
        at = _aware(e.occurred_at)
        if at > as_of:
            future_excluded += 1
        elif e.kind == "followup_opt_out" and e.verified and not e.synthetic:
            historical_opt_out_keys.add(e.contact_key)
            relevant.append(e)
        elif (as_of - at).total_seconds() > policy.max_age_days * 86400:
            stale_excluded += 1
        elif not e.verified or e.synthetic:
            unverified_excluded += 1
        else:
            relevant.append(e)
    relevant.sort(key=lambda e: (_aware(e.occurred_at), e.event_id))

    by_contact: dict[str, list[InboundWorkflowEvent]] = {}
    by_call: dict[str, list[InboundWorkflowEvent]] = {}
    for e in relevant:
        by_contact.setdefault(e.contact_key, []).append(e)
        by_call.setdefault(e.call_id, []).append(e)

    suppressed: set[str] = set(historical_opt_out_keys)
    consent: dict[str, tuple[bool, datetime | None]] = {}
    for contact_key, records in by_contact.items():
        if any(e.kind == "followup_opt_out" for e in records):
            suppressed.add(contact_key)
        current: tuple[bool, datetime | None] = (False, None)
        for e in records:
            if e.kind == "callback_consent_granted":
                current = (True, _aware(e.consent_expires_at))
            elif e.kind == "callback_consent_revoked":
                current = (False, None)
        consent[contact_key] = current

    appointment_status: dict[tuple[str, str], str] = {}
    appointment_owner: dict[tuple[str, str], str] = {}
    booking_conflicts = 0
    for e in relevant:
        if e.kind not in BOOKING_KINDS:
            continue
        identifier = (e.calendar_ref, e.appointment_id)
        owner = appointment_owner.get(identifier)
        if owner is not None and owner != e.call_id:
            booking_conflicts += 1
            appointment_status[identifier] = "conflicted"
            continue
        appointment_owner[identifier] = e.call_id
        if appointment_status.get(identifier) == "conflicted":
            continue
        appointment_status[identifier] = (
            "confirmed" if e.kind == "calendar_booking_confirmed" else "cancelled"
        )

    entries: list[dict] = []
    for call_id, records in by_call.items():
        latest_requested = max(
            (_aware(e.occurred_at) for e in records if e.kind == "appointment_requested"),
            default=None,
        )
        callback_requested = any(e.kind == "callback_requested" for e in records)
        contact_keys = {e.contact_key for e in records}
        # Calls with conflicting contact identifiers cannot qualify for any
        # callback suggestion without a human audit of the identity join.
        conflicting_contact = len(contact_keys) != 1
        contact_key = next(iter(contact_keys)) if not conflicting_contact else None
        opt_out = bool(contact_key and contact_key in suppressed)
        consent_valid = False
        if contact_key:
            granted, expiry = consent.get(contact_key, (False, None))
            consent_valid = bool(granted and expiry and as_of < expiry and not opt_out)
        bookings = [
            ident for ident, owner in appointment_owner.items() if owner == call_id
        ]
        active = sum(
            appointment_status.get(ident) == "confirmed" for ident in bookings
        )
        cancelled = sum(
            appointment_status.get(ident) == "cancelled" for ident in bookings
        )
        conflicted = sum(
            appointment_status.get(ident) == "conflicted" for ident in bookings
        )
        callback_connected = any(e.kind == "callback_connected" for e in records)
        if opt_out:
            callback_state = "suppressed_opt_out"
        elif conflicting_contact:
            callback_state = "hold_conflicting_contact_identity"
        elif callback_connected:
            callback_state = "already_connected"
        elif not callback_requested:
            callback_state = "no_callback_requested"
        elif not consent_valid:
            callback_state = "hold_consent_unverified_or_expired"
        else:
            callback_state = "operator_review_eligible"
        entries.append({
            "call_id": call_id,
            "appointment_requested": latest_requested is not None,
            "active_calendar_confirmations": active,
            "calendar_cancellations": cancelled,
            "calendar_identity_conflicts": conflicted,
            "callback_requested": callback_requested,
            "callback_state": callback_state,
            "human_review_required": callback_state == "operator_review_eligible",
            "no_customer_contact_authority": True,
            "evidence_event_ids": [e.event_id for e in records],
        })
    entries.sort(key=lambda entry: entry["call_id"])
    total_entries = len(entries)
    return {
        "tenant_id": policy.tenant_id,
        "mode": "offline_workflow_evidence_only",
        "as_of": as_of.isoformat(),
        "call_workflows_total": total_entries,
        "call_workflows_returned": min(total_entries, policy.max_calls),
        "call_workflows_overflow": max(0, total_entries - policy.max_calls),
        "appointment_requests": sum(entry["appointment_requested"] for entry in entries),
        "active_calendar_confirmations": sum(
            entry["active_calendar_confirmations"] for entry in entries
        ),
        "calendar_cancellations": sum(entry["calendar_cancellations"] for entry in entries),
        "calendar_identity_conflicts": booking_conflicts,
        "operator_callback_reviews": sum(
            entry["callback_state"] == "operator_review_eligible" for entry in entries
        ),
        "suppressed_callback_workflows": sum(
            entry["callback_state"] == "suppressed_opt_out" for entry in entries
        ),
        "unverified_events_excluded": unverified_excluded,
        "stale_events_excluded": stale_excluded,
        "future_events_excluded": future_excluded,
        "contact_keys_returned": False,
        "revenue_inferred": False,
        "outbound_sent": False,
        "bookings_created": False,
        "workflows": entries[:policy.max_calls],
    }
