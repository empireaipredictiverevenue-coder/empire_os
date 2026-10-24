"""Original EmpireOS PRIME: provider receipt reconciliation for synthetic timers.

No provider connection, transport, user, phone, device, customer data, DB
writer, or secret persistence. HMAC here is an *injectable fake provider*
authentication rehearsal; it cannot attest any real push/SMS/email provider,
user consent or delivery. The caller's original replay snapshot is itself
untrusted and is cross-checked for conservative non-execution conditions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
import json
import re
from typing import Any, Mapping, Sequence

from empire_os.prime_flagship_timer_recovery_shadow import (
    SCHEMA as TIMER_SCHEMA, TimerRecoveryHold,
)

SCHEMA = "empire.prime.synthetic_provider_reconciliation.v1"
PROVIDER = "synthetic_local_receipt_fixture"
SHA = re.compile(r"^[0-9a-f]{64}$")
KEY = re.compile(r"^[0-9a-f]{64}$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
FIELDS = frozenset({
    "schema_version", "provider", "tenant_id", "timer_digest",
    "claim_event_digest", "delivery_reference_digest",
    "receipt_nonce", "status_code", "occurred_at", "synthetic_only",
    "signature_hex",
})
STATUS = frozenset({"ACCEPTED", "DELIVERED", "FAILED"})


class ProviderReconciliationHold(ValueError):
    pass


def _time(value: Any) -> datetime:
    if type(value) is not str or len(value) > 40 or len(value) < 20:
        raise ProviderReconciliationHold("exact_utc_receipt_timestamp_required")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        raise ProviderReconciliationHold("invalid_utc_receipt_timestamp") from None
    if moment.utcoffset() != timedelta(0):
        raise ProviderReconciliationHold("receipt_timestamp_must_be_utc")
    return moment.astimezone(timezone.utc)


def _canonical(r: Mapping[str, Any]) -> bytes:
    content = {k: r[k] for k in sorted(FIELDS - {"signature_hex"})}
    return json.dumps(
        content,sort_keys=True,separators=(",",":"),ensure_ascii=True,
    ).encode("utf-8")


def reconcile_synthetic_provider_receipts(
    *, original_timer_replay: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    fixture_hmac_key: bytes,
    expected_claim_event_digest: str,
    expected_delivery_reference_digest: str,
    as_of: datetime,
) -> dict[str, Any]:
    """Verify fake HMAC, replay/binding/temporal constraints; never send.

    The injected test-only secret does NOT represent a production credential.
    Any real provider integration needs an independent original owner-managed
    signature scheme, API rights, receipts/endpoint verification and audit.
    """
    if (type(original_timer_replay) is not dict
        or original_timer_replay.get("schema_version") != TIMER_SCHEMA
        or original_timer_replay.get("mode") != "SIMULATION"
        or original_timer_replay.get("status") not in (
            "CLAIMED_RECONCILIATION_REQUIRED", "PROVIDER_ACCEPTED_NOT_DELIVERED",
            "DELIVERY_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
            "DELIVERY_FAILED_REPORTED_NO_AUTO_RETRY",
        )
        or original_timer_replay.get("claim_seq") != 2
        or original_timer_replay.get("event_count") not in (2,3,4)
        or original_timer_replay.get("durable_original_empiredb_rows_independently_verified") is not False
        or original_timer_replay.get("source_owner_consent_verified") is not False
        or original_timer_replay.get("actual_provider_notification_sent") is not False
        or original_timer_replay.get("actual_provider_delivery_verified") is not False
        or original_timer_replay.get("original_empiredb_writes") is not False
        or original_timer_replay.get("execution_authority") != "none"):
        raise ProviderReconciliationHold("original_nonexecuting_timer_replay_required")
    tenant = original_timer_replay.get("original_tenant_uuid_fixture")
    timer = original_timer_replay.get("synthetic_timer_digest")
    if (type(tenant) is not str or UUID.fullmatch(tenant) is None
        or type(timer) is not str or SHA.fullmatch(timer) is None):
        raise ProviderReconciliationHold("original_tenant_timer_scope_required")
    if (type(expected_claim_event_digest) is not str
        or SHA.fullmatch(expected_claim_event_digest) is None
        or type(expected_delivery_reference_digest) is not str
        or SHA.fullmatch(expected_delivery_reference_digest) is None
        or expected_claim_event_digest == expected_delivery_reference_digest):
        raise ProviderReconciliationHold("bound_opaque_claim_and_delivery_reference_required")
    if (type(fixture_hmac_key) is not bytes
        or not 32 <= len(fixture_hmac_key) <= 128
        or fixture_hmac_key in (b"0"*32,b"x"*32)):
        raise ProviderReconciliationHold("bounded_nontrivial_synthetic_receipt_secret_required")
    if (not isinstance(as_of,datetime) or as_of.utcoffset() is None):
        raise ProviderReconciliationHold("timezone_aware_receipt_review_clock_required")
    if (type(receipts) not in (tuple,list) or len(receipts) > 2):
        raise ProviderReconciliationHold("bounded_synthetic_provider_receipts_required")
    now = as_of.astimezone(timezone.utc)
    seen: set[str] = set()
    stages: list[str] = []
    for item in receipts:
        if type(item) is not dict or set(item) != FIELDS:
            raise ProviderReconciliationHold("exact_privacy_minimal_provider_receipt_required")
        if (item["schema_version"] != "empire.prime.synthetic_provider_receipt.v1"
            or item["provider"] != PROVIDER
            or item["synthetic_only"] is not True
            or type(item["tenant_id"]) is not str or item["tenant_id"] != tenant
            or type(item["timer_digest"]) is not str or item["timer_digest"] != timer
            or type(item["claim_event_digest"]) is not str
            or item["claim_event_digest"] != expected_claim_event_digest
            or type(item["delivery_reference_digest"]) is not str
            or item["delivery_reference_digest"] != expected_delivery_reference_digest):
            raise ProviderReconciliationHold("fake_provider_or_binding_scope_mismatch")
        if (type(item["receipt_nonce"]) is not str
            or SHA.fullmatch(item["receipt_nonce"]) is None
            or item["receipt_nonce"] in seen):
            raise ProviderReconciliationHold("synthetic_receipt_replayed_or_malformed")
        if type(item["status_code"]) is not str or item["status_code"] not in STATUS:
            raise ProviderReconciliationHold("unknown_fake_provider_delivery_status")
        at = _time(item["occurred_at"])
        if at > now + timedelta(minutes=1) or at < now - timedelta(hours=24):
            raise ProviderReconciliationHold("receipt_outside_bounded_review_window")
        if type(item["signature_hex"]) is not str or SHA.fullmatch(item["signature_hex"]) is None:
            raise ProviderReconciliationHold("missing_synthetic_receipt_signature")
        computed = hmac_new(fixture_hmac_key,_canonical(item),"sha256").hexdigest()
        if not compare_digest(item["signature_hex"],computed):
            raise ProviderReconciliationHold("synthetic_receipt_signature_mismatch")
        if stages and at < _time(receipts[len(stages)-1]["occurred_at"]):
            raise ProviderReconciliationHold("out_of_order_synthetic_receipt_time")
        seen.add(item["receipt_nonce"])
        stages.append(item["status_code"])
    if stages and (stages[0] not in ("ACCEPTED","FAILED")
                   or len(stages)==2 and
                   (stages[0]!="ACCEPTED" or stages[1] not in ("DELIVERED","FAILED"))):
        raise ProviderReconciliationHold("illegal_synthetic_provider_status_transition")
    if (len(stages)==1 and stages[0]=="DELIVERED"):
        raise ProviderReconciliationHold("delivery_requires_previous_provider_acceptance")
    if (original_timer_replay["status"]=="DELIVERY_FAILED_REPORTED_NO_AUTO_RETRY"
        and stages and stages[-1]!="FAILED"):
        raise ProviderReconciliationHold("prior_failure_cannot_promote_to_delivered")
    if (original_timer_replay["status"]=="DELIVERY_REPORTED_NOT_INDEPENDENTLY_VERIFIED"
        and stages and stages[-1]=="FAILED"):
        raise ProviderReconciliationHold("contradictory_terminal_provider_receipt")
    if not stages:
        state = "NO_RECEIPT_UNKNOWN_NOT_FAILED"
        decision = "STOP_NO_RESEND_RECONCILE_ORIGINAL_PROVIDER"
    elif stages[-1]=="ACCEPTED":
        state = "SYNTHETIC_PROVIDER_ACCEPTED_NOT_DELIVERED"
        decision = "STOP_AWAIT_VERIFIABLE_DEVICE_RECEIPT"
    elif stages[-1]=="DELIVERED":
        state = "SYNTHETIC_RECEIPT_CHAIN_VALID_NOT_REAL_DELIVERY"
        decision = "HOLD_FOR_ORIGINAL_PROVIDER_OWNER_ATTESTATION"
    else:
        state = "SYNTHETIC_PROVIDER_FAILURE_TERMINAL_NO_RETRY"
        decision = "STOP_MANUAL_PROVIDER_REVIEW_NO_AUTO_RESEND"
    return {
        "schema_version": SCHEMA,
        "mode": "SIMULATION",
        "status": state,
        "fictional_receipt_count": len(stages),
        "synthetic_signature_checks_passed": len(stages),
        "fake_provider_signature_not_real_source_attestation": True,
        "synthetic_receipt_chain_consistent": True,
        "nonexecuting_recovery_decision": decision,
        "verified_real_provider_delivery": False,
        "verified_real_user_device_receipt": False,
        "current_user_consent_verified": False,
        "actual_provider_contact_or_transport_used": False,
        "outbound_notification_sent": False,
        "automatic_retry_permitted": False,
        "original_empiredb_writes": False,
        "real_customer_data_seen": False,
        "execution_authority": "none",
    }


def founder_provider_receipt_reconciliation(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Founder-safe projection never includes original IDs, signatures or keys."""
    if value is None:
        return {
            "schema_version": "empire.prime.founder_provider_reconciliation.v1",
            "mode": "SIMULATION", "status": "NOT_CONNECTED",
            "verified_real_provider_delivery": False,
            "execution_authority": "none",
        }
    valid = {
        "schema_version","mode","status","fictional_receipt_count",
        "synthetic_signature_checks_passed",
        "fake_provider_signature_not_real_source_attestation",
        "synthetic_receipt_chain_consistent","nonexecuting_recovery_decision",
        "verified_real_provider_delivery","verified_real_user_device_receipt",
        "current_user_consent_verified","actual_provider_contact_or_transport_used",
        "outbound_notification_sent","automatic_retry_permitted",
        "original_empiredb_writes","real_customer_data_seen","execution_authority",
    }
    statuses={
        "NO_RECEIPT_UNKNOWN_NOT_FAILED",
        "SYNTHETIC_PROVIDER_ACCEPTED_NOT_DELIVERED",
        "SYNTHETIC_RECEIPT_CHAIN_VALID_NOT_REAL_DELIVERY",
        "SYNTHETIC_PROVIDER_FAILURE_TERMINAL_NO_RETRY",
    }
    if (type(value) is not dict or set(value)!=valid
        or value.get("schema_version")!=SCHEMA
        or value.get("mode")!="SIMULATION"
        or value.get("status") not in statuses
        or type(value.get("fictional_receipt_count")) is not int
        or not 0<=value["fictional_receipt_count"]<=2
        or value.get("synthetic_signature_checks_passed")!=value["fictional_receipt_count"]
        or value.get("fake_provider_signature_not_real_source_attestation") is not True
        or value.get("synthetic_receipt_chain_consistent") is not True
        or value.get("verified_real_provider_delivery") is not False
        or value.get("verified_real_user_device_receipt") is not False
        or value.get("current_user_consent_verified") is not False
        or value.get("actual_provider_contact_or_transport_used") is not False
        or value.get("outbound_notification_sent") is not False
        or value.get("automatic_retry_permitted") is not False
        or value.get("original_empiredb_writes") is not False
        or value.get("real_customer_data_seen") is not False
        or value.get("execution_authority")!="none"):
        raise ProviderReconciliationHold("untrusted_original_provider_receipt_projection")
    return {
        "schema_version":"empire.prime.founder_provider_reconciliation.v1",
        "mode":"SIMULATION",
        "status":value["status"],
        "synthetic_receipt_count":value["fictional_receipt_count"],
        "verified_real_provider_delivery":False,
        "real_user_device_alert_delivered":False,
        "execution_authority":"none",
    }
