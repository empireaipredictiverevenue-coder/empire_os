# EMPIRE_WAVE_092B
from empire_os.conversations_replies_control import (
    adjudicate_records,
)


def valid():
    return {
        "message_id":
            "msg-1",

        "thread_id":
            "thread-1",

        "sender_email":
            "buyer@example.com",

        "classification":
            "positive_reply",

        "received_at":
            "2026-10-07T10:00:00Z",
    }


def test_valid_reply_canonicalises():

    d = adjudicate_records(
        [
            (
                "public.inbound_replies",
                valid(),
            )
        ]
    )

    assert (
        d[
            "semantic_effectiveness"
        ][
            "canonical_message_count"
        ]
        == 1
    )

    assert (
        d[
            "semantic_effectiveness"
        ][
            "outcome_link_count"
        ]
        == 1
    )


def test_duplicate_collapses():

    row = valid()

    d = adjudicate_records(
        [
            (
                "a",
                row,
            ),
            (
                "b",
                row,
            ),
        ]
    )

    assert (
        d[
            "duplicate_detection"
        ][
            "duplicate_count"
        ]
        == 1
    )

    assert (
        d[
            "semantic_effectiveness"
        ][
            "canonical_message_count"
        ]
        == 1
    )


def test_thread_collision_quarantines():

    a = valid()

    b = dict(a)

    b[
        "thread_id"
    ] = "thread-2"

    d = adjudicate_records(
        [
            (
                "public.inbound_replies",
                a,
            ),
            (
                "public.inbound_replies",
                b,
            ),
        ]
    )

    assert (
        d[
            "conflict_detection"
        ][
            "conflict_count"
        ]
        == 1
    )

    assert (
        d[
            "semantic_effectiveness"
        ][
            "canonical_message_count"
        ]
        == 0
    )


def test_missing_identity_holds():

    row = valid()

    row.pop(
        "sender_email"
    )

    d = adjudicate_records(
        [
            (
                "public.inbound_replies",
                row,
            )
        ]
    )

    assert (
        d[
            "semantic_effectiveness"
        ][
            "canonical_message_count"
        ]
        == 0
    )


def test_no_live_authority_claim():

    d = adjudicate_records(
        [
            (
                "public.inbound_replies",
                valid(),
            )
        ]
    )

    assert (
        d[
            "control_effectiveness"
        ][
            "action_authority"
        ]
        is False
    )

    assert (
        d[
            "governance"
        ][
            "mailbox_write"
        ]
        is False
    )
