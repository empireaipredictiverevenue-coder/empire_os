from datetime import datetime, timezone

import pytest

from empire_os.circuit_breaker import (
    CLOSED,
    HALF_OPEN,
    OPEN,
    evaluate_lane_circuit,
    evaluate_provider_circuit,
)

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def event(at: str):
    return {"at": at}


def failures(*times: str):
    return [event(value) for value in times]


def test_closed_without_failures():
    result = evaluate_lane_circuit("lane:roofing", now=NOW)
    assert result["state"] == CLOSED
    assert result["failure_count_recent"] == 0
    assert result["can_accept"] is True
    assert result["side_effects"] == "none"


def test_open_when_threshold_breached_and_cooldown_active():
    rows = failures(
        "2026-09-20T11:50:00+00:00",
        "2026-09-20T11:51:00+00:00",
        "2026-09-20T11:52:00+00:00",
    )
    result = evaluate_lane_circuit(
        "lane:roofing",
        failure_events=rows,
        failure_threshold=3,
        cooldown_seconds=600,
        now=NOW,
    )
    assert result["state"] == OPEN
    assert result["reason"] == "failure_threshold_breached_cooldown_active"
    assert result["can_accept"] is False
    assert result["trip_at"] == "2026-09-20T11:52:00+00:00"


def test_half_open_after_cooldown_elapsed():
    rows = failures(
        "2026-09-20T11:00:00+00:00",
        "2026-09-20T11:01:00+00:00",
        "2026-09-20T11:02:00+00:00",
    )
    result = evaluate_lane_circuit(
        "lane:roofing",
        failure_events=rows,
        failure_threshold=3,
        cooldown_seconds=300,
        now=NOW,
    )
    assert result["state"] == HALF_OPEN
    assert result["reason"] == "cooldown_elapsed_probe_allowed"
    assert result["can_accept"] is True


def test_success_after_trip_closes_circuit():
    rows = failures(
        "2026-09-20T11:40:00+00:00",
        "2026-09-20T11:41:00+00:00",
        "2026-09-20T11:42:00+00:00",
    )
    result = evaluate_lane_circuit(
        "lane:roofing",
        failure_events=rows,
        success_events=[event("2026-09-20T11:45:00+00:00")],
        failure_threshold=3,
        cooldown_seconds=600,
        now=NOW,
    )
    assert result["state"] == CLOSED
    assert result["reason"] == "success_after_trip"
    assert result["last_success_at"] == "2026-09-20T11:45:00+00:00"


def test_old_failures_do_not_count_as_recent_but_preserve_trip_history():
    rows = failures(
        "2026-09-20T08:00:00+00:00",
        "2026-09-20T08:01:00+00:00",
        "2026-09-20T08:02:00+00:00",
    )
    result = evaluate_lane_circuit(
        "lane:roofing",
        failure_events=rows,
        failure_threshold=3,
        cooldown_seconds=300,
        now=NOW,
    )
    assert result["failure_count_recent"] == 0
    assert result["state"] == HALF_OPEN


def test_future_and_invalid_events_are_ignored():
    rows = [
        event("not-a-time"),
        event("2026-09-20T12:30:00+00:00"),
        event("2026-09-20T11:59:00+00:00"),
    ]
    result = evaluate_lane_circuit(
        "lane:roofing",
        failure_events=rows,
        failure_threshold=2,
        now=NOW,
    )
    assert result["state"] == CLOSED
    assert result["failure_count_recent"] == 1


def test_provider_key_is_namespaced():
    result = evaluate_provider_circuit(
        "resend",
        failure_events=failures(
            "2026-09-20T11:58:00+00:00",
            "2026-09-20T11:59:00+00:00",
        ),
        failure_threshold=2,
        cooldown_seconds=300,
        now=NOW,
    )
    assert result["key"] == "provider:resend"
    assert result["state"] == OPEN


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"failure_threshold": 0}, "failure_threshold"),
        ({"failure_window_seconds": 0}, "failure_window_seconds"),
        ({"cooldown_seconds": -1}, "cooldown_seconds"),
    ],
)
def test_invalid_configuration_fails_closed(kwargs, message):
    with pytest.raises(ValueError, match=message):
        evaluate_lane_circuit("lane:roofing", now=NOW, **kwargs)


def test_naive_now_is_rejected():
    with pytest.raises(ValueError, match="timezone"):
        evaluate_lane_circuit(
            "lane:roofing",
            now=datetime(2026, 9, 20, 12, 0),
        )


def test_same_evidence_and_clock_is_deterministic():
    rows = failures(
        "2026-09-20T11:58:00+00:00",
        "2026-09-20T11:59:00+00:00",
    )
    left = evaluate_provider_circuit(
        "resend",
        failure_events=rows,
        failure_threshold=2,
        now=NOW,
    )
    right = evaluate_provider_circuit(
        "resend",
        failure_events=rows,
        failure_threshold=2,
        now=NOW,
    )
    assert left == right
