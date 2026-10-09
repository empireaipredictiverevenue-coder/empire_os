from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from empire_os.revenue_leak_entity_observer import (
    observe_entity_revenue_leaks,
)


NOW = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)
START = NOW - timedelta(hours=24)


def intent(entity_id=None):
    return {
        "id": str(uuid4()),
        "entity_id": str(entity_id or uuid4()),
    }


def delivered(intent_id, *, when=NOW - timedelta(hours=1)):
    return {
        "id": str(uuid4()),
        "intent_id": intent_id,
        "event_type": "delivered",
        "occurred_at": when,
    }


def reply(
    intent_id,
    classification,
    *,
    when=NOW - timedelta(minutes=30),
):
    return {
        "id": str(uuid4()),
        "intent_id": intent_id,
        "classification": classification,
        "received_at": when,
    }


def test_delivered_without_commercial_reply_is_observed_leak():
    entity_id = uuid4()
    i = intent(entity_id)

    rows = observe_entity_revenue_leaks(
        intents=[i],
        events=[delivered(i["id"])],
        replies=[],
        start=START,
        end=NOW,
    )

    assert len(rows) == 1
    row = rows[0].as_dict()

    assert row["entity_id"] == str(entity_id)
    assert row["signal_type"] == "revenue_leak"
    assert row["truth_class"] == "OBSERVED"
    assert row["observed_zero_conversion"] is True
    assert row["delivered_count"] == 1
    assert row["commercial_reply_count"] == 0
    assert row["lost_revenue_cents"] is None
    assert row["expected_revenue_cents"] is None
    assert row["conversion_value_cents"] is None


@pytest.mark.parametrize(
    "classification",
    ["positive", "question", "objection"],
)
def test_commercial_reply_closes_zero_reply_leak(classification):
    i = intent()

    rows = observe_entity_revenue_leaks(
        intents=[i],
        events=[delivered(i["id"])],
        replies=[reply(i["id"], classification)],
        start=START,
        end=NOW,
    )

    assert rows == []


@pytest.mark.parametrize(
    "classification",
    ["unsubscribe", "spam", "negative", "unknown"],
)
def test_noncommercial_reply_does_not_fabricate_conversion(classification):
    i = intent()

    rows = observe_entity_revenue_leaks(
        intents=[i],
        events=[delivered(i["id"])],
        replies=[reply(i["id"], classification)],
        start=START,
        end=NOW,
    )

    assert len(rows) == 1
    assert rows[0].commercial_reply_count == 0


def test_missing_entity_lineage_is_ignored():
    i = {"id": str(uuid4()), "entity_id": None}

    rows = observe_entity_revenue_leaks(
        intents=[i],
        events=[delivered(i["id"])],
        replies=[],
        start=START,
        end=NOW,
    )

    assert rows == []


def test_non_delivered_events_do_not_create_leak():
    i = intent()
    e = delivered(i["id"])
    e["event_type"] = "sent"

    rows = observe_entity_revenue_leaks(
        intents=[i],
        events=[e],
        replies=[],
        start=START,
        end=NOW,
    )

    assert rows == []


def test_out_of_window_delivery_is_ignored():
    i = intent()

    rows = observe_entity_revenue_leaks(
        intents=[i],
        events=[
            delivered(
                i["id"],
                when=START - timedelta(seconds=1),
            )
        ],
        replies=[],
        start=START,
        end=NOW,
    )

    assert rows == []


def test_duplicate_delivery_event_is_deduplicated():
    i = intent()
    e = delivered(i["id"])

    rows = observe_entity_revenue_leaks(
        intents=[i],
        events=[e, dict(e)],
        replies=[],
        start=START,
        end=NOW,
    )

    assert len(rows) == 1
    assert rows[0].delivered_count == 1


def test_evidence_is_exact_and_deterministic():
    i = intent()
    e = delivered(i["id"])

    rows = observe_entity_revenue_leaks(
        intents=[i],
        events=[e],
        replies=[],
        start=START,
        end=NOW,
    )

    assert rows[0].evidence_refs == tuple(
        sorted(
            {
                f"canonical:outbound_intents:{i['id']}",
                f"canonical:outbound_events:{e['id']}",
            }
        )
    )


def test_no_authority_expansion():
    i = intent()

    row = observe_entity_revenue_leaks(
        intents=[i],
        events=[delivered(i["id"])],
        replies=[],
        start=START,
        end=NOW,
    )[0].as_dict()

    assert row["execution_authority"] == "none"
    assert row["commercial_authority"] == "none"
    assert row["payment_authority"] == "none"
    assert row["traffic_authority"] == "none"
    assert row["review_required"] is True


def test_window_is_bounded_to_31_days():
    with pytest.raises(ValueError, match="31 days"):
        observe_entity_revenue_leaks(
            intents=[],
            events=[],
            replies=[],
            start=NOW - timedelta(days=32),
            end=NOW,
        )


def test_timestamps_must_be_timezone_aware():
    with pytest.raises(ValueError, match="timezone"):
        observe_entity_revenue_leaks(
            intents=[],
            events=[],
            replies=[],
            start=datetime(2026, 10, 5),
            end=NOW,
        )


def test_conflicting_intent_entity_lineage_fails_closed():
    intent_id = str(uuid4())

    with pytest.raises(ValueError, match="conflicting entity lineage"):
        observe_entity_revenue_leaks(
            intents=[
                {"id": intent_id, "entity_id": str(uuid4())},
                {"id": intent_id, "entity_id": str(uuid4())},
            ],
            events=[],
            replies=[],
            start=START,
            end=NOW,
        )
