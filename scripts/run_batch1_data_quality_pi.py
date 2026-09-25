#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.execution_plane_dispatcher import (
    ExecutionRequest,
    dispatch_execution_request,
)


def main() -> int:
    request = ExecutionRequest(
        request_id="batch1-data-quality-source-reliability-001",
        capability="backend_code",
        department="market_opportunity",
        objective=(
            "Implement the Data Quality & Source Reliability Agent strictly from "
            "docs/BUSINESS_AGENT_ARCHITECTURE_BATCH_1.md. Reuse source_health_observer, "
            "source_intelligence, acquisition_source_policy, candidate_quality, "
            "crawler_runner, source_qualification_bridge, source_buyer_review_bridge "
            "and existing Search Intelligence health/quality modules. Build observed "
            "source reliability features for run success/failure, latency, candidate "
            "yield, duplicate/freshness/field coverage, identity-resolution, "
            "qualification and downstream commercial usefulness only when evidence "
            "exists. Do not fabricate source economics, delete canonical evidence, "
            "turn model scores into truth, or retire sources irreversibly. Add a "
            "bounded recommendation layer for scheduler weighting/recovery and a "
            "read-only Founder surface where cleanly supported. Add focused tests. "
            "No external sends, production deployment, payment action, or revenue "
            "recognition."
        ),
        authority="internal_write",
        risk_class="medium",
        source_ref="docs/BUSINESS_AGENT_ARCHITECTURE_BATCH_1.md",
        allowed_paths=(
            "empire_os/source_health_observer.py",
            "empire_os/source_intelligence.py",
            "empire_os/acquisition_source_policy.py",
            "empire_os/candidate_quality.py",
            "empire_os/crawler_runner.py",
            "empire_os/source_qualification_bridge.py",
            "empire_os/source_buyer_review_bridge.py",
            "empire_os/founder_source_intelligence_api.py",
            "tests/",
        ),
        lease_resources=(
            "domain:source_reliability",
            "path:empire_os/source_health_observer.py",
            "path:empire_os/source_intelligence.py",
            "path:empire_os/acquisition_source_policy.py",
            "path:empire_os/candidate_quality.py",
        ),
        required_tests=(
            "tests/test_source_health_observer.py",
            "tests/test_source_intelligence.py",
            "tests/test_acquisition_source_policy.py",
            "tests/test_candidate_quality.py",
            "tests/test_crawler_runner.py",
            "tests/test_source_qualification_bridge.py",
            "tests/test_source_buyer_review_bridge.py",
            "tests/test_founder_source_intelligence_api.py",
        ),
        priority=90,
        max_runtime_seconds=1200,
        ai_behavior_change=False,
    )
    result = dispatch_execution_request(
        "/srv/empire_os",
        request,
        execute_pi=True,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") in {
        "CANDIDATE_VERIFIED",
        "PROPOSAL_READY",
        "COMPLETED_NO_CHANGES",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
