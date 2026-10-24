"""Synthetic objection lifecycle cases; no private message, CRM or live receipt."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from empire_os.prime_objection_lifecycle_shadow import (
    ObjectionLifecycleHold, review_objection_lifecycle,
    founder_objection_lifecycle_status, FIELDS,
)

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
CASE = sha256(b"fictional-internal-case-only").hexdigest()
PRICE = "PRICE_OR_BUDGET_QUESTION"
PRIVACY = "PRIVACY_OR_COMPLIANCE_CONCERN"

def event(kind, i, concern=PRICE, **kw):
    t = (NOW - timedelta(days=2) + timedelta(minutes=i * 10)).isoformat()
    data = {
        "event_digest": sha256(f"synthetic-event-{i}-{kind}".encode()).hexdigest(),
        "kind": kind,
        "direction": "outbound" if kind == "HUMAN_EXPLANATION_SENT" else "inbound",
        "concern_code": concern if kind not in ("PERSON_DECLINED", "PERSON_OPTED_OUT") else None,
        "observed_at": t,
        "original_owner_readback_reviewed": True,
        "purpose_reviewed": True,
        "synthetic": False,  # synthetic fixtures of owner-approved *shape*, not proof
        "contains_personal_data": False,
    }
    data.update(kw)
    return data

def review(*events):
    return review_objection_lifecycle(
        case_digest=CASE, events=list(events), as_of=NOW,
    )

def test_unavailable_case_is_unknown_not_empty_commercial_funnel():
    v = review_objection_lifecycle(case_digest=CASE, events=None, as_of=NOW)
    assert v["status"] == "NO_OWNER_CASE_EVENTS_CONNECTED"
    assert v["source_absence_not_interpreted_as_no_objections"] is True
    assert v["event_count_not_unique_people"] is None
    assert founder_objection_lifecycle_status(v)["objection_resolved_independently_verified"] is False

def test_objection_remains_open_until_a_genuine_new_event():
    v = review(event("PERSON_STATED_CONCERN", 1))
    assert v["private_case_state_counts_not_verified_truth"] == {
        "open": 1, "awaiting": 0, "person_reported": 0,
    }
    assert v["outbound_sent"] is False
    assert v["provider_and_tenant_authentication_verified_by_this_module"] is False

def test_human_answer_does_not_count_as_resolution():
    v = review(event("PERSON_STATED_CONCERN", 1), event("HUMAN_EXPLANATION_SENT", 2))
    assert v["private_case_state_counts_not_verified_truth"] == {
        "open": 0, "awaiting": 1, "person_reported": 0,
    }
    assert v["human_explanation_not_proof_of_resolution"] is True
    assert v["realized_revenue_cents"] is None

def test_explicit_person_resolved_remains_unverified_original_provider_report():
    v = review(
        event("PERSON_STATED_CONCERN", 1),
        event("HUMAN_EXPLANATION_SENT", 2),
        event("PERSON_EXPLICITLY_CONFIRMED_RESOLVED", 3),
    )
    assert v["private_case_state_counts_not_verified_truth"]["person_reported"] == 1
    assert v["person_reported_resolution_not_provider_authenticated"] is True
    f = founder_objection_lifecycle_status(v)
    assert f["objection_resolved_independently_verified"] is False
    assert "PRICE" not in str(f)
    assert CASE not in str(f)

def test_reopen_after_person_reported_resolution():
    v = review(
        event("PERSON_STATED_CONCERN", 1),
        event("PERSON_EXPLICITLY_CONFIRMED_RESOLVED", 2),
        event("PERSON_STATED_CONCERN", 3),
    )
    assert v["private_case_state_counts_not_verified_truth"]["open"] == 1
    assert v["private_case_state_counts_not_verified_truth"]["person_reported"] == 0

def test_followup_question_overrides_explanation():
    v = review(
        event("PERSON_STATED_CONCERN", 1),
        event("HUMAN_EXPLANATION_SENT", 2),
        event("PERSON_STILL_CONCERNED", 3),
    )
    assert v["private_case_state_counts_not_verified_truth"]["open"] == 1

def test_multiple_concerns_have_separate_states_without_private_ids():
    v = review(
        event("PERSON_STATED_CONCERN", 1, PRICE),
        event("PERSON_STATED_CONCERN", 2, PRIVACY),
        event("HUMAN_EXPLANATION_SENT", 3, PRICE),
        event("PERSON_EXPLICITLY_CONFIRMED_RESOLVED", 4, PRICE),
    )
    assert v["private_case_state_counts_not_verified_truth"] == {
        "open": 1, "awaiting": 0, "person_reported": 1,
    }
    assert "PRIVACY_OR_COMPLIANCE_CONCERN" not in str(v)
    assert v["independently_verified_buying_intent"] is False

@pytest.mark.parametrize("terminal,expected", [
    ("PERSON_OPTED_OUT", "EXPLICIT_OPT_OUT_OWNER_SUPPRESSION_REVIEW_REQUIRED"),
    ("PERSON_DECLINED", "PERSON_DECLINED_STOP_CONTACT_REVIEW_REQUIRED"),
])
def test_terminal_decline_or_optout_refuses_further_objection_handling(terminal,expected):
    stop = event(terminal, 2)
    v = review(event("PERSON_STATED_CONCERN", 1), stop)
    assert v["status"] == expected
    assert v["contact_stop_or_suppression_review_required"] is True
    with pytest.raises(ObjectionLifecycleHold, match="events_after_decline"):
        review(event("PERSON_STATED_CONCERN", 1), stop,
               event("HUMAN_EXPLANATION_SENT", 3))

@pytest.mark.parametrize("kind", [
    "HUMAN_EXPLANATION_SENT",
    "PERSON_STILL_CONCERNED",
    "PERSON_EXPLICITLY_CONFIRMED_RESOLVED",
])
def test_first_message_cannot_conjure_a_previous_objection(kind):
    with pytest.raises(ObjectionLifecycleHold):
        review(event(kind, 1))

def test_second_person_objection_cannot_inflate_duplicate_open_concern():
    with pytest.raises(ObjectionLifecycleHold, match="repeated_open_objection"):
        review(event("PERSON_STATED_CONCERN", 1),
               event("PERSON_STATED_CONCERN", 2))

def test_original_event_cannot_claim_sent_action_from_inbound_direction():
    with pytest.raises(ObjectionLifecycleHold, match="direction_event_mismatch"):
        review(event("HUMAN_EXPLANATION_SENT", 2, direction="inbound"))

@pytest.mark.parametrize("changes,reason", [
    ({"event_digest": "person@example.test"}, "digest"),
    ({"kind": "SECRET_PSYCHOLOGICAL_TRIGGER"}, "unrecognised"),
    ({"concern_code": "ANXIETY_VULNERABILITY_SCORE"}, "category"),
    ({"synthetic": True}, "provenance_and_rights"),
    ({"original_owner_readback_reviewed": False}, "provenance_and_rights"),
    ({"purpose_reviewed": False}, "provenance_and_rights"),
    ({"contains_personal_data": True}, "provenance_and_rights"),
    ({"raw_body": "never store this"}, "exact_original_owner"),
    ({"observed_at": (NOW + timedelta(days=3)).isoformat()}, "future_original"),
    ({"observed_at": "2026-10-24T10:00:00"}, "aware_original_event"),
    ({"observed_at": (NOW - timedelta(days=80)).isoformat()}, "historical_case_age"),
])
def test_bad_owner_or_privacy_fields_fail_closed(changes,reason):
    row = event("PERSON_STATED_CONCERN", 1)
    row.update(changes)
    with pytest.raises(ObjectionLifecycleHold, match=reason):
        review(row)

def test_event_chain_requires_strictly_increasing_real_world_time():
    with pytest.raises(ObjectionLifecycleHold, match="noncausal_or_tied"):
        review(event("PERSON_STATED_CONCERN", 4),
               event("HUMAN_EXPLANATION_SENT", 3))

def test_provider_event_replay_is_not_an_independent_second_message():
    e = event("PERSON_STATED_CONCERN", 1)
    with pytest.raises(ObjectionLifecycleHold, match="duplicate_or_invalid"):
        review(e, e)

def test_explanation_for_wrong_concern_must_not_close_previous_one():
    with pytest.raises(ObjectionLifecycleHold, match="reply_cannot_resolve"):
        review(event("PERSON_STATED_CONCERN", 1, PRICE),
               event("HUMAN_EXPLANATION_SENT", 2, PRIVACY))

def test_resolved_concern_cannot_be_resolved_again_without_new_objection():
    with pytest.raises(ObjectionLifecycleHold, match="resolution_without_open"):
        review(event("PERSON_STATED_CONCERN", 1),
               event("PERSON_EXPLICITLY_CONFIRMED_RESOLVED", 2),
               event("PERSON_EXPLICITLY_CONFIRMED_RESOLVED", 3))

def test_founder_projection_rejects_objection_source_that_claims_revenue_or_power():
    v = review(event("PERSON_STATED_CONCERN", 1))
    v["outbound_sent"] = True
    with pytest.raises(ObjectionLifecycleHold, match="untrusted_founder"):
        founder_objection_lifecycle_status(v)

def test_never_publish_case_identifiers_or_emotion_labels():
    v = review(event("PERSON_STATED_CONCERN", 1))
    assert CASE not in str(v)
    assert "event_digest" not in str(v)
    assert "emotion" not in str(founder_objection_lifecycle_status(v)).lower()

def test_absent_founder_source_is_not_authenticated():
    f = founder_objection_lifecycle_status(None)
    assert f["status"] == "NOT_CONNECTED"
    assert f["send_authorized"] is False
    assert f["source_authenticated"] is False


def test_original_prime_bridge_sees_only_reduced_status_not_private_case():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    lifecycle = review(
        event("PERSON_STATED_CONCERN", 1),
        event("HUMAN_EXPLANATION_SENT", 2),
        event("PERSON_EXPLICITLY_CONFIRMED_RESOLVED", 3),
    )
    brain = build_predictive_revenue_brain_review(
        tenant_id="synthetic-original-tenant", as_of=NOW,
        original_objection_lifecycle_shadow=lifecycle,
    )
    status = brain["prime_objection_lifecycle_shadow"]
    assert status["status"] == "ORIGINAL_OWNER_OBJECTION_LIFECYCLE_SHADOW_ONLY"
    assert status["objection_resolved_independently_verified"] is False
    assert status["send_authorized"] is False
    assert "private_case_state_counts_not_verified_truth" not in str(status)
    assert CASE not in str(status)
    assert brain["prime_first_buyer_intent_independently_verified"] is False
    assert brain["recognized_revenue_cents"] is None
    assert brain["outbound_sent"] is False
    assert brain["database_writes"] is False

def test_original_prime_bridge_missing_case_stays_unknown():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    brain = build_predictive_revenue_brain_review(
        tenant_id="synthetic-original-tenant", as_of=NOW,
    )
    assert brain["prime_objection_lifecycle_shadow"]["status"] == "NOT_CONNECTED"
    assert brain["prime_objection_lifecycle_shadow"]["source_authenticated"] is False

def test_original_prime_bridge_refuses_fake_resolution_authority():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    lifecycle = review(event("PERSON_STATED_CONCERN", 1))
    lifecycle["provider_and_tenant_authentication_verified_by_this_module"] = True
    with pytest.raises(ObjectionLifecycleHold, match="untrusted_founder"):
        build_predictive_revenue_brain_review(
            tenant_id="synthetic-original-tenant", as_of=NOW,
            original_objection_lifecycle_shadow=lifecycle,
        )

def test_original_prime_bridge_honors_terminal_optout_without_sending():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    status = review(event("PERSON_STATED_CONCERN", 1), event("PERSON_OPTED_OUT", 2))
    brain = build_predictive_revenue_brain_review(
        tenant_id="synthetic-original-tenant", as_of=NOW,
        original_objection_lifecycle_shadow=status,
    )
    assert brain["prime_objection_lifecycle_shadow"]["status"] == "EXPLICIT_OPT_OUT_OWNER_SUPPRESSION_REVIEW_REQUIRED"
    assert brain["outbound_sent"] is False
    assert brain["payment_executed"] is False


@pytest.mark.parametrize("tamper", [
    {"source_absence_not_interpreted_as_no_objections": True},
    {"contact_stop_or_suppression_review_required": True},
    {"private_case_state_counts_not_verified_truth": {"open": 500, "awaiting": 0, "person_reported": 0}},
    {"private_case_state_counts_not_verified_truth": {"open": 0}},
    {"event_count_not_unique_people": 999},
    {"mode": "PRODUCTION"},
    {"person_reported_resolution_not_provider_authenticated": False},
    {"raw_message_body": "this is private"},
])
def test_founder_rejects_forged_private_lifecycle_contract(tamper):
    source = review(event("PERSON_STATED_CONCERN", 1))
    source.update(tamper)
    with pytest.raises(ObjectionLifecycleHold):
        founder_objection_lifecycle_status(source)


def test_founder_refuses_fake_optout_without_matching_owner_hold():
    source = review(event("PERSON_STATED_CONCERN", 1))
    source["status"] = "EXPLICIT_OPT_OUT_OWNER_SUPPRESSION_REVIEW_REQUIRED"
    with pytest.raises(ObjectionLifecycleHold, match="inconsistent_private"):
        founder_objection_lifecycle_status(source)


def test_no_events_is_not_a_claim_of_customer_satisfaction():
    source = review_objection_lifecycle(case_digest=CASE, events=None, as_of=NOW)
    assert source["private_case_state_counts_not_verified_truth"] is None
    assert source["person_reported_resolution_not_provider_authenticated"] is True
    assert founder_objection_lifecycle_status(source)["objection_resolved_independently_verified"] is False
