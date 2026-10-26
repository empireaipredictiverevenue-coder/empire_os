#!/usr/bin/env python3
"""One read-only command to review EmpireOS buyer, opportunity and revenue handoffs.

Uses the original supervisor and original Gmail relationship reconciler.
No schedule, DB connection, mail send, money, or runtime artifact write.
"""
from __future__ import annotations
import json
from pathlib import Path

from empire_os.revenue_completion_supervisor import build_snapshot
from empire_os.revenue_evidence_workplan import build_workplan
from scripts.reconcile_buyer_email_relationships import build as relationship_review


def report(supervisor: dict, relationships: dict) -> dict:
    cohesion = supervisor["cross_system_cohesion"]
    handoffs = supervisor["canonical_opportunity_handoffs"]
    brain = relationships["buyer_evidence_brain"]
    workplan = build_workplan(cohesion, handoffs, brain)
    if (supervisor.get("mode") != "OBSERVE"
            or supervisor.get("execution_authority") != "none"
            or cohesion.get("execution_authority") != "NONE"
            or handoffs.get("execution_authority") != "NONE"
            or brain.get("execution_authority") != "NONE"
            or relationships.get("outbound_authorized") is not False):
        raise ValueError("UNSAFE_UNIFIED_EVIDENCE_AUTHORITY")
    states = cohesion.get("sources") or {}
    current = sum(x.get("status") == "CURRENT_OBSERVATION"
                  for x in states.values() if isinstance(x, dict))
    stage_count = len(cohesion.get("lifecycle_handoff_gates") or [])
    records = handoffs.get("records_reviewed")
    approved = handoffs.get("handoff_ready_count")
    cap = brain.get("buyer_capacity_evidence") or {}
    if (stage_count != 12 or len(states) != 9
            or type(records) is not int or type(approved) is not int
            or handoffs.get("database_writes") is not False
            or handoffs.get("outbound_authorized") is not False
            or cohesion.get("emails_sent") is not False
            or cohesion.get("db_writes") is not False
            or cohesion.get("payments_executed") is not False
            or brain.get("database_writes") is not False
            or brain.get("new_emails_sent") is not False):
        raise ValueError("UNSAFE_OR_INCOMPLETE_UNIFIED_REVIEW")
    return {
        "schema_version": "empire.unified_revenue_loop_review.v1",
        "mode": "OBSERVE",
        "source_snapshots_current": current,
        "source_snapshots_expected": 9,
        "lifecycle_stage_count": stage_count,
        "factory_records_reviewed": records,
        "canonical_handoff_ready_count": approved,
        "buyer_capacity_status": cap.get("status"),
        "publisher_relationships_reviewed": brain.get("publisher_reviewed_count"),
        "publisher_commercial_proof_tasks": brain.get("commercial_proof_task_count"),
        "commercial_loop_verified": cohesion.get("fully_verified_commercial_loop") is True,
        "canonical_tenant_link_verified": cohesion.get("crm_tenant_link_verified_in_this_reader") is True,
        "recognized_revenue_cents": cohesion.get("evidence_population_counts", {}).get("recognized_revenue_cents"),
        "next_original_supervisor_action": supervisor.get("next_action"),
        "evidence_work_proposal_count": workplan["work_count"],
        "next_evidence_work": workplan["work_proposals"][:4],
        "original_department_queue_mutated": workplan["queue_mutated"],
        "next_factory_handoff_action": (
            handoffs["items"][0].get("next_action") if handoffs.get("items") else None
        ),
        "execution_authority": "NONE",
        "database_writes": False,
        "outbound_sent": False,
        "payments_executed": False,
    }


def main() -> int:
    original = build_snapshot()
    relations = relationship_review(Path("/srv/empire_os"))
    print(json.dumps(report(original, relations), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
