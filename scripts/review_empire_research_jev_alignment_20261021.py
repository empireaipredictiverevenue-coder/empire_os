"""Record fixed-ledger Jev-compatible local Laya Research shadow evaluation.

No paid Jev endpoint, source text to model, source admission, email, DB or
execution. This creates one immutable evidence receipt for owner review.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from empire_os.research.jev_source_triage import triage_original_sources

LEDGER = "RESEARCH_SOLAR_HVAC_LEGAL_PROPERTY_UK_US_OFFICIAL_SOURCES_20261021.json"
RECEIPT = "RESEARCH_JEV_LOCAL_SHADOW_TRIAGE_20261021.json"


def run_review(source: dict, *, provider=None, calls: int = 0) -> dict:
    baseline = []
    for _ in range(30):
        begin = perf_counter()
        baseline_result = triage_original_sources(source)
        baseline.append((perf_counter() - begin) * 1000)
    candidate = triage_original_sources(
        source, provider=provider, max_shadow_calls=calls,
    )
    if candidate["deterministic_review_lane_counts"] != baseline_result["deterministic_review_lane_counts"]:
        raise ValueError("deterministic review drift")
    model_rows = [
        row for row in candidate["review_items"]
        if row["model_advisory_status"] != "NOT_CALLED"
    ]
    return {
        "schema_version": "empire.research.jev_shadow_triage_receipt.v1",
        "status": "RESEARCH_LOCAL_SHADOW_COMPARISON_REVIEW_ONLY",
        "input_sha256": sha256(json.dumps(source, sort_keys=True).encode()).hexdigest(),
        "original_source_count": candidate["original_sources_reviewed"],
        "deterministic_review_lane_counts": candidate["deterministic_review_lane_counts"],
        "deterministic_median_elapsed_ms_30_samples": round(median(baseline), 4),
        "local_shadow_attempts": candidate["shadow_model_calls_attempted"],
        "observed_model_latency_ms": [
            row.get("provider_observed_latency_ms")
            for row in model_rows
            if row.get("provider_observed_latency_ms") is not None
        ],
        "model_review_status_counts": {
            status: sum(row["model_advisory_status"] == status for row in model_rows)
            for status in sorted({row["model_advisory_status"] for row in model_rows})
        },
        "model_disagreements_with_deterministic": sum(
            row.get("model_disagrees_with_deterministic_gate") is True
            for row in model_rows
        ),
        "shadow_model_has_no_commercial_authority": True,
        "trusted_source_admissions": candidate["trusted_research_sources_admitted"],
        "external_paid_jev_api_called": False,
        "human_editorial_signoff_present": False,
        "messages_sent": 0,
        "db_writes": False,
        "execution_authority": "none",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--local-shadow", action="store_true")
    parser.add_argument("--max-shadow-calls", type=int, default=0)
    args = parser.parse_args()
    if args.local_shadow != (args.max_shadow_calls > 0):
        raise ValueError("local-shadow flag and explicit call budget must agree")
    root = Path(__file__).resolve().parents[1]
    original = root / "docs/commercial" / LEDGER
    output = root / "docs/commercial" / RECEIPT
    if (original.is_symlink() or not original.is_file()
        or not 0 < original.stat().st_size <= 500000
        or output.exists() or output.is_symlink()):
        raise ValueError("unsafe or existing Research source/receipt file")
    source = json.loads(original.read_text())
    provider = None
    if args.local_shadow:
        from empire_os.laya_http_provider import LayaHttpTypedDecisionProvider
        provider = LayaHttpTypedDecisionProvider(
            base_url="http://127.0.0.1:8769", timeout_s=3,
        )
    receipt = run_review(source, provider=provider, calls=args.max_shadow_calls)
    with output.open("x", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({
        "status": receipt["status"],
        "sources": receipt["original_source_count"],
        "local_shadow_attempts": receipt["local_shadow_attempts"],
        "source_admissions": receipt["trusted_source_admissions"],
        "model_disagreements": receipt["model_disagreements_with_deterministic"],
        "execution_authority": receipt["execution_authority"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
