from datetime import datetime, timedelta, timezone

from empire_os.revenue_pulse_reader import (
    fetch_current_and_previous_windows,
    fetch_revenue_pulse_window,
    fetch_revenue_pulse_window_postgres,
    fetch_current_and_previous_windows_postgres,
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



class _PulseCursor:
    def __init__(self, values):
        self.values = list(values)
        self.calls = []
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).split())
        self.calls.append((normalized, tuple(params or ())))
        if normalized.startswith(
            "SELECT public.get_revenue_pulse_window"
        ):
            self.row = (self.values.pop(0),)

    def fetchone(self):
        return self.row


class _PulseConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self._cursor


def _pulse_raw(acquisitions=2, delivered=1):
    return {
        "acquisitions": acquisitions,
        "qualified": 1,
        "buyer_reviews": 1,
        "delivered_outreach": delivered,
        "commercial_replies": 0,
        "commercial_terms": 0,
        "verified_payments": 0,
        "fulfilments": 0,
        "recognized_revenue_cents": 0,
        "realized_gp_cents": 0,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def test_postgres_reader_uses_restricted_role():
    cursor = _PulseCursor([_pulse_raw()])

    def connect(dsn):
        assert dsn == "postgresql://restricted/pulse"
        return _PulseConnection(cursor)

    window = fetch_revenue_pulse_window_postgres(
        "postgresql://restricted/pulse",
        label="current_24h",
        start=NOW - timedelta(hours=24),
        end=NOW,
        connect_factory=connect,
    )

    assert window.acquisitions == 2
    assert window.delivered_outreach == 1
    assert window.commercial_replies == 0
    assert window.recognized_revenue_cents == 0
    assert cursor.calls[0] == (
        "SET LOCAL ROLE empire_intelligence_materializer",
        (),
    )
    assert cursor.calls[1][0].startswith(
        "SELECT public.get_revenue_pulse_window"
    )


def test_postgres_current_previous_are_separate_windows():
    cursor = _PulseCursor([
        _pulse_raw(acquisitions=4, delivered=2),
        _pulse_raw(acquisitions=1, delivered=0),
    ])

    def connect(_dsn):
        return _PulseConnection(cursor)

    current, previous = fetch_current_and_previous_windows_postgres(
        "postgresql://restricted/pulse",
        now=NOW,
        hours=24,
        connect_factory=connect,
    )

    assert current.acquisitions == 4
    assert previous.acquisitions == 1
    assert current.delivered_outreach == 2
    assert previous.delivered_outreach == 0
