"""Evidence-only opportunity prioritisation; no automated customer actions."""
from datetime import datetime, timezone, timedelta

import pytest

from empire_os.inbound_business_hours import BusinessHoursPolicy, StaffedWindow
from empire_os.inbound_opportunity_intelligence import (
    OpportunityPolicy, OpportunitySignal, build_opportunity_queue,
)
from empire_os.inbound_revenue_recovery import RecoveryEvent

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def event(kind, minute=0, *, call="C1", tenant="business-1",
          verified=None, synthetic=False, evidence=None):
    if verified is None:
        verified = kind in {"unanswered", "busy", "answered", "callback_connected", "booking_confirmed", "booking_cancelled"}
    origin = {
        "unanswered": "provider", "busy": "provider",
        "answered": "provider", "callback_connected": "provider",
        "booking_confirmed": "calendar", "booking_cancelled": "calendar",
    }.get(kind, "operator")
    return RecoveryEvent(
        tenant_id=tenant, call_id=call,
        event_id=f"{call}-{kind}-{minute}",
        occurred_at=(NOW + timedelta(minutes=minute)).isoformat(),
        kind=kind, origin=origin, verified=verified,
        synthetic=synthetic,
        evidence_ref=(evidence if evidence is not None else ("receipt-" + call + kind if verified else "")),
    )


def signal(kind, *, call="C1", confirmed=True, origin="human_reviewed",
           synthetic=False, tenant="business-1", observed_at=None, sid=None):
    return OpportunitySignal(
        tenant_id=tenant, call_id=call, kind=kind,
        signal_id=sid or ("signal-" + kind + call),
        observed_at=(observed_at or (NOW + timedelta(minutes=1))).isoformat(),
        origin=origin, human_confirmed=confirmed, synthetic=synthetic,
        evidence_ref="evidence-" + kind,
    )


def queue(events, *, minute=30, signals=(), policy=None, hours=None):
    return build_opportunity_queue(
        events, policy=policy or OpportunityPolicy("business-1"),
        as_of=NOW + timedelta(minutes=minute),
        business_hours=hours, signals=signals,
    )


def test_verified_missed_call_triggers_human_triage_not_outbound():
    report = queue([event("unanswered")])
    assert report["queue_total"] == 1
    ticket = report["tickets"][0]
    assert ticket["priority"] == "normal"
    assert ticket["suggested_internal_action"] == "operator_triage_missing_call"
    assert ticket["human_review_required"]
    assert not ticket["outbound_authorized"]
    assert not ticket["payment_authorized"]
    assert report["outbound_sent"] is False


def test_booking_request_gets_high_priority_with_clear_reason():
    report = queue([event("unanswered"), event("booking_requested", 2)], minute=21)
    item = report["tickets"][0]
    assert item["priority"] == "urgent_review"  # Overdue booking request.
    assert item["sla_target_minutes"] == 20
    assert item["sla_overdue_wall_clock"]
    assert "booking_requested" in item["priority_explanation"]
    assert not item["booking_authorized"]


def test_verified_connection_and_booking_clear_open_tickets():
    for completion in ("callback_connected", "booking_confirmed"):
        report = queue([
            event("unanswered"), event(completion, 3)
        ])
        assert report["tickets"] == []
        assert report["already_recovered_calls"] == 1


def test_unverified_missed_call_cannot_create_actionable_ticket():
    report = queue([event("unanswered", verified=False)])
    assert report["queue_total"] == 0
    assert report["unverified_missed_events_excluded"] == 1


def test_synthetic_and_cross_tenant_never_enter_queue():
    report = queue([
        event("unanswered", synthetic=True),
        event("unanswered", call="C2", tenant="other"),
    ])
    assert report["queue_total"] == 0


def test_optout_excludes_even_if_operator_event_unverified():
    report = queue([event("unanswered"), event("followup_opt_out", 2)])
    assert report["opted_out_calls_excluded"] == 1
    assert report["tickets"] == []


def test_model_inference_does_not_raise_priority():
    report = queue([
        event("unanswered"),
    ], signals=[signal("urgent_need", confirmed=False, origin="model_candidate")])
    assert report["tickets"][0]["priority"] == "normal"
    assert report["unverified_model_signals_ignored"] == 1
    assert report["tickets"][0]["human_confirmed_signal_count"] == 0


def test_human_attested_urgency_can_prioritise_but_never_execute():
    report = queue([
        event("unanswered")
    ], signals=[signal("urgent_need", confirmed=True)])
    assert report["tickets"][0]["priority"] == "urgent_review"
    assert report["tickets"][0]["priority_score"] == 50  # Urgent flag, not inferred income.
    assert report["customer_contact_authorized"] is False


def test_signal_from_before_missed_call_does_not_transfer_intent():
    report = queue([event("unanswered")], signals=[
        signal("urgent_need", observed_at=NOW - timedelta(minutes=5))
    ])
    assert report["tickets"][0]["priority"] == "normal"


def test_model_cannot_fake_human_confirmation():
    with pytest.raises(ValueError, match="human_confirmation"):
        signal("urgent_need", confirmed=True, origin="model_candidate")


def test_stale_opportunities_expire_from_action_queue():
    report = queue([event("unanswered")], minute=60 * 24 * 4)
    assert report["stale_calls_excluded"] == 1
    assert report["queue_total"] == 0


def test_future_events_not_counted():
    report = queue([event("unanswered", 60)], minute=20)
    assert report["queue_total"] == 0


def test_tenant_scope_applies_to_human_signals():
    report = queue([event("unanswered")], signals=[
        signal("urgent_need", tenant="other")
    ])
    assert report["tickets"][0]["priority"] == "normal"


def test_human_review_staffing_unknown_without_verified_schedule():
    report = queue([event("unanswered")])
    assert report["tickets"][0]["staffing_status"] == "unknown"
    assert report["next_staffed_open_at"] is None


def test_weekend_staffing_closed_even_for_high_priority():
    hours = BusinessHoursPolicy(
        tenant_id="business-1", timezone_name="Europe/London",
        windows=(StaffedWindow(0, "09:00", "17:00"),),
        verified=True,
    )
    saturday = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)
    missed = event("unanswered")
    report = build_opportunity_queue(
        [missed], policy=OpportunityPolicy("business-1"),
        as_of=saturday, business_hours=hours,
    )
    assert report["staffing_status"] == "verified_closed"
    assert report["tickets"] == []  # age beyond 72h, no made-up new work


def test_duplicate_event_replay_cannot_create_extra_tickets():
    missed = event("unanswered")
    report = queue([missed, missed, missed])
    assert report["queue_total"] == 1
    changed = RecoveryEvent(
        tenant_id=missed.tenant_id, event_id=missed.event_id,
        call_id="different", occurred_at=missed.occurred_at,
        kind="unanswered", origin="provider", verified=True, synthetic=False,
    )
    with pytest.raises(ValueError, match="conflicting_duplicate"):
        queue([missed, changed])


def test_queue_order_is_stable_and_capped():
    policy = OpportunityPolicy("business-1", max_tickets=2)
    events = [
        event("unanswered", call="C3"),
        event("unanswered", call="C1"),
        event("unanswered", call="C2"),
        event("booking_requested", 1, call="C2"),
    ]
    report = queue(events, policy=policy)
    assert report["queue_total"] == 3
    assert report["overflow_count"] == 1
    assert [r["call_id"] for r in report["tickets"]] == ["C2", "C1"]


def test_opportunity_policy_rejects_invalid_values():
    with pytest.raises(ValueError):
        OpportunityPolicy("business-1", general_sla_minutes=0)
    with pytest.raises(ValueError):
        OpportunityPolicy("business-1", max_tickets=True)


def test_naive_clock_and_mismatched_schedule_are_blocked():
    with pytest.raises(ValueError, match="timezone_aware"):
        build_opportunity_queue(
            [event("unanswered")], policy=OpportunityPolicy("business-1"),
            as_of=datetime(2026, 10, 20, 12),
        )
    with pytest.raises(ValueError, match="tenant_mismatch"):
        build_opportunity_queue(
            [event("unanswered")], policy=OpportunityPolicy("business-1"),
            as_of=NOW + timedelta(minutes=10),
            business_hours=BusinessHoursPolicy("other", "Europe/London"),
        )


def test_unverified_manual_claim_cannot_mark_recovered():
    # A "booking requested" is not a calendar-confirmed booking.
    report = queue([event("unanswered"), event("booking_requested", 2)])
    assert report["already_recovered_calls"] == 0
    assert report["queue_total"] == 1


def test_cancelled_booking_reopens_prior_missed_opportunity():
    booked = event("booking_confirmed", 3, evidence="appt-1")
    cancel = event("booking_cancelled", 4, evidence="appt-1")
    result = queue([event("unanswered"), booked, cancel])
    assert result["queue_total"] == 1
    assert result["already_recovered_calls"] == 0
    assert result["tickets"][0]["suggested_internal_action"] == "operator_triage_missing_call"
