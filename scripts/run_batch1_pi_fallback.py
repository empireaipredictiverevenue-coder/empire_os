#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.execution_plane_dispatcher import (
    ExecutionRequest,
    dispatch_execution_request,
)


def run(request: ExecutionRequest) -> dict:
    result = dispatch_execution_request(
        "/srv/empire_os",
        request,
        execute_pi=True,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> int:
    requests = [
        ExecutionRequest(
            request_id="batch1-buyer-reply-conversation-ops-pi-001",
            capability="parallel_backend_code",
            department="revenue_sales",
            objective=(
                "Implement the Buyer Reply / Conversation Operations Agent "
                "strictly from docs/BUSINESS_AGENT_ARCHITECTURE_BATCH_1.md. "
                "Reuse the existing Gmail reply, conversation, closer, reply "
                "classifier, Laya specialist and outbound-governor components. "
                "Do not create duplicate conversation or commercial truth stores. "
                "Preserve provenance, opt-out/DNC, unknown-is-unknown, and all "
                "existing send/payment/revenue authority gates. Add focused tests."
            ),
            authority="internal_write",
            risk_class="medium",
            source_ref="docs/BUSINESS_AGENT_ARCHITECTURE_BATCH_1.md",
            allowed_paths=(
                "empire_os/gmail_reply_adapter.py",
                "empire_os/gmail_reply_runtime.py",
                "empire_os/conversation_ingest.py",
                "empire_os/conversation_os.py",
                "empire_os/conversation_qualification.py",
                "empire_os/conversation_timeline.py",
                "empire_os/conversation_value.py",
                "empire_os/closer_reply_worker.py",
                "empire_os/closer_reply_draft.py",
                "empire_os/reply_classifier.py",
                "empire_os/laya_reply_specialist.py",
                "empire_os/founder_execution_plane_api.py",
                "tests/",
            ),
            lease_resources=(
                "domain:conversation_os",
            ),
            required_tests=(
                "tests/test_gmail_reply_adapter.py",
                "tests/test_gmail_reply_runtime.py",
                "tests/test_conversation_ingest.py",
                "tests/test_conversation_os.py",
                "tests/test_conversation_qualification.py",
                "tests/test_conversation_timeline.py",
                "tests/test_conversation_value.py",
                "tests/test_closer_reply_worker.py",
                "tests/test_closer_reply_draft.py",
                "tests/test_reply_classifier.py",
                "tests/test_laya_reply_specialist.py",
            ),
            max_runtime_seconds=1200,
            ai_behavior_change=True,
        ),
        ExecutionRequest(
            request_id="batch1-deliverability-sender-reputation-pi-001",
            capability="parallel_backend_code",
            department="revenue_sales",
            objective=(
                "Implement the Deliverability & Sender Reputation Agent strictly "
                "from docs/BUSINESS_AGENT_ARCHITECTURE_BATCH_1.md. Reuse existing "
                "outbound governor/provider/follow-up/outreach-quality evidence. "
                "Separate temporary deferral from permanent failure; preserve "
                "suppression and opt-out evidence; allow only reversible internal "
                "health/recommendation state. Do not send, mutate DNS, create paid "
                "commitments, expand authority or recognize revenue. Add tests."
            ),
            authority="internal_write",
            risk_class="medium",
            source_ref="docs/BUSINESS_AGENT_ARCHITECTURE_BATCH_1.md",
            allowed_paths=(
                "empire_os/outbound_governor.py",
                "empire_os/outbound_governor_executor.py",
                "empire_os/outbound_provider.py",
                "empire_os/outbound_followup_worker.py",
                "empire_os/outreach_quality.py",
                "empire_os/founder_execution_plane_api.py",
                "tests/",
            ),
            lease_resources=(
                "domain:deliverability",
            ),
            required_tests=(
                "tests/test_outbound_governor.py",
                "tests/test_outbound_governor_executor.py",
                "tests/test_outbound_provider.py",
                "tests/test_outbound_followup_worker.py",
                "tests/test_outreach_quality.py",
            ),
            max_runtime_seconds=1200,
            ai_behavior_change=False,
        ),
        ExecutionRequest(
            request_id="batch1-data-quality-source-reliability-pi-002",
            capability="parallel_backend_code",
            department="market_opportunity",
            objective=(
                "Implement the Data Quality & Source Reliability Agent strictly "
                "from docs/BUSINESS_AGENT_ARCHITECTURE_BATCH_1.md. Reuse existing "
                "source health/intelligence/policy/quality/crawler bridges. Use "
                "observed evidence only, keep unknown economics unknown, and make "
                "only bounded reversible scheduling/recovery recommendations. "
                "Add focused tests and read-only Founder state where appropriate."
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
            max_runtime_seconds=1200,
            ai_behavior_change=False,
        ),
    ]

    statuses = []
    for request in requests:
        print(f"=== {request.request_id} ===")
        result = run(request)
        statuses.append((request.request_id, result.get("status")))

    print("=== BATCH SUMMARY ===")
    print(json.dumps(statuses, indent=2))
    good = {
        "CANDIDATE_VERIFIED",
        "PROPOSAL_READY",
        "COMPLETED_NO_CHANGES",
    }
    return 0 if all(status in good for _, status in statuses) else 2


if __name__ == "__main__":
    raise SystemExit(main())
