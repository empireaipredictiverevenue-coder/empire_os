from datetime import datetime, timedelta, timezone

from empire_os.conversation_recovery import (
    build_conversation_recovery,
    parse_delivered_events,
)


NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def test_recovery_hydrates_legacy_placeholder_context():
    intents = [{
        "id": "i1",
        "prospect_id": "p1",
        "recipient": "buyer@example.com",
        "subject": "Jim — local market opportunities in your market",
        "status": "delivered",
        "metadata": {
            "candidate_evidence": {
                "business_name": "your team",
                "niche": "local market",
                "metro": "your market",
            }
        },
    }]
    events = {"i1": NOW - timedelta(hours=60)}
    prospects = {
        "p1": {
            "business_name": "RCG Nashville",
            "niche": "roofing",
            "metro": "Nashville",
            "rating": 4.8,
            "review_count": 90,
        }
    }
    result = build_conversation_recovery(
        intents, events, prospects, now=NOW
    )
    item = result["items"][0]
    assert item["placeholder_evidence"] is False
    assert item["recoverable"] is True
    assert item["business_name"] == "RCG Nashville"
    assert item["due_within_24h"] is True
    assert item["legacy_generic_subject"] is True


def test_72_hour_cadence_is_not_shortened():
    intents = [{
        "id": "i1",
        "prospect_id": "p1",
        "recipient": "buyer@example.com",
        "subject": "Clay — one thing I noticed in Wichita",
        "status": "delivered",
        "metadata": {
            "candidate_evidence": {
                "business_name": "Kihle Roofing",
                "niche": "roofing",
                "metro": "Wichita",
            }
        },
    }]
    result = build_conversation_recovery(
        intents,
        {"i1": NOW - timedelta(hours=19)},
        {"p1": {"business_name": "Kihle Roofing", "niche": "roofing", "metro": "Wichita"}},
        now=NOW,
    )
    assert result["due_now"] == 0
    assert result["next_due_in_hours"] == 53.0
    assert result["proposal_created"] is False
    assert result["send_executed"] is False


def test_due_after_72_hours():
    intents = [{
        "id": "i1",
        "prospect_id": "p1",
        "recipient": "buyer@example.com",
        "subject": "Clay — one thing I noticed in Wichita",
        "status": "delivered",
        "metadata": {
            "candidate_evidence": {
                "business_name": "Kihle Roofing",
                "niche": "roofing",
                "metro": "Wichita",
            }
        },
    }]
    result = build_conversation_recovery(
        intents,
        {"i1": NOW - timedelta(hours=73)},
        {"p1": {"business_name": "Kihle Roofing", "niche": "roofing", "metro": "Wichita"}},
        now=NOW,
    )
    assert result["due_now"] == 1
    assert result["items"][0]["recovery_reason"] == "due_now"


def test_event_parser_keeps_latest_delivery():
    rows = [
        {"intent_id": "i1", "event_type": "delivered", "occurred_at": "2026-09-20T10:00:00Z"},
        {"intent_id": "i1", "event_type": "delivered", "occurred_at": "2026-09-20T11:00:00Z"},
    ]
    result = parse_delivered_events(rows)
    assert result["i1"].hour == 11
