"""Original PRIME / Conversation OS: conservative objection-resolution lifecycle.

Metadata-only, owner-prepared case replay. Provider identity, consent, source
rights and replay-proof remain independently unverified by this pure module.
No personal profiling, inferred emotions, message bodies, CRM writes or sends.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
import re
from typing import Any

from empire_os.prime_conversation_objection_shadow import CUES

SCHEMA = "empire.prime.original_conversation_objection_lifecycle_shadow.v1"
FOUNDER_SCHEMA = "empire.prime.founder_objection_lifecycle_research.v1"
CATEGORIES = frozenset(code for code, _, _ in CUES)
EVENT_TYPES = frozenset({
    "PERSON_STATED_CONCERN",
    "HUMAN_EXPLANATION_SENT",
    "PERSON_STILL_CONCERNED",
    "PERSON_EXPLICITLY_CONFIRMED_RESOLVED",
    "PERSON_DECLINED",
    "PERSON_OPTED_OUT",
})
INBOUND_EVENTS = frozenset({
    "PERSON_STATED_CONCERN", "PERSON_STILL_CONCERNED",
    "PERSON_EXPLICITLY_CONFIRMED_RESOLVED", "PERSON_DECLINED",
    "PERSON_OPTED_OUT",
})
MAX_EVENTS = 64
MAX_CASE_DAYS = 45
HEX = re.compile(r"^[a-f0-9]{64}$")
FIELDS = frozenset({
    "event_digest", "kind", "direction", "concern_code", "observed_at",
    "original_owner_readback_reviewed", "purpose_reviewed",
    "synthetic", "contains_personal_data",
})


RESULT_FIELDS = frozenset({
    "schema_version", "mode", "status", "private_case_state_counts_not_verified_truth",
    "event_count_not_unique_people", "source_absence_not_interpreted_as_no_objections",
    "contact_stop_or_suppression_review_required",
    "human_explanation_not_proof_of_resolution",
    "person_reported_resolution_not_provider_authenticated",
    "provider_and_tenant_authentication_verified_by_this_module",
    "source_processing_rights_verified_by_this_module",
    "independently_verified_buying_intent", "covert_personality_or_emotion_profiles",
    "private_body_or_identity_returned", "realized_revenue_cents",
    "model_training", "outbound_sent", "crm_writes", "empiredb_writes",
    "execution_authority",
})

class ObjectionLifecycleHold(ValueError):
    """An untrusted source row cannot be admitted even as research metadata."""


def _time(value: Any, *, as_of: datetime) -> datetime:
    if type(value) is not str or not 1 <= len(value) <= 40:
        raise ObjectionLifecycleHold("bounded_original_event_clock_required")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (OverflowError, ValueError):
        raise ObjectionLifecycleHold("original_event_clock_invalid") from None
    if stamp.utcoffset() is None:
        raise ObjectionLifecycleHold("aware_original_event_clock_required")
    moment = stamp.astimezone(timezone.utc)
    if moment > as_of + timedelta(minutes=5):
        raise ObjectionLifecycleHold("future_original_event_refused")
    if as_of - moment > timedelta(days=MAX_CASE_DAYS):
        raise ObjectionLifecycleHold("historical_case_age_outside_review_limit")
    return moment


def review_objection_lifecycle(
    *,
    case_digest: str,
    events: Sequence[Mapping[str, Any]] | None,
    as_of: datetime,
) -> dict[str, Any]:
    """Review a single permitted case with no trust elevation.

    A claimed human explanation NEVER resolves an objection. Only a later
    person's explicit resolution report can change a concern to RESOLVED,
    and even that remains structurally unverified until original owners attest.
    """
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ObjectionLifecycleHold("aware_review_clock_required")
    if type(case_digest) is not str or HEX.fullmatch(case_digest) is None:
        raise ObjectionLifecycleHold("purpose_scoped_original_case_digest_required")
    if events is None:
        return _result(None, "NO_OWNER_CASE_EVENTS_CONNECTED", 0, False)
    if type(events) not in (tuple, list) or not 1 <= len(events) <= MAX_EVENTS:
        raise ObjectionLifecycleHold("bounded_owner_event_chain_required")
    now = as_of.astimezone(timezone.utc)
    seen: set[str] = set()
    states: dict[str, str] = {}
    stopped = False
    declined = False
    prior: datetime | None = None
    for e in events:
        if type(e) is not dict or set(e) != FIELDS:
            raise ObjectionLifecycleHold("exact_original_owner_event_contract_required")
        digest = e["event_digest"]
        if type(digest) is not str or HEX.fullmatch(digest) is None or digest in seen:
            raise ObjectionLifecycleHold("duplicate_or_invalid_original_event_digest")
        seen.add(digest)
        kind, direction, concern = e["kind"], e["direction"], e["concern_code"]
        if type(kind) is not str or kind not in EVENT_TYPES:
            raise ObjectionLifecycleHold("unrecognised_original_conversation_event")
        if direction != ("inbound" if kind in INBOUND_EVENTS else "outbound"):
            raise ObjectionLifecycleHold("original_direction_event_mismatch")
        if (e["original_owner_readback_reviewed"] is not True
            or e["purpose_reviewed"] is not True
            or e["synthetic"] is not False
            or e["contains_personal_data"] is not False):
            raise ObjectionLifecycleHold("original_owner_provenance_and_rights_hold")
        at = _time(e["observed_at"], as_of=now)
        if prior is not None and at <= prior:
            raise ObjectionLifecycleHold("noncausal_or_tied_original_event_order")
        prior = at
        if stopped or declined:
            raise ObjectionLifecycleHold("events_after_decline_or_optout_forbidden")
        if kind in ("PERSON_DECLINED", "PERSON_OPTED_OUT"):
            if concern is not None:
                raise ObjectionLifecycleHold("terminal_event_must_not_profile_a_concern")
            declined = kind == "PERSON_DECLINED"
            stopped = kind == "PERSON_OPTED_OUT"
            continue
        if type(concern) is not str or concern not in CATEGORIES:
            raise ObjectionLifecycleHold("existing_original_objection_category_required")
        current = states.get(concern)
        if kind == "PERSON_STATED_CONCERN":
            if current in ("OPEN", "ANSWERED_AWAITING_CONFIRMATION", "REOPENED"):
                raise ObjectionLifecycleHold("repeated_open_objection_without_new_evidence")
            states[concern] = "OPEN" if current is None else "REOPENED"
        elif kind == "HUMAN_EXPLANATION_SENT":
            if current not in ("OPEN", "REOPENED"):
                raise ObjectionLifecycleHold("reply_cannot_resolve_or_create_objection")
            states[concern] = "ANSWERED_AWAITING_CONFIRMATION"
        elif kind == "PERSON_STILL_CONCERNED":
            if current is None:
                raise ObjectionLifecycleHold("followup_without_initial_person_concern")
            states[concern] = "REOPENED"
        elif kind == "PERSON_EXPLICITLY_CONFIRMED_RESOLVED":
            if current not in (
                "OPEN", "ANSWERED_AWAITING_CONFIRMATION", "REOPENED",
            ):
                raise ObjectionLifecycleHold("resolution_without_open_original_objection")
            states[concern] = "PERSON_REPORTED_RESOLVED_NOT_PROVIDER_VERIFIED"
    n_open = sum(s in ("OPEN", "REOPENED") for s in states.values())
    n_awaiting = sum(s == "ANSWERED_AWAITING_CONFIRMATION" for s in states.values())
    n_reported = sum(s == "PERSON_REPORTED_RESOLVED_NOT_PROVIDER_VERIFIED" for s in states.values())
    status = (
        "EXPLICIT_OPT_OUT_OWNER_SUPPRESSION_REVIEW_REQUIRED" if stopped
        else "PERSON_DECLINED_STOP_CONTACT_REVIEW_REQUIRED" if declined
        else "ORIGINAL_OWNER_OBJECTION_LIFECYCLE_SHADOW_ONLY"
    )
    return _result(
        {"open": n_open, "awaiting": n_awaiting, "person_reported": n_reported},
        status, len(events), stopped or declined,
    )


def _result(counts: dict[str, int] | None, status: str, event_count: int, stop: bool) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": status,
        "private_case_state_counts_not_verified_truth": counts,
        "event_count_not_unique_people": event_count if counts is not None else None,
        "source_absence_not_interpreted_as_no_objections": counts is None,
        "contact_stop_or_suppression_review_required": stop,
        "human_explanation_not_proof_of_resolution": True,
        "person_reported_resolution_not_provider_authenticated": True,
        "provider_and_tenant_authentication_verified_by_this_module": False,
        "source_processing_rights_verified_by_this_module": False,
        "independently_verified_buying_intent": False,
        "covert_personality_or_emotion_profiles": False,
        "private_body_or_identity_returned": False,
        "realized_revenue_cents": None,
        "model_training": False,
        "outbound_sent": False,
        "crm_writes": False,
        "empiredb_writes": False,
        "execution_authority": "none",
    }


def founder_objection_lifecycle_status(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Founder can see safe workflow state, never individual concern counts."""
    if value is None:
        return {
            "schema_version": FOUNDER_SCHEMA, "mode": "OBSERVE",
            "status": "NOT_CONNECTED", "source_authenticated": False,
            "objection_resolved_independently_verified": False,
            "send_authorized": False, "execution_authority": "none",
        }
    if (type(value) is not dict or set(value) != RESULT_FIELDS
        or value.get("schema_version") != SCHEMA
        or value.get("execution_authority") != "none"
        or value.get("provider_and_tenant_authentication_verified_by_this_module") is not False
        or value.get("source_processing_rights_verified_by_this_module") is not False
        or value.get("independently_verified_buying_intent") is not False
        or value.get("covert_personality_or_emotion_profiles") is not False
        or value.get("private_body_or_identity_returned") is not False
        or value.get("realized_revenue_cents") is not None
        or value.get("outbound_sent") is not False
        or value.get("crm_writes") is not False
        or value.get("empiredb_writes") is not False
        or value.get("model_training") is not False
        or value.get("mode") != "OBSERVE"
        or value.get("human_explanation_not_proof_of_resolution") is not True
        or value.get("person_reported_resolution_not_provider_authenticated") is not True):
        raise ObjectionLifecycleHold("untrusted_founder_objection_source_projection")
    status = value.get("status")
    if status not in {
        "NO_OWNER_CASE_EVENTS_CONNECTED",
        "ORIGINAL_OWNER_OBJECTION_LIFECYCLE_SHADOW_ONLY",
        "EXPLICIT_OPT_OUT_OWNER_SUPPRESSION_REVIEW_REQUIRED",
        "PERSON_DECLINED_STOP_CONTACT_REVIEW_REQUIRED",
    }:
        raise ObjectionLifecycleHold("unexpected_original_lifecycle_state")
    n = value.get("private_case_state_counts_not_verified_truth")
    size = value.get("event_count_not_unique_people")
    unknown = status == "NO_OWNER_CASE_EVENTS_CONNECTED"
    stopped = status in (
        "EXPLICIT_OPT_OUT_OWNER_SUPPRESSION_REVIEW_REQUIRED",
        "PERSON_DECLINED_STOP_CONTACT_REVIEW_REQUIRED",
    )
    if (value.get("source_absence_not_interpreted_as_no_objections") is not unknown
        or value.get("contact_stop_or_suppression_review_required") is not stopped
        or (unknown and (n is not None or size is not None))
        or (not unknown and (
            type(n) is not dict or set(n) != {"open", "awaiting", "person_reported"}
            or any(type(x) is not int or x < 0 or x > len(CATEGORIES)
                   for x in n.values())
            or sum(n.values()) > len(CATEGORIES)
            or type(size) is not int or not 1 <= size <= MAX_EVENTS
        ))):
        raise ObjectionLifecycleHold("inconsistent_private_objection_source_projection")
    return {
        "schema_version": FOUNDER_SCHEMA,
        "mode": "OBSERVE",
        "status": status,
        "source_authenticated": False,
        "objection_resolved_independently_verified": False,
        "send_authorized": False,
        "execution_authority": "none",
    }
