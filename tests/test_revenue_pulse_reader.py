from datetime import datetime, timedelta, timezone

from empire_os.revenue_pulse_reader import (
    fetch_current_and_previous_windows,
    fetch_revenue_pulse_window,
)


NOW = datetime(2026, 9, 20, 23, 30, tzinfo=timezone.utc)


def fake_reader(path, params):
    assert "and" in params
    if path.endswith("/prospect_acquisitions"):
        return [{"id": "a1"}, {"id": "a2"}]
    if path.endswith("/prospect_qualifications"):
        assert params["status"] == "eq.scored"
        return [{"id": "q1", "status": "scored"}]
    if path.endswith("/buyer_candidate_reviews"):
        return [
            {
                "id": "r1",
                "status": "approved",
                "evidence": {
                    "outreach_ready": True,
                    "verified_contacts": [
                        {
                            "email": "owner@example.test",
                            "bound_to_decision_maker": True,
                            "is_valid": True,
                        }
                    ],
                },
            },
            {
                "id": "r2",
                "status": "approved",
                "evidence": {
                    "outreach_ready": False,
                    "verified_contacts": [],
                },
            },
        ]
    if path.endswith("/outbound_events"):
        assert params["event_type"] == "eq.delivered"
        return [{"id": "o1", "event_type": "delivered"}]
    if path.endswith("/outbound_replies"):
        return [
            {"id": "p1", "classification": "positive"},
            {"id": "p2", "classification": "unsubscribe"},
        ]
    if path.endswith("/commercial_terms_reviews"):
        return []
    if path.endswith("/bsc_payment_evidence"):
        return []
    if path.endswith("/fulfilment_orders"):
        return []
    if path.endswith("/commercial_events"):
        assert params["event_type"] == "eq.revenue_recognized"
        return [
            {
                "id": "rev1",
                "amount_cents": 25000,
                "margin_cents": 9000,
            }
        ]
    raise AssertionError(path)


def test_reader_builds_canonical_window_without_inference():
    window = fetch_revenue_pulse_window(
        fake_reader,
        label="current_24h",
        start=NOW - timedelta(hours=24),
        end=NOW,
    )

    assert window.acquisitions == 2
    assert window.qualified == 1
    assert window.buyer_reviews == 1
    assert window.delivered_outreach == 1
    assert window.commercial_replies == 1
    assert window.commercial_terms == 0
    assert window.verified_payments == 0
    assert window.fulfilments == 0
    assert window.recognized_revenue_cents == 25000
    assert window.realized_gp_cents == 9000


def test_reader_uses_two_separate_windows():
    calls = []

    def reader(path, params):
        calls.append((path, params["and"]))
        return []

    current, previous = fetch_current_and_previous_windows(
        reader,
        now=NOW,
        hours=24,
    )

    assert current.label == "current_24h"
    assert previous.label == "previous_24h"
    assert current.hours == 24
    assert previous.hours == 24
    assert len(calls) == 18
    current_filters = {f for _, f in calls[:9]}
    previous_filters = {f for _, f in calls[9:]}
    assert current_filters != previous_filters


def test_reader_rejects_invalid_window():
    try:
        fetch_revenue_pulse_window(
            fake_reader,
            label="bad",
            start=NOW,
            end=NOW,
        )
    except ValueError as exc:
        assert "end must be after start" in str(exc)
    else:
        raise AssertionError("invalid window must fail")
