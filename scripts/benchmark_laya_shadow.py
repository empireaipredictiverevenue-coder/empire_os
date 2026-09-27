#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time

from empire_os.laya_http_provider import LayaHttpTypedDecisionProvider
from empire_os.laya_reply_specialist import review_laya_reply_specialist
from empire_os.laya_typed_decision import load_laya_provider
from empire_os.typed_decision_provider import (
    TypedDecisionRequest,
    review_typed_decision_result,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "benchmarks/laya_reply_cases.jsonl"
LABELS = (
    "positive",
    "question",
    "objection",
    "later",
    "negative",
    "unsubscribe",
    "other",
)
CRITERIA = {
    "positive": "explicit interest or request to continue",
    "question": "asks for information without clear buying intent",
    "objection": "raises a concern or blocking condition",
    "later": "asks to revisit at a future time",
    "negative": "declines without asking to unsubscribe",
    "unsubscribe": "asks to stop future contact",
    "other": "none of the other labels fit",
}


def read_cases(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--threshold", type=float, default=0.80)
    parser.add_argument(
        "--provider",
        choices=("http", "python"),
        default="http",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8769")
    parser.add_argument("--model", default="convaiinnovations/laya")
    parser.add_argument("--subfolder", default=None)
    args = parser.parse_args()

    if args.provider == "http":
        provider = LayaHttpTypedDecisionProvider(
            base_url=args.base_url,
        )
    else:
        provider = load_laya_provider(
            model_key=args.model,
            subfolder=args.subfolder,
        )
    rows = read_cases(Path(args.cases))
    raw_passed = 0
    safe_passed = 0
    unsafe_accepts = 0
    accepted = 0
    escalated = 0
    specialist_accepted = 0
    specialist_correct = 0
    specialist_misses = 0
    latencies = []
    confidences = []

    for case in rows:
        request = TypedDecisionRequest(
            task_key="reply_classification",
            decision_schema_ref="schema:reply:v2",
            state_ref=case["case_id"],
            state=case["state"],
            allowed_labels=LABELS,
            risk_class="low",
            instructions="Classify the buyer reply by commercial intent.",
            label_criteria=CRITERIA,
        )
        started = time.perf_counter()
        result = provider.evaluate(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies.append(elapsed_ms)
        confidences.append(result.confidence)
        review = review_typed_decision_result(
            request=request,
            result=result,
            confidence_threshold=args.threshold,
        )
        raw_ok = result.label == case["expected_label"]
        raw_passed += int(raw_ok)
        requires_escalation = bool(review["requires_escalation"])
        escalated += int(requires_escalation)
        accepted_now = not requires_escalation
        accepted += int(accepted_now)
        safe_ok = raw_ok or requires_escalation
        safe_passed += int(safe_ok)
        if accepted_now and not raw_ok:
            unsafe_accepts += 1

        specialist = review_laya_reply_specialist(
            request=request,
            result=result,
        )
        specialist_accept = bool(
            specialist["accepted_for_shadow_analysis"]
        )
        specialist_accepted += int(specialist_accept)
        if specialist_accept and raw_ok:
            specialist_correct += 1
        if specialist_accept and not raw_ok:
            specialist_misses += 1

        print(json.dumps({
            "case_id": case["case_id"],
            "expected_label": case["expected_label"],
            "actual_label": result.label,
            "confidence": result.confidence,
            "requires_escalation": requires_escalation,
            "accepted_without_escalation": accepted_now,
            "elapsed_ms": round(elapsed_ms, 2),
            "raw_pass": raw_ok,
            "safe_pass": safe_ok,
            "shadow_only": result.shadow_only,
            "specialist_accept": specialist_accept,
            "specialist_reason": specialist["reason"],
        }, sort_keys=True))

    total = len(rows)
    summary = {
        "schema_version": "empire.laya-shadow-benchmark.v1",
        "cases": total,
        "raw_passed": raw_passed,
        "raw_accuracy": round(raw_passed / total, 4) if total else 0.0,
        "safe_passed": safe_passed,
        "safe_accuracy": round(safe_passed / total, 4) if total else 0.0,
        "accepted": accepted,
        "escalated": escalated,
        "escalation_rate": round(escalated / total, 4) if total else 0.0,
        "unsafe_accepts": unsafe_accepts,
        "specialist_accepted": specialist_accepted,
        "specialist_correct": specialist_correct,
        "specialist_precision": (
            round(specialist_correct / specialist_accepted, 4)
            if specialist_accepted else None
        ),
        "specialist_misses": specialist_misses,
        "confidence_mean": (
            round(statistics.mean(confidences), 4)
            if confidences else None
        ),
        "confidence_min": (
            round(min(confidences), 4)
            if confidences else None
        ),
        "confidence_max": (
            round(max(confidences), 4)
            if confidences else None
        ),
        "latency_ms_p50": (
            round(statistics.median(latencies), 2) if latencies else None
        ),
        "shadow_only": True,
        "execution_authority": "none",
    }
    print(json.dumps({"summary": summary}, sort_keys=True))
    return 0 if (
        unsafe_accepts == 0
        and specialist_misses == 0
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
