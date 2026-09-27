#!/usr/bin/env python3
"""Microbenchmark for Empire Decision Judge.

No network calls, no outreach, no billing, no revenue mutation.
Measures deterministic typed decision latency across representative voice cases.
"""
from __future__ import annotations

import json
import statistics
import time

from empire_os.decision_judge import EmpireDecisionJudge, TranscriptCandidate


CASES = (
    ("opt_out", ["Please do not call me again."]),
    (
        "no_now_flip",
        ["Empire Voice Lab test. Now external voice vendor is being used."],
    ),
    ("follow_up", ["Yes, send me the brief by email."]),
    ("payment", ["I accept the terms and I'll pay now."]),
    (
        "asr_price_disagreement",
        [
            TranscriptCandidate(
                source="zipformer",
                text="The pilot is 1500 pounds.",
            ),
            TranscriptCandidate(
                source="whisper",
                text="The pilot is 500 pounds.",
            ),
        ],
    ),
    ("unknown", ["Who are you and what is this about?"]),
)


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, round((len(ordered) - 1) * p))
    return ordered[index]


def main() -> int:
    judge = EmpireDecisionJudge()
    iterations = 5000
    timings_ms: list[float] = []
    actions: dict[str, int] = {}
    intents: dict[str, int] = {}

    started = time.perf_counter()
    for i in range(iterations):
        name, payload = CASES[i % len(CASES)]
        before = time.perf_counter()
        if payload and isinstance(payload[0], TranscriptCandidate):
            result = judge.judge_candidates(payload)
        else:
            result = judge.judge_text(
                str(payload[0]),
                source="benchmark",
            )
        elapsed_ms = (time.perf_counter() - before) * 1000
        timings_ms.append(elapsed_ms)
        actions[result.action] = actions.get(result.action, 0) + 1
        intents[result.intent] = intents.get(result.intent, 0) + 1

    total = time.perf_counter() - started
    result = {
        "schema_version": "empire.decision_judge_benchmark.v1",
        "ok": True,
        "iterations": iterations,
        "case_count": len(CASES),
        "total_seconds": round(total, 4),
        "throughput_per_second": round(iterations / total, 1),
        "latency_ms": {
            "mean": round(statistics.mean(timings_ms), 4),
            "median": round(statistics.median(timings_ms), 4),
            "p95": round(percentile(timings_ms, 0.95), 4),
            "p99": round(percentile(timings_ms, 0.99), 4),
            "max": round(max(timings_ms), 4),
        },
        "actions": actions,
        "intents": intents,
        "network_dependency": False,
        "execution_authority": False,
        "outbound_mutation": False,
        "live_call_placed": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
