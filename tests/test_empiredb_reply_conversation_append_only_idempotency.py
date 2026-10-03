from pathlib import Path


MIGRATION = Path(
    "migrations/empiredb/"
    "034_reply_conversation_append_only_idempotency.sql"
)


def source():
    return MIGRATION.read_text()


def event_fragment():
    text = source()
    start = text.index(
        "-- Conversation events are append-only."
    )
    end = text.index(
        "v_event_status := 'existing';",
        start,
    )
    return text[start:end]


def test_event_lookup_does_not_require_update_authority():
    fragment = event_fragment()
    assert "FOR UPDATE" not in fragment


def test_provider_event_insert_is_race_safe():
    text = source()

    assert (
        "ON CONFLICT (\n"
        "                conversation_id,\n"
        "                provider_event_id"
        in text
    )

    assert "DO NOTHING" in text
    assert (
        "canonical provider event unavailable after conflict"
        in text
    )


def test_payload_conflict_still_fails_closed():
    text = source()
    assert "provider event payload mismatch" in text


def test_no_authority_expansion():
    text = source()

    forbidden = (
        "GRANT UPDATE",
        "GRANT DELETE",
        "approve_bsc_payment_request",
        "record_bsc_payment_evidence",
        "fulfilment_order",
    )

    for token in forbidden:
        assert token not in text


def test_revenue_truth_remains_false():
    assert "'actual_revenue',false" in source()
