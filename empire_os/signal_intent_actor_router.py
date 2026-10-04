"""Route durable intent signals into the governed Revenue Actor queue."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from empire_os.revenue_actor_queue import (
    enqueue_actor_job,
)


def observation_from_signal(
    signal_id: str,
    signal: Mapping[str, Any],
) -> dict[str, Any] | None:
    source = str(
        signal.get("source") or ""
    ).strip()

    if not source.endswith("_intent"):
        return None

    if signal.get("status") not in {
        "unresolved",
        "needs_review",
    }:
        return None

    raw = signal.get("raw")
    if not isinstance(raw, Mapping):
        return None

    observation = raw.get("community_intent")
    if not isinstance(observation, Mapping):
        return None

    payload = dict(observation)

    payload["signal_id"] = str(
        signal.get("signal_id") or signal_id
    )
    payload["signal_source"] = source

    if not payload.get("niche"):
        payload["niche"] = signal.get("niche")

    if not payload.get("url"):
        payload["url"] = signal.get("url")

    if not payload.get("observed_at"):
        payload["observed_at"] = (
            signal.get("last_seen_at")
            or signal.get("created_at")
        )

    if not payload.get("evidence_urls"):
        evidence_urls = raw.get("evidence_urls")
        if isinstance(evidence_urls, (list, tuple)):
            payload["evidence_urls"] = list(
                evidence_urls
            )

    return payload


def route_signal_inbox(
    signals: Mapping[str, Any],
    *,
    queue: Path,
    lock: Path,
    limit: int = 25,
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise ValueError(
            "signal actor routing limit must be 1-100"
        )

    ordered = sorted(
        (
            (str(signal_id), signal)
            for signal_id, signal in signals.items()
            if isinstance(signal, Mapping)
        ),
        key=lambda item: str(
            item[1].get("last_seen_at")
            or item[1].get("created_at")
            or ""
        ),
        reverse=True,
    )

    considered = 0
    routed = 0
    deduplicated = 0
    skipped = 0

    job_ids: list[str] = []

    for signal_id, signal in ordered:
        if considered >= limit:
            break

        source = str(
            signal.get("source") or ""
        )

        if not source.endswith("_intent"):
            continue

        considered += 1

        payload = observation_from_signal(
            signal_id,
            signal,
        )

        if payload is None:
            skipped += 1
            continue

        result = enqueue_actor_job(
            "intent_brain",
            payload,
            source_ref=(
                f"signal_inbox:{signal_id}"
            ),
            queue=queue,
            lock=lock,
        )

        job_ids.append(result["job_id"])

        if result["created"]:
            routed += 1
        else:
            deduplicated += 1

    return {
        "schema_version":
            "empire.signal_intent_actor_route.v1",
        "mode": "OBSERVE",
        "considered": considered,
        "routed": routed,
        "deduplicated": deduplicated,
        "skipped": skipped,
        "job_ids": job_ids,
        "outbound_sent": False,
        "canonical_promotion_performed": False,
        "payment_mutation": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
