from datetime import datetime, timezone

from empire_os.outbound_capacity_reservation import (
    plan_capacity_reservation,
    replay_capacity_reservations,
)


NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def test_plan_capacity_reservation_is_bounded_and_non_authorizing():
    result = plan_capacity_reservation(
        mailbox_key="sender:1",
        domain="mail.example.com",
        transport_key="transport:a",
        units=3,
        remaining_capacity=10,
        reservation_key="res:1",
        idempotency_key="idem:1",
        now=NOW,
        ttl_seconds=600,
    )
    assert result["status"] == "READY_TO_RESERVE"
    assert result["event"]["event_type"] == "RESERVE"
    assert result["event"]["units"] == 3
    assert result["mutation_authorized"] is False


def test_plan_capacity_reservation_blocks_oversubscription():
    result = plan_capacity_reservation(
        mailbox_key="sender:1",
        domain="mail.example.com",
        transport_key="transport:a",
        units=11,
        remaining_capacity=10,
        reservation_key="res:1",
        idempotency_key="idem:1",
        now=NOW,
    )
    assert result["status"] == "HOLD"
    assert "insufficient_remaining_capacity" in result["blockers"]


def test_duplicate_idempotency_retry_is_ignored():
    events = [
        {
            "id": "1",
            "mailbox_key": "sender:1",
            "event_type": "RESERVE",
            "units": 4,
            "reservation_key": "res:1",
            "idempotency_key": "idem:reserve:1",
            "lease_expires_at": "2026-10-03T12:30:00+00:00",
            "recorded_at": "2026-10-03T11:50:00+00:00",
        },
        {
            "id": "2",
            "mailbox_key": "sender:1",
            "event_type": "RESERVE",
            "units": 4,
            "reservation_key": "res:1",
            "idempotency_key": "idem:reserve:1",
            "lease_expires_at": "2026-10-03T12:30:00+00:00",
            "recorded_at": "2026-10-03T11:50:01+00:00",
        },
    ]
    result = replay_capacity_reservations(events, now=NOW)
    assert result["status"] == "CONVERGED"
    assert result["active_reserved_units"] == 4
    assert result["anomalies"] == []


def test_expired_reservation_proposes_append_only_release_recovery():
    events = [{
        "id": "1",
        "mailbox_key": "sender:1",
        "event_type": "RESERVE",
        "units": 5,
        "reservation_key": "res:1",
        "idempotency_key": "idem:reserve:1",
        "lease_expires_at": "2026-10-03T11:00:00+00:00",
        "recorded_at": "2026-10-03T10:00:00+00:00",
    }]
    result = replay_capacity_reservations(events, now=NOW)
    assert result["status"] == "RECOVERY_REQUIRED"
    assert result["expired_reserved_units"] == 5
    assert result["recovery_actions"][0]["action"] == "APPEND_RELEASE"
    assert result["recovery_actions"][0]["mutation_authorized"] is False


def test_consume_then_release_closes_reservation():
    events = [
        {
            "id": "1",
            "mailbox_key": "sender:1",
            "event_type": "RESERVE",
            "units": 5,
            "reservation_key": "res:1",
            "idempotency_key": "idem:reserve:1",
            "lease_expires_at": "2026-10-03T13:00:00+00:00",
            "recorded_at": "2026-10-03T11:00:00+00:00",
        },
        {
            "id": "2",
            "mailbox_key": "sender:1",
            "event_type": "CONSUME",
            "units": 3,
            "reservation_key": "res:1",
            "idempotency_key": "idem:consume:1",
            "recorded_at": "2026-10-03T11:10:00+00:00",
        },
        {
            "id": "3",
            "mailbox_key": "sender:1",
            "event_type": "RELEASE",
            "units": 2,
            "reservation_key": "res:1",
            "idempotency_key": "idem:release:1",
            "recorded_at": "2026-10-03T11:20:00+00:00",
        },
    ]
    result = replay_capacity_reservations(events, now=NOW)
    assert result["status"] == "CONVERGED"
    state = result["reservations"]["res:1"]
    assert state["consumed"] == 3
    assert state["released"] == 2
    assert state["remaining_reserved"] == 0
    assert state["terminal"] is True


def test_consume_exceeding_reserved_units_is_hold():
    events = [
        {
            "id": "1",
            "mailbox_key": "sender:1",
            "event_type": "RESERVE",
            "units": 2,
            "reservation_key": "res:1",
            "idempotency_key": "idem:reserve:1",
            "lease_expires_at": "2026-10-03T13:00:00+00:00",
            "recorded_at": "2026-10-03T11:00:00+00:00",
        },
        {
            "id": "2",
            "mailbox_key": "sender:1",
            "event_type": "CONSUME",
            "units": 3,
            "reservation_key": "res:1",
            "idempotency_key": "idem:consume:1",
            "recorded_at": "2026-10-03T11:10:00+00:00",
        },
    ]
    result = replay_capacity_reservations(events, now=NOW)
    assert result["status"] == "HOLD"
    assert "consume_exceeds_reserved_units" in result["anomalies"]
