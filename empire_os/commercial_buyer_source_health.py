"""First-party buyer-capacity evidence health for existing adaptive Ops.

Consumes only the original Buyer Capacity and Buyer Scout evidence owners'
read-only snapshots. A webpage purchase claim is NOT buyer capacity, accepted
terms, settled orders, delivery, replies or customer spend authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any, Mapping

SCHEMA = "empire.commercial.original_buyer_evidence_health.v1"
CAPACITY_SCHEMA = "empire.buyer_capacity_readiness.v1"
QUALITY_SCHEMA = "empire.buyer_evidence_quality.v1"
CAPACITY_FILE = "runtime/buyer_capacity_readiness/latest.json"
QUALITY_FILE = "runtime/buyer_acquisition/evidence_quality_latest.json"
MAX_BYTES = 300_000
MAX_AGE_HOURS = 24


def _count(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= 2_000_000:
        raise ValueError("bounded original owner evidence count required")
    return value


def _source_age(raw: Any, now: datetime) -> tuple[str, int | None]:
    if not isinstance(raw, str) or len(raw) > 90:
        return "INVALID", None
    try:
        at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if at.utcoffset() is None:
            raise ValueError("timezone missing")
        seconds = (now - at.astimezone(timezone.utc)).total_seconds()
        if seconds < -300:
            return "FUTURE", None
        return ("STALE" if seconds > MAX_AGE_HOURS * 3600 else "FRESH",
                max(0, int(seconds // 3600)))
    except (ValueError, OverflowError, TypeError):
        return "INVALID", None


def evaluate_buyer_source_health(
    capacity: Mapping[str, Any],
    quality: Mapping[str, Any],
    *, now: datetime,
) -> dict[str, Any]:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware original buyer review required")
    clock = now.astimezone(timezone.utc)
    if (
        not isinstance(capacity, Mapping)
        or capacity.get("schema_version") != CAPACITY_SCHEMA
        or capacity.get("mode") != "OBSERVE"
        or capacity.get("execution_authority") != "none"
        or capacity.get("allocation_executed") is not False
        or capacity.get("payment_action") is not False
        or capacity.get("revenue_recognition") is not False
    ):
        raise ValueError("trusted nonexecuting buyer capacity snapshot required")
    if (
        not isinstance(quality, Mapping)
        or quality.get("schema_version") != QUALITY_SCHEMA
        or quality.get("mode") != "OBSERVE"
        or quality.get("commercial_authority") != "none"
        or quality.get("outbound_sent") is not False
        or quality.get("database_write_performed") is not False
    ):
        raise ValueError("trusted nonexecuting buyer source quality snapshot required")
    fields = ("buyers_seen", "capacity_verified", "terms_verified",
              "delivery_verified", "fully_activated")
    buyer_counts = {name: _count(capacity.get(name)) for name in fields}
    n = buyer_counts["buyers_seen"]
    if any(buyer_counts[k] > n for k in fields[1:]):
        raise ValueError("original buyer capacity count contradiction")
    quality_claims = _count(quality.get("candidate_with_valid_direct_purchase_receipt"))
    unsupported = _count(quality.get("unsupported_positive_direct_buyer_flags"))
    scout_count = _count(quality.get("scout_candidate_count"))
    if quality_claims > scout_count or unsupported > scout_count:
        raise ValueError("first-party Scout claim count contradiction")
    t1, h1 = _source_age(capacity.get("observed_at"), clock)
    t2, h2 = _source_age(quality.get("generated_at"), clock)
    freshness = {"buyer_capacity_owner": t1, "buyer_scout_evidence_owner": t2}
    stale = any(x != "FRESH" for x in freshness.values())
    return {
        "schema_version": SCHEMA,
        "status": (
            "ORIGINAL_BUYER_SOURCE_REVIEW_REQUIRED" if stale else
            "BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD"
        ),
        "mode": "OBSERVE",
        "source_owner_freshness": freshness,
        "source_owner_age_hours_floor": {
            "buyer_capacity_owner": h1,
            "buyer_scout_evidence_owner": h2,
        },
        "buyer_capacity_records_seen_not_verified_purchasers": n,
        "owner_capacity_verified_claim_count": buyer_counts["capacity_verified"],
        "owner_terms_verified_claim_count": buyer_counts["terms_verified"],
        "owner_delivery_verified_claim_count": buyer_counts["delivery_verified"],
        "owner_fully_activated_count_not_independent_payment_proof": buyer_counts["fully_activated"],
        "scout_candidate_count_separate_cohort": scout_count,
        "first_party_purchase_claim_receipts_not_contracts": quality_claims,
        "unsupported_direct_purchase_claim_flags": unsupported,
        "missing_verified_terms_for_any_capacity_record": buyer_counts["terms_verified"] == 0,
        "missing_verified_capacity_for_any_capacity_record": buyer_counts["capacity_verified"] == 0,
        "proof_required_from_existing_owner": [
            "ORIGINAL_TENANT_SCOPED_COUNTERPARTY_IDENTITY",
            "ACCEPTED_COMMERCIAL_BUY_BOX_AND_TERMS",
            "VERIFIED_BUYER_CAPACITY_AND_DELIVERY_DESTINATION",
            "EXACT_CANONICAL_ORDER_AND_PAYMENT_PROVENANCE_FOR_OUTCOMES",
        ],
        "verified_purchase_events_claimed_by_this_report": None,
        "realized_revenue_cents_claimed_by_this_report": None,
        "no_cross_source_person_or_company_matching": True,
        "no_buyer_activation_from_page_receipt": True,
        "outbound_authorized": False,
        "database_writes": False,
        "payments_executed": False,
        "agent_tasks_created": False,
        "execution_authority": "none",
    }


def _bounded_owner_file(root: Path, relative: str):
    p = root / relative
    if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_BYTES:
        raise ValueError("bounded owner source unavailable")
    record = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError("original owner record required")
    return record


def inspect_original_buyer_health(root: Path, *, now: datetime) -> dict[str, Any]:
    try:
        return evaluate_buyer_source_health(
            _bounded_owner_file(root, CAPACITY_FILE),
            _bounded_owner_file(root, QUALITY_FILE),
            now=now,
        )
    except (ValueError, TypeError, OSError, json.JSONDecodeError, OverflowError):
        return {
            "schema_version": SCHEMA,
            "status": "ORIGINAL_BUYER_SOURCE_UNAVAILABLE",
            "mode": "OBSERVE",
            "proof_required_from_existing_owner": [
                "ORIGINAL_BUYER_CAPACITY_AND_EVIDENCE_SNAPSHOTS"
            ],
            "verified_purchase_events_claimed_by_this_report": None,
            "realized_revenue_cents_claimed_by_this_report": None,
            "outbound_authorized": False,
            "database_writes": False,
            "payments_executed": False,
            "agent_tasks_created": False,
            "execution_authority": "none",
        }


_CHANGE_FIELDS = (
    "buyer_capacity_records_seen_not_verified_purchasers",
    "owner_capacity_verified_claim_count",
    "owner_terms_verified_claim_count",
    "owner_delivery_verified_claim_count",
    "owner_fully_activated_count_not_independent_payment_proof",
    "scout_candidate_count_separate_cohort",
    "first_party_purchase_claim_receipts_not_contracts",
    "unsupported_direct_purchase_claim_flags",
)


def review_buyer_evidence_transition(
    previous: Mapping[str, Any] | None, current: Mapping[str, Any]
) -> dict[str, Any]:
    """Existing Ops snapshot memory: compare owner claims only, no dispatch."""
    valid_current = (
        isinstance(current, Mapping)
        and current.get("schema_version") == SCHEMA
        and current.get("mode") == "OBSERVE"
        and current.get("execution_authority") == "none"
        and current.get("outbound_authorized") is False
        and current.get("database_writes") is False
    )
    if not valid_current:
        raise ValueError("original owner health report required")
    active = current.get("status") == "BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD"
    prior_ok = (
        isinstance(previous, Mapping)
        and previous.get("schema_version") == SCHEMA
        and previous.get("mode") == "OBSERVE"
        and previous.get("execution_authority") == "none"
        and previous.get("outbound_authorized") is False
        and previous.get("database_writes") is False
        and previous.get("status") == "BUYER_CONTRACT_CAPACITY_EVIDENCE_HOLD"
        and all(type(previous.get(k)) is int and 0 <= previous[k] <= 2_000_000
                for k in _CHANGE_FIELDS)
    )
    if not active:
        state = "SOURCE_UNAVAILABLE_OR_OUTDATED_HOLD"
        delta = {}
    else:
        if any(type(current.get(k)) is not int or current[k] < 0 for k in _CHANGE_FIELDS):
            raise ValueError("bounded current buyer owner counters required")
        delta = {
            k: current[k] - previous[k] for k in _CHANGE_FIELDS
            if prior_ok and current[k] != previous[k]
        }
        state = (
            "INITIAL_BUYER_EVIDENCE_BASELINE" if not prior_ok else
            "OWNER_COHORT_COUNTERS_CHANGED_REQUIRE_VERIFICATION" if delta else
            "UNCHANGED_ORIGINAL_BUYER_EVIDENCE_HOLD"
        )
    return {
        "schema_version": "empire.commercial.buyer_evidence_transition.v1",
        "status": state,
        "owner_claim_counter_deltas_not_transactions": delta,
        "owner_attestation_required_before_commercial_progress": True,
        "repeated_owner_attention_suppressed": not bool(delta) and prior_ok,
        "no_cross_source_identity_linkage": True,
        "verified_new_buyer_purchases": None,
        "new_contracts_signed": None,
        "money_received_cents": None,
        "outbound_authorized": False,
        "task_dispatched": False,
        "execution_authority": "none",
    }


def inspect_original_warm_partner_closing(
    root: Path, *, now: datetime,
) -> dict[str, Any]:
    """Read original founder relationship/buy-box ownership, never send or admit.

    Relationship replies establish what buyer said, not commercial settlement.
    Use only the pre-existing registry's protected review queue, no names,
    addresses, email bodies or prospect records from other systems.
    """
    from empire_os.buyer_qualification_evidence_bridge import load_registry

    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware commercial review required")
    raw, source_state = load_registry(root, now=now.astimezone(timezone.utc))
    held = {
        "schema_version": "empire.commercial.existing_warm_partner_closing.v1",
        "mode": "OBSERVE",
        "source_state": source_state,
        "status": "ORIGINAL_FOUNDER_REGISTRY_REVIEW_HOLD",
        "warm_relationship_count": None,
        "warm_reviews": [],
        "confirmed_buyer_payable_agreement_count": None,
        "verified_order_outcome_count": None,
        "verified_recognized_revenue_cents": None,
        "qualification_requires_existing_commercial_owner": True,
        "actual_revenue_claimed": False,
        "outbound_authorized": False,
        "agent_tasks_created": False,
        "execution_authority": "none",
    }
    if not raw:
        return held
    relationships = raw.get("relationships", [])
    warm = raw.get("warm_business_action_queue", [])
    pilots = raw.get("partner_pilot_readiness_queue", [])
    if (not isinstance(relationships, list) or len(relationships) > 500
            or not isinstance(warm, list) or len(warm) > 25
            or not isinstance(pilots, list) or len(pilots) > 50
            or raw.get("founder_actions_are_draft_only") is not True
            or raw.get("outbound_authorized") is not False
            or raw.get("outbound_sent") is not False):
        return held
    by_entity: dict[str, list[dict]] = {}
    for item in relationships:
        if isinstance(item, dict) and isinstance(item.get("entity_key"), str):
            by_entity.setdefault(item["entity_key"], []).append(item)
    by_pilot: dict[str, list[dict]] = {}
    for item in pilots:
        if isinstance(item, dict) and isinstance(item.get("entity_key"), str):
            by_pilot.setdefault(item["entity_key"], []).append(item)
    work = []
    seen: set[str] = set()
    for item in warm:
        if not isinstance(item, dict):
            return held
        key = item.get("entity_key")
        if not isinstance(key, str) or not 1 <= len(key) <= 110 or key in seen:
            return held
        seen.add(key)
        rel = by_entity.get(key, [])
        pilot = by_pilot.get(key, [])
        if len(rel) != 1 or len(pilot) > 1:
            return held
        relation = rel[0]
        partner = pilot[0] if pilot else {}
        stage = relation.get("stage")
        next_task = partner.get("current_next_partner_task") or relation.get("next_founder_action")
        allowed_tasks = {
            "WAIT_CURRENT_BUYBOX_AND_SOURCE_APPROVAL",
            "CONFIRM_VALIDATED_AFFILIATE_TERMS_AND_BUYBOX",
            "DEFER_INQUIRLY_UNTIL_VERIFIED_TRAFFIC_NO_REPEAT_REQUEST",
            "CLARIFY_CONNEXIS_LIVE_CALLS_VS_API_CPL_TERMS",
            "REVIEW_EXISTING_ROUTING_RECORDING_REPLY_NO_REPEAT",
            "REVIEW_ANSWERED_FIELDS_ONLY_NO_REPEAT_QUESTIONNAIRE",
            "WAIT_BUYER_ONBOARDING_AND_MARKETS",
        }
        if next_task not in allowed_tasks:
            next_task = "REVIEW_ORIGINAL_OWNER_EVIDENCE_NO_REPEAT"
        work.append({
            "entity_key": key,
            "partner_name": str(relation.get("company") or "")[:100],
            "relationship_stage": stage if stage in {
                "AWAITING_BUYER", "INBOUND_REVIEW_REQUIRED", "EVIDENCE_HOLD",
                "CONTACTED_AWAITING_RESPONSE", "DELIVERY_HOLD", "RESEARCH_ONLY"
            } else "UNKNOWN",
            "original_partner_pilot_stage": str(partner.get("activation_stage") or "NOT_IN_PILOT")[:80],
            "original_next_founder_task": next_task,
            "two_way_thread_original_owner_reported": partner.get("two_way_gmail_thread_observed") is True,
            "original_owner_verified_pilot_gate_count": (
                int(partner.get("gate_count_verified"))
                if type(partner.get("gate_count_verified")) is int
                and 0 <= partner["gate_count_verified"] <= 9 else None
            ),
            "buyer_acceptance_independently_verified_by_review": False,
            "written_payable_terms_independently_verified_by_review": False,
            "settled_order_verified_by_review": False,
            "next_owner": "existing_founder_commercial_and_partner_relationship_owner",
            "no_repeat_outreach_automatic": True,
            "send_authorized": False,
        })
    return {
        **held,
        "status": "EXISTING_WARM_BUYERS_REQUIRE_OWNER_TERMS_PROOF",
        "warm_relationship_count": len(work),
        "warm_reviews": work,
        "buyer_ready_count_not_claimed": None,
        "no_new_buyer_candidate_promoted": True,
        "no_cross_cohort_matching": True,
    }


def inspect_existing_lead_smart_cash_pulse(root: Path, *, now: datetime) -> dict[str, Any]:
    """Read the safe original campaign pulse, not the protected call records.

    Never infer settlement from observed payout, Ringba test calls or a
    disabled consumer handoff. Protected owner data stays inaccessible.
    """
    from pathlib import Path as _Path
    import stat

    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware commercial proof review required")
    unknown = {
        "status": "ORIGINAL_LEAD_SMART_PULSE_UNAVAILABLE",
        "source_freshness": "UNKNOWN",
        "site_handoffs": None,
        "site_handoff_switch_enabled": None,
        "provider_row_count": None,
        "protected_call_to_cash_receipt": "UNKNOWN",
        "provider_accepted_calls_claimed": None,
        "settled_revenue_cents": None,
        "next_existing_owner_action": "REVIEW_ORIGINAL_RINGBA_REPORTING_AND_CONFIRMED_DISPOSITION",
        "buyer_route_or_call_activation_authorized": False,
        "predictive_cloud_calibration_authorized": False,
        "execution_authority": "none",
    }
    path = root / "runtime/revenue/lead_smart/commercial_pulse/latest.json"
    protected = root / "runtime/revenue/lead_smart/commercial_pulse/call_to_cash_latest.json"
    protected_status = "UNKNOWN"
    try:
        mode = protected.stat()
        if (not protected.is_symlink() and stat.S_ISREG(mode.st_mode)
                and mode.st_uid == 0 and stat.S_IMODE(mode.st_mode) == 0o600):
            protected_status = "PROTECTED_ROOT_ONLY_NOT_READ_BY_OPS"
        else:
            protected_status = "UNTRUSTED_PROTECTED_RECEIPT_METADATA"
    except OSError:
        protected_status = "MISSING_OR_NOT_STATABLE"
    try:
        if path.is_symlink() or not path.is_file() or not 50 <= path.stat().st_size <= 150_000:
            return {**unknown, "protected_call_to_cash_receipt": protected_status}
        pulse = json.loads(path.read_text(encoding="utf-8"))
        when = datetime.fromisoformat(str(pulse["observed_at_utc"]).replace("Z", "+00:00"))
        seconds = (now.astimezone(timezone.utc) - when.astimezone(timezone.utc)).total_seconds()
        if (not isinstance(pulse, dict)
                or pulse.get("schema_version") != "empire.lead_smart.commercial_pulse.v1"
                or pulse.get("campaign_id") != "CA8278ed3f26e9495b881fe3833174d007"
                or pulse.get("buyer") != "Lead Smart"
                or pulse.get("site_route") != "/roofing"
                or type(pulse.get("site_handoffs_recorded")) is not int
                or pulse["site_handoffs_recorded"] < 0
                or type(pulse.get("site_handoff_switch_enabled")) is not bool
                or pulse.get("no_real_revenue_inferred_from_tracking") is not True
                or pulse.get("settled_revenue_verified") is not False
                or pulse.get("qualified_billable_calls_verified") is not False
                or pulse.get("actual_connected_homeowner_calls_verified") is not False
                or pulse.get("raw_call_identifiers_persisted") is not False
                or not 0 <= seconds <= 24 * 3600):
            return {**unknown, "protected_call_to_cash_receipt": protected_status,
                    "source_freshness": "INVALID_OR_STALE"}
        ringba = pulse.get("ringba")
        if (not isinstance(ringba, dict)
                or ringba.get("provider_token_read_by_unprivileged_process") is not False
                or ringba.get("payable_call_verified") is not False
                or ringba.get("settled_revenue_verified") is not False
                or ringba.get("buyer_leg_connected_verified") is not False):
            return {**unknown, "protected_call_to_cash_receipt": protected_status,
                    "source_freshness": "UNTRUSTED_PROVIDER_SUMMARY"}
        count = ringba.get("matching_rows_in_returned_window")
        if type(count) is not int or not 0 <= count <= 100000:
            return {**unknown, "protected_call_to_cash_receipt": protected_status}
        return {
            **unknown,
            "status": "NO_CONFIRMED_PAYABLE_CALL_FROM_UNPRIVILEGED_OWNER_PULSE",
            "source_freshness": "FRESH",
            "site_handoffs": pulse["site_handoffs_recorded"],
            "site_handoff_switch_enabled": pulse["site_handoff_switch_enabled"],
            "provider_row_count": count,
            "protected_call_to_cash_receipt": protected_status,
            "no_proof_of_accepted_calls": True,
            "no_proof_of_received_cash": True,
        }
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        return {**unknown, "protected_call_to_cash_receipt": protected_status}
