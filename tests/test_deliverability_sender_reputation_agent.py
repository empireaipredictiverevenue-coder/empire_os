from empire_os.deliverability_sender_reputation_agent import (
    build_deliverability_state,
    deliverability_agent_status,
)


def test_hard_failures_become_suppression_candidates_only():
    row = build_deliverability_state([
        {"event_type": "sent", "recipient": "a@example.com"},
        {"event_type": "hard_bounce", "recipient": "a@example.com"},
    ])
    assert row.suppression_candidates == ("a@example.com",)
    assert row.recommended_action == "suppress_proven_hard_failures"
    assert row.action_performed is False
    assert row.outbound_send_authority is False


def test_high_hard_bounce_rate_recommends_lane_pause_review():
    events = [{"event_type": "sent"} for _ in range(20)]
    events += [{"event_type": "hard_bounce"} for _ in range(2)]
    row = build_deliverability_state(events)
    assert row.hard_bounce_rate == 0.1
    assert row.recommended_action == "pause_sender_lane_review"


def test_high_deferral_rate_recommends_cap_reduction_review():
    events = [{"event_type": "sent"} for _ in range(20)]
    events += [{"event_type": "deferred"} for _ in range(5)]
    row = build_deliverability_state(events)
    assert row.deferral_rate == 0.25
    assert row.recommended_action == "reduce_cap_review"


def test_unknown_volume_keeps_rates_unknown():
    row = build_deliverability_state([])
    assert row.delivery_rate is None
    assert row.hard_bounce_rate is None
    assert row.composite_reputation_score is None


def test_status_has_no_consequential_authority():
    row = deliverability_agent_status()
    assert row["outbound_send_authority"] is False
    assert row["dns_mutation_authority"] is False
    assert row["payment_authority"] is False
    assert row["revenue_recognition_authority"] is False
