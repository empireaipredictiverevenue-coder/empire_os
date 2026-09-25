#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time

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
    parser.add_argument("--model", default="convaiinnovations/laya")
    parser.add_argument("--subfolder", default=None)
    args = parser.parse_args()

    provider = load_laya_provider(
        model_key=args.model,
        subfolder=args.subfolder,
    )
    rows = read_cases(Path(args.cases))
    passed = 0
    latencies = []

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
        review = review_typed_decision_result(
            request=request,
            result=result,
            confidence_threshold=args.threshold,
        )
        ok = result.label == case["expected_label"]
        passed += int(ok)
        print(json.dumps({
            "case_id": case["case_id"],
            "expected_label": case["expected_label"],
            "actual_label": result.label,
            "confidence": result.confidence,
            "requires_escalation": review["requires_escalation"],
            "elapsed_ms": round(elapsed_ms, 2),
            "pass": ok,
            "shadow_only": result.shadow_only,
        }, sort_keys=True))

    total = len(rows)
    summary = {
        "schema_version": "empire.laya-shadow-benchmark.v1",
        "cases": total,
        "passed": passed,
        "accuracy": round(passed / total, 4) if total else 0.0,
        "latency_ms_p50": (
            round(statistics.median(latencies), 2) if latencies else None
        ),
        "shadow_only": True,
        "execution_authority": "none",
    }
    print(json.dumps({"summary": summary}, sort_keys=True))
    return 0 if passed == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
