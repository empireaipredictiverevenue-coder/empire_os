"""Deterministic, bounded work proposals for existing EmpireOS department owners.

This is an evidence-preserving planner, not a new task queue or a way to
authorize commercial actions. It consumes the existing unified review.
The existing DepartmentWorkQueue is the only supported downstream worker
transport, and this module intentionally NEVER enqueues anything.
"""
from __future__ import annotations
from hashlib import sha256
import json
import re
from typing import Any, Mapping

SCHEMA = "empire.revenue_evidence_workplan.v1"
MAX_FACTORY_WORK = 3
MAX_WORK = 12
RESTORE = {
    "buyer_scout": ("BuyerScout", "REFRESH_ORIGINAL_BUYER_SCOUT"),
    "jev": ("JEV", "REFRESH_ORIGINAL_CLIENT_PAIN_RESEARCH"),
    "opportunity_factory": ("OpportunityFactory", "RECHECK_FACTORY_ORIGINAL_SOURCE"),
    "buyer_relationships": ("BuyerReplyOperations", "RECHECK_ORIGINAL_GMAIL_EVIDENCE"),
    "buyer_capacity": ("BuyerAcquisition", "RECHECK_ORIGINAL_CAPACITY_READER"),
    "predictive_revenue": ("PredictiveCloud", "RECHECK_PREDICTIVE_CONTEXT_READER"),
    "orders_payments": ("RevenueLedger", "RECHECK_ORDER_PAYMENT_EVIDENCE"),
    "revenue_pulse": ("RevenuePulse", "RECHECK_RECOGNISED_REVENUE_READ_MODEL"),
    "economic_memory": ("EconomicMemory", "RECHECK_CAUSAL_OUTCOME_MEMORY"),
}

def _work(owner: str, action: str, source_ref: str, *,
          priority: int, state: str, proof: str) -> dict[str, Any]:
    if (not owner or not action or not source_ref or len(source_ref) > 240
            or not isinstance(priority, int) or not 0 <= priority <= 100):
        raise ValueError("INVALID_EVIDENCE_WORK_IDENTITY")
    # Deliberately stable across timer runs. Never depend on timestamp,
    # rankings, candidate counts, or message text.
    token = json.dumps((owner, action, source_ref), separators=(",", ":"))
    key = "evidence_work:" + sha256(token.encode("utf-8")).hexdigest()[:24]
    return {
        "work_key": key, "original_owner": owner,
        "action": action, "evidence_ref": source_ref,
        "required_proof": proof, "priority": priority,
        "state": state, "review_only": True,
        "enqueue_authorized": False,
        "external_execution_authorized": False,
        "outbound_authorized": False,
        "commercial_terms_authorized": False,
        "tenant_mutation_authorized": False,
        "money_movement_authorized": False,
    }

def build_workplan(cohesion: Mapping[str, Any], handoffs: Mapping[str, Any],
                   brain: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if (not isinstance(cohesion, Mapping)
            or cohesion.get("schema_version") != "empire.cross_system_cohesion.v1"
            or cohesion.get("mode") != "OBSERVE"
            or cohesion.get("execution_authority") != "NONE"
            or cohesion.get("db_writes") is not False
            or cohesion.get("outbound_authorized") is not False
            or cohesion.get("payments_executed") is not False):
        raise ValueError("UNTRUSTED_COHESION_INPUT")
    if (not isinstance(handoffs, Mapping)
            or handoffs.get("schema_version") != "empire.opportunity.canonical_handoff_review.v1"
            or handoffs.get("execution_authority") != "NONE"
            or handoffs.get("database_writes") is not False
            or handoffs.get("outbound_authorized") is not False
            or type(handoffs.get("handoff_ready_count")) is not int
            or handoffs["handoff_ready_count"] != 0):
        raise ValueError("UNTRUSTED_OPPORTUNITY_HANDOFF_INPUT")
    statuses = cohesion.get("sources")
    if not isinstance(statuses, Mapping) or set(statuses) != set(RESTORE):
        raise ValueError("INVALID_SOURCE_INVENTORY")
    tasks = []
    for key, pair in RESTORE.items():
        value = statuses[key]
        if not isinstance(value, Mapping):
            raise ValueError("INVALID_SOURCE_STATUS")
        status = value.get("status")
        if status != "CURRENT_OBSERVATION":
            tasks.append(_work(*pair, "snapshot:"+key, priority=95,
                               state="EVIDENCE_SOURCE_HOLD",
                               proof="Current bounded original artifact with exact schema and OBSERVE authority"))
    # A buyer can be independently researched before Factory readiness.
    counts = cohesion.get("evidence_population_counts") or {}
    if not isinstance(counts, Mapping):
        raise ValueError("INVALID_POPULATION_COUNTS")
    if (statuses["buyer_capacity"].get("status") == "CURRENT_OBSERVATION"
            and counts.get("fully_activated_buyers") == 0):
        tasks.append(_work("BuyerAcquisition",
                           "VERIFY_ONE_CONTRACTED_DOWNSTREAM_PAYER_BUYBOX",
                           "snapshot:buyer_capacity",
                           priority=100, state="COMMERCIAL_PROOF_REQUIRED",
                           proof="Exact named buyer, signed terms, territory, capacity, acceptance and payable price"))
    # Factory and cohesion must have read the EXACT same immutable bytes.
    # This is generation consistency, NOT cryptographic origin authority.
    factory_hash = statuses["opportunity_factory"].get("sha256")
    same_factory_generation = (
        isinstance(factory_hash, str) and len(factory_hash) == 64
        and handoffs.get("factory_source_sha256") == factory_hash
    )
    # Research rows are NOT canonical entities: preserve per-row review IDs.
    if statuses["opportunity_factory"].get("status") == "CURRENT_OBSERVATION":
        if not same_factory_generation:
            tasks.append(_work("OpportunityFactory", "RECHECK_COHERENT_FACTORY_GENERATION",
                               "snapshot:opportunity_factory", priority=98,
                               state="CONCURRENT_REFRESH_HOLD",
                               proof="One consistent Factory source digest across cohesion and exact-record review"))
        elif handoffs.get("source_reviewed") is not True:
            tasks.append(_work("OpportunityFactory", "RESTORE_EXACT_FACTORY_REVIEW",
                               "snapshot:opportunity_factory", priority=94,
                               state="SOURCE_REVIEW_HOLD",
                               proof="Validated per-row original research keys and source provenance"))
        else:
            rows = handoffs.get("items")
            if not isinstance(rows, list) or len(rows) > 200:
                raise ValueError("UNBOUNDED_OPPORTUNITY_REVIEW")
            for row in rows[:MAX_FACTORY_WORK]:
                if (not isinstance(row, Mapping)
                        or row.get("handoff_ready") is not False
                        or row.get("commercial_authority") is not False
                        or row.get("next_action") not in (
                            "COMPLETE_REAL_FACTORY_VALIDATION",
                            "VERIFY_EXISTING_EMPIREDB_GTM_ENTITY_TENANT_LINK")
                        or not isinstance(row.get("review_id"), str)
                        or not row["review_id"].startswith("research_review:")):
                    raise ValueError("UNSAFE_CANDIDATE_WORK_PROPOSAL")
                action = row["next_action"]
                owner = ("OpportunityFactory" if action == "COMPLETE_REAL_FACTORY_VALIDATION"
                         else "CanonicalIdentity / SmartCRM")
                tasks.append(_work(owner, action, row["review_id"],
                                   priority=86 if owner == "OpportunityFactory" else 90,
                                   state="RESEARCH_ONLY",
                                   proof=("Specific source-row receipt, real Factory validation and immutable link"
                                          if owner == "OpportunityFactory" else
                                          "Privileged EmpireDB GTM UUID, legal entity and authenticated tenant scope")))
    # Actual existing inbound buyer exchanges outrank generic research.
    # Keep them on the original reply-review lane, never a new mail send.
    replies = cohesion.get("existing_inbound_buyer_reply_reviews", [])
    if not isinstance(replies, list) or len(replies) > 3:
        raise ValueError("UNBOUNDED_EXISTING_BUYER_REPLIES")
    if statuses["buyer_relationships"].get("status") == "CURRENT_OBSERVATION":
        for row in replies:
            if (not isinstance(row, Mapping)
                    or row.get("existing_owner") != "BuyerReplyOperations"
                    or row.get("source_action") != "REVIEW_EXISTING_ROUTING_RECORDING_REPLY_NO_REPEAT"
                    or row.get("new_outbound_authorized") is not False
                    or row.get("buyer_contract_verified") is not False
                    or row.get("execution_authority") != "NONE"
                    or not isinstance(row.get("review_ref"), str)
                    or re.fullmatch(r"founder_review:[a-z0-9_-]{1,100}", row["review_ref"]) is None):
                raise ValueError("UNTRUSTED_EXISTING_BUYER_REPLY")
            tasks.append(_work("BuyerReplyOperations", row["source_action"],
                               row["review_ref"], priority=98,
                               state="REAL_REPLY_REVIEW_HOLD",
                               proof="Review original routing, recording, retention, approved capacity and exact buyer acceptance before any further mail or traffic"))
    if cohesion.get("crm_tenant_link_verified_in_this_reader") is not True:
        tasks.append(_work("SmartCRM", "ATTEST_CANONICAL_TENANT_BUSINESS_BINDING",
                           "snapshot:buyer_relationships", priority=89,
                           state="PRIVILEGED_READER_REQUIRED",
                           proof=("Execute only via the existing signed CRM read-only login: "
                                  "canonical_prospect_tenant_handoff.review_signed_crm_prospect_tenant; "
                                  "validate original prospect_entity_links, no identity conflicts, "
                                  "unique active tenant_business_entity_bindings; "
                                  "GTM opportunity binding and buyer terms separately held")))
    # Publisher suggestions only if actual recognised Gmail evidence is present.
    if brain is not None:
        if (not isinstance(brain, Mapping)
                or brain.get("schema_version") != "empire.buyer_evidence_brain.v1"
                or brain.get("execution_authority") != "NONE"
                or brain.get("new_emails_sent") is not False
                or brain.get("database_writes") is not False):
            raise ValueError("UNTRUSTED_BUYER_BRAIN")
        rows = brain.get("commercial_proof_tasks")
        if (not isinstance(rows, list) or len(rows) > 24
                or type(brain.get("commercial_proof_task_count")) is not int
                or len(rows) != brain["commercial_proof_task_count"]):
            raise ValueError("UNTRUSTED_COMMERCIAL_PROOF_TASKS")
        for row in rows:
            if (not isinstance(row, Mapping)
                    or row.get("task") != "VERIFY_ONE_CONTRACTED_INSTALLER_BUYBOX_AND_PRICE"
                    or row.get("outbound_authorized") is not False
                    or row.get("execution_authority") != "NONE"
                    or not isinstance(row.get("gmail_source_ref"), str)
                    or not row["gmail_source_ref"].startswith("gmail:")
                    or re.fullmatch(r"gmail:[0-9a-f]{16,32}", row["gmail_source_ref"]) is None):
                raise ValueError("UNTRUSTED_PUBLISHER_WORK")
            tasks.append(_work("BuyerAcquisition", row["task"],
                               row["gmail_source_ref"], priority=99,
                               state="BUYER_PROOF_REQUIRED",
                               proof="Exact downstream installer signed buy box, terms, coverage, privacy and price"))
    unique = {item["work_key"]: item for item in tasks}
    if len(unique) != len(tasks):
        raise ValueError("DUPLICATE_EVIDENCE_WORK")
    ordered = sorted(unique.values(), key=lambda x:(-x["priority"], x["original_owner"], x["work_key"]))
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "work_count": min(MAX_WORK, len(ordered)),
        "work_proposals": ordered[:MAX_WORK],
        "truncated": len(ordered) > MAX_WORK,
        "factory_snapshot_generation_consistent": same_factory_generation,
        "original_queue": "empire_os.department_work_queue.DepartmentWorkQueue",
        "queue_mutated": False, "work_dispatched": 0,
        "execution_authority": "NONE",
        "external_outbound_authorized": False,
        "payments_executed": False, "database_writes": False,
    }
