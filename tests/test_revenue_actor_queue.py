import json
from pathlib import Path

from empire_os.revenue_actor_queue import (
    actor_queue_snapshot,
    enqueue_actor_job,
    process_actor_queue,
)
from empire_os.signal_intent_actor_router import (
    route_signal_inbox,
)


def owner_signal():
    return {
        "sig-owner": {
            "signal_id": "sig-owner",
            "status": "unresolved",
            "source": "reddit_intent",
            "niche": "roofing",
            "url":
                "https://reddit.com/r/roofing/1",
            "created_at":
                "2026-10-04T08:00:00+00:00",
            "last_seen_at":
                "2026-10-04T09:00:00+00:00",
            "raw": {
                "community_intent": {
                    "title":
                        "Need roofing appointments",
                    "text": (
                        "I own a roofing company. "
                        "We need 2-4 more qualified "
                        "appointments per week. "
                        "Google Ads are not profitable."
                    ),
                    "niche": "roofing",
                    "url":
                        "https://reddit.com/r/roofing/1",
                    "intent_score": 76,
                    "intent_band": "high",
                    "pain_points": [
                        "lead_generation",
                    ],
                    "evidence_urls": [],
                },
                "evidence_urls": [],
            },
        }
    }


def job_signal():
    return {
        "sig-job": {
            "signal_id": "sig-job",
            "status": "unresolved",
            "source": "reddit_intent",
            "niche": "b2b",
            "url":
                "https://reddit.com/r/sales/1",
            "created_at":
                "2026-10-04T08:00:00+00:00",
            "raw": {
                "community_intent": {
                    "title":
                        "Where should I take "
                        "my sales career?",
                    "text": (
                        "Need advice about which "
                        "jobs I should apply for. "
                        "I want to land a sales job."
                    ),
                    "niche": "b2b",
                    "url":
                        "https://reddit.com/r/sales/1",
                    "intent_score": 76,
                    "intent_band": "high",
                    "evidence_urls": [],
                }
            },
        }
    }


def paths(tmp_path: Path):
    return (
        tmp_path / "queue.json",
        tmp_path / "queue.lock",
    )


def test_queue_deduplicates_same_actor_input(
    tmp_path,
):
    queue, lock = paths(tmp_path)

    payload = {
        "title": "Need leads",
        "text": "I own a roofing company.",
    }

    first = enqueue_actor_job(
        "intent_brain",
        payload,
        source_ref="signal:sig-1",
        queue=queue,
        lock=lock,
    )

    second = enqueue_actor_job(
        "intent_brain",
        payload,
        source_ref="signal:sig-1",
        queue=queue,
        lock=lock,
    )

    assert first["created"] is True
    assert second["created"] is False
    assert first["job_id"] == second["job_id"]


def test_router_creates_durable_job(
    tmp_path,
):
    queue, lock = paths(tmp_path)

    result = route_signal_inbox(
        owner_signal(),
        queue=queue,
        lock=lock,
    )

    assert result["routed"] == 1
    assert result["execution_authority"] == "none"

    payload = json.loads(
        queue.read_text()
    )

    assert len(payload["jobs"]) == 1


def test_owner_signal_routes_to_identity_resolution(
    tmp_path,
):
    queue, lock = paths(tmp_path)

    route_signal_inbox(
        owner_signal(),
        queue=queue,
        lock=lock,
    )

    run = process_actor_queue(
        queue=queue,
        lock=lock,
    )

    assert run["completed"] == 1
    assert run["failed"] == 0

    saved = json.loads(
        queue.read_text()
    )

    job = next(iter(saved["jobs"].values()))

    assert job["status"] == "completed"
    assert (
        job["result"]["decision"]
        == "RESOLVE_IDENTITY"
    )
    assert (
        job["result"]["governance"]
        ["execution_authority"]
        == "none"
    )


def test_job_seeker_is_rejected_by_actor(
    tmp_path,
):
    queue, lock = paths(tmp_path)

    route_signal_inbox(
        job_signal(),
        queue=queue,
        lock=lock,
    )

    process_actor_queue(
        queue=queue,
        lock=lock,
    )

    snapshot = actor_queue_snapshot(queue)

    assert (
        snapshot["by_decision"]["REJECT"]
        == 1
    )


def test_second_route_is_idempotent(
    tmp_path,
):
    queue, lock = paths(tmp_path)

    first = route_signal_inbox(
        owner_signal(),
        queue=queue,
        lock=lock,
    )

    second = route_signal_inbox(
        owner_signal(),
        queue=queue,
        lock=lock,
    )

    assert first["routed"] == 1
    assert second["routed"] == 0
    assert second["deduplicated"] == 1


def test_resolved_signal_is_not_routed(
    tmp_path,
):
    queue, lock = paths(tmp_path)

    signal = owner_signal()
    signal["sig-owner"]["status"] = "resolved"

    result = route_signal_inbox(
        signal,
        queue=queue,
        lock=lock,
    )

    assert result["routed"] == 0
    assert result["skipped"] == 1


def test_completed_jobs_not_reprocessed(
    tmp_path,
):
    queue, lock = paths(tmp_path)

    route_signal_inbox(
        job_signal(),
        queue=queue,
        lock=lock,
    )

    first = process_actor_queue(
        queue=queue,
        lock=lock,
    )

    second = process_actor_queue(
        queue=queue,
        lock=lock,
    )

    assert first["completed"] == 1
    assert second["claimed"] == 0
