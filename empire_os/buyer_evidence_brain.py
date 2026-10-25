"""Evidence-bound next work for the original EmpireOS buyer-acquisition cycle.

No second agent, synthetic business inputs, Gmail write, CRM write or commercial
activation. Treat provider email as a report, never proof of a buying contract.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from empire_os.executive_buyer_capacity_review import review_buyer_capacity

SCHEMA = "empire.buyer_evidence_brain.v1"
MAX_PUBLISHERS = 24

def plan_evidence_work(
    publishers: list[dict[str, Any]],
    *,
    buyer_snapshot: Mapping[str, Any] | None,
    now: datetime,
) -> dict[str, Any]:
    if not isinstance(publishers, list) or len(publishers) > MAX_PUBLISHERS:
        raise ValueError("UNBOUNDED_PUBLISHER_EVIDENCE")
    review = review_buyer_capacity(buyer_snapshot, as_of=now)
    tasks: list[dict[str, Any]] = []
    for row in publishers:
        if (not isinstance(row, dict) or row.get("outbound_authorized") is not False
                or row.get("buyer_demand_verified") is not False):
            raise ValueError("UNTRUSTED_PUBLISHER_EVIDENCE")
        assessment = row.get("publisher_next_evidence") or {}
        if (not isinstance(assessment, dict)
                or assessment.get("execution_authority") != "NONE"
                or assessment.get("quote_authorized") is not False
                or assessment.get("buyer_capacity_verified") is not False):
            raise ValueError("UNSAFE_PUBLISHER_DECISION")
        if row.get("next_action") != "VERIFY_ONE_CONTRACTED_INSTALLER_BUYBOX_AND_PRICE":
            continue
        if len(tasks) >= MAX_PUBLISHERS:
            raise ValueError("TOO_MANY_BUYER_EVIDENCE_TASKS")
        tasks.append({
            "domain": row["domain"],
            "publisher_role": "TRAFFIC_SUPPLY_HYPOTHESIS_NOT_VERIFIED",
            "gmail_source_ref": assessment.get("reported_evidence_ref"),
            "latest_reply_id": row["last_reply_id"],
            "priority": "FIRST_CONTRACTED_DOWNSTREAM_BUYER",
            "task": "VERIFY_ONE_CONTRACTED_INSTALLER_BUYBOX_AND_PRICE",
            "proofs_required": list(assessment.get("required_evidence", [])),
            "buyer_capacity_snapshot_status": review["status"],
            "full_buyer_contract_verified": False,
            "outbound_authorized": False,
            "execution_authority": "NONE",
        })
    tasks.sort(key=lambda x: (x["domain"], x["latest_reply_id"]))
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "buyer_capacity_evidence": review,
        "publisher_reviewed_count": len(publishers),
        "commercial_proof_task_count": len(tasks),
        "commercial_proof_tasks": tasks,
        "any_contract_approved": False,
        "lead_delivery_authorized": False,
        "new_emails_sent": False,
        "database_writes": False,
        "money_moved": False,
        "recognized_revenue": None,
        "execution_authority": "NONE",
    }
