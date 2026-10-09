# EMPIRE_WAVE_090C_B
from empire_os.consent_suppression_control import (
    build_snapshot,
    extract_identity_candidates,
    normalize_email,
    normalize_phone,
)


def test_email_normalization():

    assert (
        normalize_email(
            "  Person@Example.COM "
        )
        == "person@example.com"
    )


def test_phone_without_country_is_quarantined():

    value, international = (
        normalize_phone(
            "020 7946 0000"
        )
    )

    assert value
    assert international is False


def test_extract_generic_email_contract():

    rows = extract_identity_candidates(
        {
            "channel":
                "email",

            "recipient":
                "x@example.com",
        }
    )

    assert len(rows) == 1
    assert rows[0][
        "entity_type"
    ] == "EMAIL"


def test_snapshot_never_allows():

    snapshot = build_snapshot(
        [
            {
                "id":
                    1,

                "email":
                    "blocked@example.com",

                "reason":
                    "unsubscribe",
            }
        ]
    )

    assert (
        snapshot[
            "output_quality"
        ][
            "allow_decision_count"
        ]
        == 0
    )

    assert (
        snapshot[
            "output_quality"
        ][
            "block_count"
        ]
        == 1
    )


def test_duplicate_detection():

    snapshot = build_snapshot(
        [
            {
                "id": 1,
                "email":
                    "same@example.com",
            },
            {
                "id": 2,
                "email":
                    "SAME@example.com",
            },
        ]
    )

    assert (
        snapshot[
            "duplicate_detection"
        ][
            "duplicate_count"
        ]
        == 1
    )


def test_conflicting_states_hold():

    snapshot = build_snapshot(
        [
            {
                "id": 1,
                "email":
                    "same@example.com",
                "active":
                    True,
            },
            {
                "id": 2,
                "email":
                    "same@example.com",
                "active":
                    False,
            },
        ]
    )

    assert (
        snapshot[
            "conflict_detection"
        ][
            "conflict_count"
        ]
        == 1
    )

    assert all(
        item[
            "recommended_action"
        ]
        == "HOLD"
        for item
        in snapshot[
            "records"
        ]
    )


def test_raw_pii_not_required_in_output_contract():

    snapshot = build_snapshot(
        [
            {
                "id": 1,
                "email":
                    "secret@example.com",
            }
        ]
    )

    encoded = str(
        snapshot[
            "records"
        ]
    )

    assert (
        "secret@example.com"
        not in encoded
    )
