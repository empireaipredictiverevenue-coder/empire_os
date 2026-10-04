import json

from empire_os.revenue_identity_handoff import (
    process_identity_handoffs,
)


def write_queue(
    path,
    *,
    decision,
):
    path.write_text(
        json.dumps({
            "schema_version":
                "empire.revenue_actor_queue.v1",
            "jobs": {
                "job-one": {
                    "status":
                        "completed",
                    "source_ref":
                        "signal_inbox:sig-one",
                    "payload": {
                        "signal_id":
                            "sig-one",
                        "title":
                            "Need an SEO agency",
                        "text":
                            "Looking for an SEO team",
                        "url":
                            "https://linkedin.com/posts/example",
                        "niche":
                            "seo",
                    },
                    "result": {
                        "decision":
                            decision,
                        "governance": {
                            "execution_authority":
                                "none",
                        },
                    },
                },
            },
        })
    )


def test_watch_does_not_enter_identity(
    tmp_path,
):
    queue = tmp_path / "queue.json"
    state = tmp_path / "state.json"
    lock = tmp_path / "state.lock"

    write_queue(
        queue,
        decision="WATCH",
    )

    calls = {
        "business": 0,
    }

    def business(payload):
        calls["business"] += 1
        raise AssertionError(
            "WATCH must not enter identity"
        )

    result = process_identity_handoffs(
        queue=queue,
        state=state,
        lock=lock,
        business_runner=business,
    )

    assert result["eligible"] == 0
    assert result["business_attempted"] == 0
    assert calls["business"] == 0
    assert result["execution_authority"] == "none"


def test_resolve_identity_enters_business_only_when_unverified(
    tmp_path,
):
    queue = tmp_path / "queue.json"
    state = tmp_path / "state.json"
    lock = tmp_path / "state.lock"

    write_queue(
        queue,
        decision="RESOLVE_IDENTITY",
    )

    def business(payload):
        assert (
            payload[
                "upstream_decision"
            ]
            == "RESOLVE_IDENTITY"
        )

        return {
            "decision":
                "BUSINESS_IDENTITY_UNRESOLVED",
            "output": {
                "business_identity": {
                    "business_identity_verified":
                        False,
                    "business_name":
                        None,
                    "website":
                        None,
                }
            },
            "governance": {
                "execution_authority":
                    "none",
            },
        }

    def first_party(payload):
        raise AssertionError(
            "unverified business must not "
            "enter first-party identity"
        )

    result = process_identity_handoffs(
        queue=queue,
        state=state,
        lock=lock,
        business_runner=business,
        first_party_runner=first_party,
    )

    assert result["eligible"] == 1
    assert result["business_attempted"] == 1
    assert result["first_party_attempted"] == 0
    assert result["stopped"] == 1


def test_verified_business_enters_first_party(
    tmp_path,
):
    queue = tmp_path / "queue.json"
    state = tmp_path / "state.json"
    lock = tmp_path / "state.lock"

    write_queue(
        queue,
        decision="RESOLVE_IDENTITY",
    )

    def business(payload):
        return {
            "decision":
                "BUSINESS_IDENTITY_VERIFIED",
            "output": {
                "business_identity": {
                    "business_identity_verified":
                        True,
                    "business_name":
                        "Example Roofing Ltd",
                    "website":
                        "https://example-roofing.co.uk",
                }
            },
            "governance": {
                "execution_authority":
                    "none",
            },
        }

    def first_party(payload):
        assert (
            payload[
                "business_name"
            ]
            == "Example Roofing Ltd"
        )

        assert (
            payload[
                "website"
            ]
            == "https://example-roofing.co.uk"
        )

        assert (
            payload[
                "first_party_site_verified"
            ]
            is True
        )

        return {
            "decision":
                "IDENTITY_VERIFIED",
            "output": {
                "decision_maker": {
                    "name":
                        "Jane Example",
                }
            },
            "governance": {
                "execution_authority":
                    "none",
            },
        }

    result = process_identity_handoffs(
        queue=queue,
        state=state,
        lock=lock,
        business_runner=business,
        first_party_runner=first_party,
    )

    assert result["eligible"] == 1
    assert result["business_attempted"] == 1
    assert result["first_party_attempted"] == 1

    saved = json.loads(
        state.read_text()
    )

    assert (
        saved[
            "jobs"
        ][
            "job-one"
        ][
            "status"
        ]
        == "identity_verified"
    )


def test_handoff_is_idempotent(
    tmp_path,
):
    queue = tmp_path / "queue.json"
    state = tmp_path / "state.json"
    lock = tmp_path / "state.lock"

    write_queue(
        queue,
        decision="RESOLVE_IDENTITY",
    )

    calls = {
        "business": 0,
    }

    def business(payload):
        calls["business"] += 1

        return {
            "decision":
                "BUSINESS_IDENTITY_UNRESOLVED",
            "output": {
                "business_identity": {
                    "business_identity_verified":
                        False,
                }
            },
            "governance": {
                "execution_authority":
                    "none",
            },
        }

    first = process_identity_handoffs(
        queue=queue,
        state=state,
        lock=lock,
        business_runner=business,
    )

    second = process_identity_handoffs(
        queue=queue,
        state=state,
        lock=lock,
        business_runner=business,
    )

    assert first["business_attempted"] == 1
    assert second["business_attempted"] == 0
    assert second["deduplicated"] == 1
    assert calls["business"] == 1


def test_provider_degraded_is_retryable_not_terminal(
    tmp_path,
    monkeypatch,
):
    queue = tmp_path / "queue.json"
    state = tmp_path / "state.json"
    lock = tmp_path / "state.lock"

    write_queue(
        queue,
        decision="RESOLVE_IDENTITY",
    )

    def business(payload):
        return {
            "decision":
                "DISCOVERY_PROVIDER_DEGRADED",
            "governance": {
                "execution_authority":
                    "none",
            },
        }

    result = process_identity_handoffs(
        queue=queue,
        state=state,
        lock=lock,
        business_runner=business,
    )

    assert result["business_attempted"] == 1

    saved = json.loads(
        state.read_text()
    )

    record = saved[
        "jobs"
    ][
        "job-one"
    ]

    assert (
        record["status"]
        == "retry_provider"
    )

    assert record[
        "retry_after"
    ] > record[
        "updated_at"
    ]
