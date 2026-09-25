#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time

from empire_os.needle_shadow_router import (
    NeedleRouteRequest,
    NeedleToolSchema,
    load_needle_shadow_router,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "benchmarks/needle_shadow_cases.jsonl"


def schemas():
    return (
        NeedleToolSchema(
            name="classify_reply",
            description=(
                "Choose this when the input is an observed buyer email/reply "
                "that needs commercial reply classification."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "message_ref": {"type": "string"},
                },
                "required": ["message_ref"],
            },
        ),
        NeedleToolSchema(
            name="build_copy_brief",
            description=(
                "Choose this when the user requests a drafting-only outreach "
                "brief for a known account using observed evidence."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "account_ref": {"type": "string"},
                },
                "required": ["account_ref"],
            },
        ),
    )


def read_cases(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--threshold", type=float, default=0.75)
    args = parser.parse_args()

    tools = schemas()
    router = load_needle_shadow_router(
        tools=tools,
        system_facts=(
            "assistant: EmpireOS shadow router; "
            "network: local; user: Empire operator"
        ),
        tool_index_path=str(ROOT / "runtime/needle/tools.idx"),
    )
    rows = read_cases(Path(args.cases))
    latencies = []
    raw_passed = 0
    safe_passed = 0
    unsafe_accepts = 0

    for case in rows:
        request = NeedleRouteRequest(
            query=case["query"],
            state_ref=case["case_id"],
            tools=tools,
            confidence_threshold=args.threshold,
        )
        started = time.perf_counter()
        result = router.route(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies.append(elapsed_ms)

        expected = case.get("expected_tool")
        raw_ok = result.tool_name == expected
        raw_passed += int(raw_ok)

        accepted = not result.requires_escalation
        safe_ok = raw_ok or result.requires_escalation
        safe_passed += int(safe_ok)
        if accepted and not raw_ok:
            unsafe_accepts += 1

        print(json.dumps({
            "case_id": case["case_id"],
            "expected_tool": expected,
            "actual_tool": result.tool_name,
            "confidence": result.confidence,
            "requires_escalation": result.requires_escalation,
            "elapsed_ms": round(elapsed_ms, 2),
            "raw_pass": raw_ok,
            "safe_pass": safe_ok,
            "accepted_without_escalation": accepted,
            "tool_executed": result.tool_executed,
        }, sort_keys=True))

    total = len(rows)
    summary = {
        "schema_version": "empire.needle-shadow-benchmark.v1",
        "cases": total,
        "raw_passed": raw_passed,
        "raw_accuracy": round(raw_passed / total, 4) if total else 0.0,
        "safe_passed": safe_passed,
        "safe_accuracy": round(safe_passed / total, 4) if total else 0.0,
        "unsafe_accepts": unsafe_accepts,
        "latency_ms_p50": (
            round(statistics.median(latencies), 2) if latencies else None
        ),
        "shadow_only": True,
        "execution_authority": "none",
        "tool_executed": False,
    }
    print(json.dumps({"summary": summary}, sort_keys=True))
    return 0 if unsafe_accepts == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
