import json

from empire_os.revenue_intent_observer import (
    normalize_community_intent,
    normalize_file,
)
from empire_os.signal_intent_actor_router import (
    route_signal_inbox,
)


def sample_payload():
    return {
        "schema_version":
            "empire.community_intent.v2",
        "mode":
            "OBSERVE",
        "observations":
            2,
        "top_observations": [
            {
                "id":
                    "signal-one",
                "title":
                    "Looking for an SEO expert",
                "snippet":
                    "Need help improving organic growth",
                "source_url":
                    "https://linkedin.com/posts/one",
                "niche":
                    "seo",
            },
            {
                "id":
                    "signal-two",
                "title":
                    "Need CRM automation help",
                "text":
                    "Looking for someone to automate HubSpot",
                "source_url":
                    "https://linkedin.com/posts/two",
                "niche":
                    "automation",
            },
        ],
    }


def test_normalization_emits_router_signal_envelopes():
    result = normalize_community_intent(
        sample_payload()
    )

    assert (
        result[
            "observation_count"
        ]
        == 2
    )

    signals = result[
        "signals"
    ]

    one = signals[
        "signal-one"
    ]

    assert (
        one[
            "source"
        ]
        == "community_intent"
    )

    assert (
        one[
            "status"
        ]
        == "unresolved"
    )

    assert isinstance(
        one[
            "raw"
        ][
            "community_intent"
        ],
        dict,
    )

    assert (
        one[
            "raw"
        ][
            "community_intent"
        ][
            "signal_id"
        ]
        == "signal-one"
    )


def test_normalized_signals_are_considered_by_router(
    tmp_path,
):
    result = normalize_community_intent(
        sample_payload()
    )

    routed = route_signal_inbox(
        result[
            "signals"
        ],
        queue=
            tmp_path
            / "queue.json",
        lock=
            tmp_path
            / "queue.lock",
        limit=50,
    )

    assert (
        routed[
            "considered"
        ]
        == 2
    )

    assert (
        routed[
            "routed"
        ]
        == 2
    )

    assert (
        routed[
            "execution_authority"
        ]
        == "none"
    )


def test_normalize_file_writes_direct_signal_mapping(
    tmp_path,
):
    source = (
        tmp_path
        / "source.json"
    )

    destination = (
        tmp_path
        / "normalized.json"
    )

    source.write_text(
        json.dumps(
            sample_payload()
        )
    )

    report = normalize_file(
        source,
        destination,
    )

    written = json.loads(
        destination.read_text()
    )

    assert (
        report[
            "observation_count"
        ]
        == 2
    )

    assert set(
        written
    ) == {
        "signal-one",
        "signal-two",
    }

    assert (
        written[
            "signal-one"
        ][
            "source"
        ]
        .endswith(
            "_intent"
        )
    )


def test_existing_intent_source_is_preserved():
    payload = sample_payload()

    payload[
        "top_observations"
    ][0][
        "source"
    ] = "reddit_intent"

    payload[
        "top_observations"
    ][0][
        "status"
    ] = "needs_review"

    result = normalize_community_intent(
        payload
    )

    one = result[
        "signals"
    ][
        "signal-one"
    ]

    assert (
        one[
            "source"
        ]
        == "reddit_intent"
    )

    assert (
        one[
            "status"
        ]
        == "needs_review"
    )
