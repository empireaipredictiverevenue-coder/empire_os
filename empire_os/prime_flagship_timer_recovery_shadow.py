"""Original EmpireOS PRIME/EmpireDB timer ledger recovery *shadow*.

Pure, synthetic-only reconstruction of a proposed immutable EmpireDB timer
event stream. No database, scheduler, phone, notification, background task or
actual delivery is accessed. Caller event values are assertions, NOT signed
owner evidence. Real execution and production release are always OFF.

State machine captures critical crash/cancellation/idempotency conditions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any, Mapping, Sequence

SCHEMA = "empire.prime.original_timer_recovery_shadow.v1"
MAX_EVENTS = 32
MAX_HORIZON_SECONDS = 3600
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ORIGINAL_KINDS = frozenset({
    "TIMER_CREATED", "TIMER_CANCELLED", "DISPATCH_CLAIMED",
    "PROVIDER_ACCEPTED_REPORTED", "PROVIDER_DELIVERED_REPORTED",
    "PROVIDER_FAILED_REPORTED",
})
FIELDS = frozenset({
    "tenant_id", "timer_digest", "event_digest", "seq", "kind",
    "occurred_at", "due_at", "duration_seconds", "provider_receipt_digest",
    "synthetic_fixture_only",
})


class TimerRecoveryHold(ValueError):
    pass


def _utc(value: Any) -> datetime:
    if type(value) is not str or not 20 <= len(value) <= 40:
        raise TimerRecoveryHold("bounded_timezone_aware_utc_timestamp_required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        raise TimerRecoveryHold("valid_timezone_aware_timestamp_required") from None
    if dt.utcoffset() is None:
        raise TimerRecoveryHold("timezone_aware_timestamp_required")
    return dt.astimezone(timezone.utc)


def _payload(value: Any, tenant_id: str, timer_digest: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != FIELDS:
        raise TimerRecoveryHold("exact_original_minimal_event_schema_required")
    if value["tenant_id"] != tenant_id or value["timer_digest"] != timer_digest:
        raise TimerRecoveryHold("cross_tenant_or_timer_event_refused")
    if value["synthetic_fixture_only"] is not True:
        raise TimerRecoveryHold("real_owner_event_not_authorized_in_shadow")
    if (type(value["event_digest"]) is not str
        or SHA256.fullmatch(value["event_digest"]) is None
        or type(value["seq"]) is not int or not 1 <= value["seq"] <= MAX_EVENTS
        or value["kind"] not in ORIGINAL_KINDS):
        raise TimerRecoveryHold("bounded_event_nonce_sequence_kind_required")
    if (value["due_at"] is not None and type(value["due_at"]) is not str
        or value["duration_seconds"] is not None
           and type(value["duration_seconds"]) is not int
        or value["provider_receipt_digest"] is not None
           and (type(value["provider_receipt_digest"]) is not str
                or SHA256.fullmatch(value["provider_receipt_digest"]) is None)):
        raise TimerRecoveryHold("bounded_event_purpose_fields_required")
    return value


def replay_original_timer_shadow(
    *, tenant_id: str, timer_digest: str,
    original_empiredb_event_rows: Sequence[Mapping[str, Any]],
    as_of: datetime,
) -> dict[str, Any]:
    """Derive a timer state from immutable hypothetical DB-compatible events.

    Does NOT independently verify the DB readback, signatures or provider
    delivery. Simulated restart recovery is replay of the same fixture rows
    in a new process. Claimed-but-unacknowledged work is NEVER auto-fired.
    """
    if type(tenant_id) is not str or re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        tenant_id,
    ) is None:
        raise TimerRecoveryHold("tenant_uuid_scope_required")
    if type(timer_digest) is not str or SHA256.fullmatch(timer_digest) is None:
        raise TimerRecoveryHold("original_purpose_keyed_timer_digest_required")
    if (type(original_empiredb_event_rows) not in (list, tuple)
        or not 1 <= len(original_empiredb_event_rows) <= MAX_EVENTS):
        raise TimerRecoveryHold("bounded_nonempty_original_event_stream_required")
    if (not isinstance(as_of, datetime) or as_of.utcoffset() is None):
        raise TimerRecoveryHold("timezone_aware_replay_clock_required")
    now = as_of.astimezone(timezone.utc)
    state: str | None = None
    due: datetime | None = None
    created_at: datetime | None = None
    last: datetime | None = None
    seen: set[str] = set()
    claim_seq: int | None = None
    provider_report_digest: str | None = None
    duration: int | None = None
    for expected, row in enumerate(original_empiredb_event_rows, 1):
        event = _payload(row, tenant_id, timer_digest)
        if event["seq"] != expected or event["event_digest"] in seen:
            raise TimerRecoveryHold("atomic_ordered_event_replay_required")
        seen.add(event["event_digest"])
        when = _utc(event["occurred_at"])
        if when > now + timedelta(minutes=1):
            raise TimerRecoveryHold("future_evidence_not_accepted")
        if last is not None and when < last:
            raise TimerRecoveryHold("out_of_order_event_timestamps_refused")
        last = when
        kind = event["kind"]
        event_due = event["due_at"]
        seconds = event["duration_seconds"]
        receipt = event["provider_receipt_digest"]
        if expected == 1:
            if kind != "TIMER_CREATED":
                raise TimerRecoveryHold("first_event_must_create_original_timer")
            if type(seconds) is not int or not 1 <= seconds <= MAX_HORIZON_SECONDS:
                raise TimerRecoveryHold("bounded_original_timer_duration_required")
            if receipt is not None or event_due is None:
                raise TimerRecoveryHold("created_event_due_without_receipt_required")
            due = _utc(event_due)
            if due <= when or abs((due - when).total_seconds() - seconds) > 1:
                raise TimerRecoveryHold("due_time_must_match_bounded_duration")
            created_at = when
            duration = seconds
            state = "SCHEDULED_WAITING"
            continue
        if event_due is not None or seconds is not None:
            raise TimerRecoveryHold("immutable_original_timer_schedule_refused")
        if kind in ("TIMER_CREATED",):
            raise TimerRecoveryHold("duplicate_timer_creation_refused")
        if kind == "TIMER_CANCELLED":
            if state != "SCHEDULED_WAITING" or when >= due:
                raise TimerRecoveryHold("cancellation_after_due_or_claim_not_confirmed")
            state = "CANCELLED_BEFORE_DISPATCH"
        elif kind == "DISPATCH_CLAIMED":
            if state != "SCHEDULED_WAITING" or when < due:
                raise TimerRecoveryHold("dispatch_requires_due_uncancelled_timer")
            if receipt is not None:
                raise TimerRecoveryHold("provider_receipt_not_part_of_claim")
            state = "CLAIMED_RECONCILIATION_REQUIRED"
            claim_seq = expected
        elif kind in ("PROVIDER_ACCEPTED_REPORTED",
                      "PROVIDER_DELIVERED_REPORTED",
                      "PROVIDER_FAILED_REPORTED"):
            if receipt is None or state not in (
                "CLAIMED_RECONCILIATION_REQUIRED",
                "PROVIDER_ACCEPTED_NOT_DELIVERED",
            ):
                raise TimerRecoveryHold("original_provider_report_after_claim_required")
            if kind == "PROVIDER_ACCEPTED_REPORTED":
                if state != "CLAIMED_RECONCILIATION_REQUIRED":
                    raise TimerRecoveryHold("duplicate_provider_acceptance_refused")
                state = "PROVIDER_ACCEPTED_NOT_DELIVERED"
            elif kind == "PROVIDER_DELIVERED_REPORTED":
                if state != "PROVIDER_ACCEPTED_NOT_DELIVERED":
                    raise TimerRecoveryHold("delivery_requires_prior_provider_acceptance")
                state = "DELIVERY_REPORTED_NOT_INDEPENDENTLY_VERIFIED"
            else:
                state = "DELIVERY_FAILED_REPORTED_NO_AUTO_RETRY"
            provider_report_digest = receipt
        else:
            raise TimerRecoveryHold("unexpected_original_timer_event")
        if kind == "TIMER_CANCELLED" and receipt is not None:
            raise TimerRecoveryHold("cancel_cannot_forge_delivery_receipt")
    assert due is not None and created_at is not None and duration is not None
    if state == "SCHEDULED_WAITING" and now >= due:
        state = "DUE_UNCLAIMED_REQUIRES_ATOMIC_DB_CLAIM"
    return {
        "schema_version": SCHEMA,
        "mode": "SIMULATION",
        "status": state,
        "event_count": len(seen),
        "created_due_seconds": duration,
        "synthetic_timer_digest": timer_digest,
        "original_tenant_uuid_fixture": tenant_id,
        "claim_seq": claim_seq,
        "provider_receipt_reported_not_verified": provider_report_digest is not None,
        "original_db_consistency_reconstructed_not_authenticated": True,
        "durable_original_empiredb_rows_independently_verified": False,
        "source_owner_consent_verified": False,
        "current_user_device_identity_verified": False,
        "claim_atomicity_proven_by_a_real_database": False,
        "actual_provider_notification_sent": False,
        "actual_provider_delivery_verified": False,
        "model_training": False,
        "original_empiredb_writes": False,
        "execution_authority": "none",
    }


def planned_next_original_timer_action(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Operator plan only. A return value cannot claim/send/cancel anything."""
    if (type(packet) is not dict
        or packet.get("schema_version") != SCHEMA
        or packet.get("mode") != "SIMULATION"
        or packet.get("durable_original_empiredb_rows_independently_verified") is not False
        or packet.get("source_owner_consent_verified") is not False
        or packet.get("claim_atomicity_proven_by_a_real_database") is not False
        or packet.get("actual_provider_notification_sent") is not False
        or packet.get("actual_provider_delivery_verified") is not False
        or packet.get("original_empiredb_writes") is not False
        or packet.get("execution_authority") != "none"):
        raise TimerRecoveryHold("untrusted_original_timer_replay_projection")
    state = packet.get("status")
    code = {
        "SCHEDULED_WAITING": "WAIT_FOR_ORIGINAL_DUE_TIMESTAMP",
        "DUE_UNCLAIMED_REQUIRES_ATOMIC_DB_CLAIM": "HOLD_FOR_OWNER_APPROVED_ATOMIC_DB_CLAIM",
        "CANCELLED_BEFORE_DISPATCH": "STOP_NO_NOTIFICATION",
        "CLAIMED_RECONCILIATION_REQUIRED": "STOP_AND_RECONCILE_PROVIDER_BEFORE_RETRY",
        "PROVIDER_ACCEPTED_NOT_DELIVERED": "STOP_PENDING_INDEPENDENT_DELIVERY_RECEIPT",
        "DELIVERY_REPORTED_NOT_INDEPENDENTLY_VERIFIED": "STOP_VERIFY_DELIVERY_SOURCE",
        "DELIVERY_FAILED_REPORTED_NO_AUTO_RETRY": "STOP_MANUAL_DELIVERY_REVIEW",
    }.get(state)
    if code is None:
        raise TimerRecoveryHold("unrecognised_original_timer_recovery_state")
    return {
        "schema_version": "empire.prime.original_timer_next_step_shadow.v1",
        "mode": "SIMULATION",
        "recommended_nonexecuting_step": code,
        "automated_retry_allowed": False,
        "contact_permission_granted": False,
        "notification_sent": False,
        "execution_authority": "none",
    }


def founder_timer_recovery_status(packet: Mapping[str, Any] | None) -> dict[str, Any]:
    """Source-private presentation, no tenant/user/key/provider identifiers."""
    if packet is None:
        return {
            "schema_version": "empire.prime.founder_timer_recovery.v1",
            "mode": "SIMULATION", "status": "NOT_CONNECTED",
            "real_notification_delivery_verified": False,
            "execution_authority": "none",
        }
    next_step = planned_next_original_timer_action(packet)
    return {
        "schema_version": "empire.prime.founder_timer_recovery.v1",
        "mode": "SIMULATION",
        "status": packet["status"],
        "nonexecuting_recovery_plan": next_step["recommended_nonexecuting_step"],
        "real_notification_delivery_verified": False,
        "execution_authority": "none",
    }
