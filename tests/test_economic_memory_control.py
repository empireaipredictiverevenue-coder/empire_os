# EMPIRE_WAVE_091B
from empire_os.economic_memory_control import (
    build_control,
)


def test_payment_event_canonicalises():

    d = build_control(
        [
            (
                "runtime/x.json",
                {
                    "payment_id":
                        "pay-1",

                    "amount":
                        "100.00",

                    "currency":
                        "USD",
                },
            )
        ]
    )

    assert (
        d[
            "canonical_identity"
        ][
            "canonical_event_count"
        ]
        == 1
    )


def test_duplicate_payment_collapses():

    value = {
        "payment_id":
            "pay-1",

        "amount":
            "100",

        "currency":
            "USD",
    }

    d = build_control(
        [
            (
                "runtime/a.json",
                value,
            ),
            (
                "runtime/b.json",
                value,
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
            "canonical_identity"
        ][
            "canonical_event_count"
        ]
        == 1
    )


def test_conflicting_amount_quarantines():

    d = build_control(
        [
            (
                "runtime/a.json",
                {
                    "payment_id":
                        "pay-1",

                    "amount":
                        "100",

                    "currency":
                        "USD",
                },
            ),
            (
                "runtime/b.json",
                {
                    "payment_id":
                        "pay-1",

                    "amount":
                        "200",

                    "currency":
                        "USD",
                },
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
            "canonical_identity"
        ][
            "canonical_event_count"
        ]
        == 0
    )


def test_event_without_stable_id_quarantines():

    d = build_control(
        [
            (
                "runtime/x.json",
                {
                    "revenue":
                        "100",

                    "currency":
                        "USD",
                },
            )
        ]
    )

    assert (
        d[
            "canonical_identity"
        ][
            "canonical_event_count"
        ]
        == 0
    )

    assert (
        d[
            "quarantine"
        ][
            "quarantine_count"
        ]
        >= 1
    )


def test_real_relation_creates_outcome_link():

    d = build_control(
        [
            (
                "runtime/x.json",
                {
                    "payment_id":
                        "pay-1",

                    "order_id":
                        "order-1",

                    "amount":
                        "100",

                    "currency":
                        "USD",
                },
            )
        ]
    )

    assert (
        len(
            d[
                "linked_outcomes"
            ]
        )
        == 1
    )

    assert (
        d[
            "control_effectiveness"
        ][
            "outcome_linkage"
        ]
        is True
    )


def test_empty_runtime_does_not_fake_controls():

    d = build_control([])

    assert (
        d[
            "control_effectiveness"
        ][
            "canonical_identity"
        ]
        is False
    )

    assert (
        d[
            "control_effectiveness"
        ][
            "outcome_linkage"
        ]
        is False
    )
