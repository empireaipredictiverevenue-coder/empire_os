"""Controlled seed-only transport benchmark.

This compares transports using Empire-owned seed mailboxes. It is not permitted to probe
unconsenting recipients or bypass provider restrictions.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def compare_seed_transports(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    aggregates: dict[str, dict[str, float]] = {}

    for raw in rows:
        row = dict(raw)
        if row.get("recipient_class") != "empire_seed":
            raise ValueError("transport_benchmark_requires_empire_seed_recipient")
        if row.get("provider_policy_compatible") is not True:
            raise ValueError("transport_benchmark_requires_policy_compatible_transport")

        name = str(row.get("transport") or "").strip()
        if not name:
            raise ValueError("transport_name_required")

        bucket = aggregates.setdefault(
            name,
            {
                "tests": 0.0,
                "inbox": 0.0,
                "spam": 0.0,
                "missing": 0.0,
                "latency_ms": 0.0,
            },
        )
        bucket["tests"] += 1
        bucket["inbox"] += 1 if row.get("placement") == "inbox" else 0
        bucket["spam"] += 1 if row.get("placement") == "spam" else 0
        bucket["missing"] += 1 if row.get("placement") == "missing" else 0
        bucket["latency_ms"] += max(0.0, float(row.get("latency_ms") or 0))

    results = []
    for name, bucket in aggregates.items():
        tests = max(1.0, bucket["tests"])
        inbox_rate = bucket["inbox"] / tests
        spam_rate = bucket["spam"] / tests
        missing_rate = bucket["missing"] / tests
        avg_latency_ms = bucket["latency_ms"] / tests
        # Placement dominates; latency is only a small tie-breaker.
        score = inbox_rate - 0.75 * spam_rate - 1.0 * missing_rate - min(
            0.05, avg_latency_ms / 1_000_000
        )
        results.append(
            {
                "transport": name,
                "tests": int(tests),
                "inbox_rate": round(inbox_rate, 4),
                "spam_rate": round(spam_rate, 4),
                "missing_rate": round(missing_rate, 4),
                "avg_latency_ms": round(avg_latency_ms, 2),
                "score": round(score, 4),
            }
        )

    results.sort(key=lambda item: (-item["score"], item["transport"]))
    return {
        "results": results,
        "preferred_transport": results[0]["transport"] if results else None,
        "scope": "controlled_seed_measurement_only",
    }
