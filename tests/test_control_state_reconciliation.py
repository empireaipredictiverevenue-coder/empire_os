from dataclasses import dataclass

from empire_os.control_state_reconciliation import (
    active_entity_set,
    entity_generation_id,
    partition_control_signals,
    stale_entity_counts,
)


@dataclass
class Signal:
    entity: str


def payload():

    return {
        "decisions": [
            {
                "canonical":
                    "buyer.com",

                "entity_type":
                    "PUBLIC_DOMAIN",

                "lane_allowed":
                    True,

                "quarantine":
                    False,
            },
            {
                "canonical":
                    "john.smith",

                "entity_type":
                    "PERSON_LIKE_OR_UNKNOWN",

                "lane_allowed":
                    False,

                "quarantine":
                    True,
            },
        ]
    }


def test_active_set_contains_current_semantic_entities():

    active = active_entity_set(
        payload()
    )

    assert active == {
        "buyer.com",
        "john.smith",
    }


def test_historical_signal_separated():

    active = {
        "buyer.com"
    }

    current, stale = (
        partition_control_signals(
            [
                Signal(
                    "buyer.com"
                ),
                Signal(
                    "oldbuyer.com"
                ),
                Signal(
                    "__system__"
                ),
            ],
            active,
        )
    )

    assert len(current) == 2
    assert len(stale) == 1
    assert stale[0].entity == (
        "oldbuyer.com"
    )


def test_generation_is_deterministic():

    left = entity_generation_id(
        payload()
    )

    right = entity_generation_id(
        payload()
    )

    assert left == right
    assert len(left) == 24


def test_stale_counts():

    counts = stale_entity_counts(
        [
            Signal("old.com"),
            Signal("old.com"),
            Signal("current.com"),
        ],
        {
            "current.com"
        },
    )

    assert counts == {
        "old.com": 2
    }
