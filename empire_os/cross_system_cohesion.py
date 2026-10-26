"""Single evidence-only systems view for the ORIGINAL revenue supervisor.

No second scheduler, database, CRM, task dispatcher or business event writer.
Source counts are separate populations; never join company names or assume
scout signals represent converted customers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import stat
from typing import Any, Mapping

SCHEMA = "empire.cross_system_cohesion.v1"
# Only pre-existing EmpireOS snapshots. CRM is intentionally an explicit
# unverified handoff: a local JSON file cannot attest to tenant SQL/RLS.
SOURCES = {
    "buyer_scout": ("runtime/buyer_acquisition/scout_latest.json",
                    "empire.buyer_acquisition_scout.v1", 120),
    "jev": ("runtime/jev_client_pain_discovery/aggregate_latest.json",
             "empire.jev.client_pain_production_observe.v1", 1440),
    "opportunity_factory": ("runtime/opportunity_factory/intake_latest.json",
                             "empire.opportunity_factory_intake_batch.v1", 180),
    "buyer_relationships": ("runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json",
                             "empire.commercial_relationship_registry.v1", 180),
    "buyer_capacity": ("runtime/buyer_capacity_readiness/latest.json",
                        "empire.buyer_capacity_readiness.v1", 180),
    "predictive_revenue": ("runtime/predictive_revenue_control/predictive_revenue_runtime_latest.json",
                           "empire-predictive-revenue-contextual-runtime-v2", 180),
    "orders_payments": ("runtime/orders_payments_revenue_control/orders_payments_revenue_runtime_latest.json",
                         "empire-orders-payments-revenue-runtime-control-v1", 180),
    "revenue_pulse": ("runtime/revenue_pulse/latest.json",
                      "empire.revenue-pulse.v3", 120),
    "economic_memory": ("runtime/economic_memory/latest.json",
                         "empire.economic_memory.v1", 180),
}
TIME_FIELDS = ("generated_at", "observed_at", "generated_at_utc")
MAX_BYTES = 1_000_000

def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None

def _authority_safe(value: dict[str, Any]) -> bool:
    if str(value.get("execution_authority", "none")).lower() != "none":
        return False
    for name in ("outbound_authorized", "outbound_sent", "db_writes",
                 "database_writes", "payment_execution", "payment_mutation",
                 "automatic_external_execution_allowed",
                 "model_weight_mutation_authorized"):
        if value.get(name) is True:
            return False
    governance = value.get("governance")
    if isinstance(governance, dict) and any(
        governance.get(name) is True for name in
        ("action_authority_granted", "db_write", "funds_movement", "mainnet_action")
    ):
        return False
    return True

def _snapshot(root: Path, key: str, now: datetime) -> tuple[dict[str, Any], dict[str, Any] | None]:
    relative, schema, max_age = SOURCES[key]
    path = root / relative
    source = {"source": key, "path": relative, "status": "UNAVAILABLE",
              "fresh": False, "age_minutes": None, "schema_verified": False,
              "sha256": None}
    try:
        if path.is_symlink() or not path.is_file():
            return source, None
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_BYTES:
            source["status"] = "UNSAFE_SOURCE"
            return source, None
        raw = path.read_bytes()
        if len(raw) > MAX_BYTES:
            source["status"] = "UNSAFE_SOURCE"
            return source, None
        value = json.loads(raw.decode("utf-8"))
        source["sha256"] = sha256(raw).hexdigest()
        if not isinstance(value, dict):
            source["status"] = "INVALID_SOURCE"
            return source, None
    except (OSError, UnicodeError, ValueError):
        source["status"] = "UNAVAILABLE"
        return source, None
    if value.get("schema_version") != schema or value.get("mode") != "OBSERVE":
        source["status"] = "SCHEMA_OR_MODE_MISMATCH"
        return source, None
    if not _authority_safe(value):
        source["status"] = "UNSAFE_EXECUTION_AUTHORITY"
        return source, None
    # Snapshot metadata may be current while its underlying business evidence
    # is stale. Never treat that as verified commercial source data.
    source["schema_verified"] = True
    time = next((_timestamp(value.get(name)) for name in TIME_FIELDS
                 if _timestamp(value.get(name)) is not None), None)
    if time is None:
        source["status"] = "TIMESTAMP_UNVERIFIED"
        return source, None
    age = (now - time).total_seconds() / 60
    source["age_minutes"] = round(age, 1)
    if age < -5 or age > max_age:
        source["status"] = "STALE_OR_FUTURE"
        return source, None
    source["fresh"] = True
    source["status"] = "CURRENT_OBSERVATION"
    return source, value

def _count(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value <= 1_000_000 else None

def build_cohesion_snapshot(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc))
    if current.tzinfo is None:
        raise ValueError("NAIVE_COHESION_CLOCK")
    current = current.astimezone(timezone.utc)
    sources: dict[str, dict] = {}
    payloads: dict[str, dict | None] = {}
    for key in SOURCES:
        sources[key], payloads[key] = _snapshot(Path(root), key, current)
    scout = payloads["buyer_scout"] or {}
    jev = payloads["jev"] or {}
    factory = payloads["opportunity_factory"] or {}
    relationships = payloads["buyer_relationships"] or {}
    capacity = payloads["buyer_capacity"] or {}
    predictive = payloads["predictive_revenue"] or {}
    payment = payloads["orders_payments"] or {}
    pulse = payloads["revenue_pulse"] or {}
    memory = payloads["economic_memory"] or {}
    capacity_verified = _count(capacity.get("fully_activated"))
    ready = _count(factory.get("factory_ready_count"))
    settlement = payment.get("semantic_truth")
    payment_observed = (
        settlement.get("real_payment_observed") is True
        if isinstance(settlement, dict) else False
    )
    revenue_truth = pulse.get("recognized_revenue_truth")
    gross = (_count(revenue_truth.get("recognized_revenue_cents"))
             if isinstance(revenue_truth, dict) else None)
    memory_outcomes = (
        len(memory["outcome_conditioned_memories"])
        if isinstance(memory.get("outcome_conditioned_memories"), list)
        else None
    )
    counts = {
        "scout_research_candidates": _count(scout.get("candidate_count")),
        "jev_observations": _count(jev.get("observations_submitted")),
        "factory_research_candidates": _count(factory.get("candidate_count")),
        "factory_ready_opportunities": ready,
        "buyer_relationships_warm": _count(relationships.get("warm_business_relationship_count")),
        "buyer_records_seen": _count(capacity.get("buyers_seen")),
        "fully_activated_buyers": capacity_verified,
        "predictive_context_candidates": _count(predictive.get("candidate_count")),
        "predictive_context_passed": _count(predictive.get("passed_count")),
        "recognized_revenue_cents": gross,
        "outcome_conditioned_memories": memory_outcomes,
    }
    # Exact, previously observed buyer replies may require human review even
    # when NO downstream buyer is activated. A reply is never a contract.
    actionable_replies = []
    if sources["buyer_relationships"]["status"] == "CURRENT_OBSERVATION":
        raw_actions = relationships.get("founder_action_queue")
        if isinstance(raw_actions, list) and len(raw_actions) <= 500:
            seen_reply_entities = set()
            for row in raw_actions:
                if not isinstance(row, Mapping):
                    continue
                key = row.get("entity_key")
                incoming = _timestamp(row.get("last_inbound_at"))
                outgoing = _timestamp(row.get("last_outbound_at"))
                if (not isinstance(key, str) or not 1 <= len(key) <= 100
                        or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in key)
                        or key in seen_reply_entities
                        or row.get("outbound_authorized") is not False
                        or row.get("stage") != "INBOUND_REVIEW_REQUIRED"
                        or row.get("next_founder_action") not in (
                            "REVIEW_EXISTING_ROUTING_RECORDING_REPLY_NO_REPEAT",)
                        or incoming is None or outgoing is None
                        or not outgoing <= incoming <= current
                        or (current-incoming).total_seconds() > 14 * 86400):
                    continue
                seen_reply_entities.add(key)
                actionable_replies.append({
                    "review_ref": "founder_review:" + key,
                    "existing_owner": "BuyerReplyOperations",
                    "source_action": row["next_founder_action"],
                    "buyer_reply_observed_at": incoming.isoformat(),
                    "source_snapshot": "buyer_relationships",
                    "buyer_contract_verified": False,
                    "buyer_route_verified": False,
                    "new_outbound_authorized": False,
                    "execution_authority": "NONE",
                })
                if len(actionable_replies) >= 3:
                    break
    actions = []
    if sources["buyer_scout"]["status"] != "CURRENT_OBSERVATION":
        actions.append(("BuyerScout", "RESTORE_EXISTING_SCOUT_EVIDENCE"))
    if sources["jev"]["status"] != "CURRENT_OBSERVATION":
        actions.append(("JEV", "REFRESH_ORIGINAL_FIRST_PARTY_SIGNAL_OBSERVATION"))
    if ready == 0:
        actions.append(("OpportunityFactory", "VALIDATE_SOURCE_RIGHTS_AND_ONE_GENUINE_OPPORTUNITY"))
    if capacity_verified is None or capacity_verified == 0:
        actions.append(("BuyerAcquisition", "VERIFY_ONE_BUYER_CONTRACT_BUYBOX_TERMS_CAPACITY"))
    if sources["buyer_relationships"]["status"] != "CURRENT_OBSERVATION":
        actions.append(("BuyerReplyOperations", "RECONCILE_ORIGINAL_GMAIL_OBSERVATIONS"))
    # An offline JSON summary cannot certify EmpireDB CRM memberships or
    # tenant isolation. The original live CRM reader must verify these.
    actions.append(("SmartCRM", "ATTEST_ONE_CANONICAL_TENANT_LINK_FROM_PRIVILEGED_READER"))
    if not payment_observed:
        actions.append(("RevenueLedger", "AWAIT_REAL_ORDER_SETTLEMENT_NO_FINANCIAL_ACTION"))
    if not memory_outcomes:
        actions.append(("EconomicMemory", "AWAIT_VERIFIED_CAUSAL_COMMERCIAL_OUTCOME"))
    # Lifecycle handoffs require the SAME canonical scoped entity and order
    # across stages. None of these aggregate snapshots can provide that join.
    chain = [
        ("DATA", "BuyerScout / JEV", "SCOUT_AND_JEV_OBSERVED_ONLY"
         if (counts["scout_research_candidates"] or counts["jev_observations"])
         else "NO_CURRENT_SOURCE_EVIDENCE"),
        ("SOURCE_RIGHTS", "SourceAuthorization", "NOT_ATTESTED_FOR_SPECIFIC_RECORD"),
        ("OPPORTUNITY", "OpportunityFactory", "NO_FACTORY_READY_OPPORTUNITY"
         if ready == 0 else "FACTORY_COUNT_NOT_CANONICAL_RECORD_LINK"),
        ("PERSON_COMPANY", "IdentityResolution / JEV", "NO_CANONICAL_ENTITY_JOIN"),
        ("TENANT_CRM", "SmartCRM", "NO_CANONICAL_TENANT_MEMBERSHIP_ATTESTATION"),
        ("BUYER_ACCEPTANCE", "BuyerAcquisition", "NO_VERIFIED_BUYER_CAPACITY"
         if not capacity_verified else "CAPACITY_COUNT_UNLINKED_TO_OPPORTUNITY"),
        ("APPROVED_OUTBOUND", "BuyerReplyOperations", "REQUIRES_EXACT_INTENT_AND_SUPPRESSION"),
        ("ACCEPTED_ORDER", "RevenueLedger", "NO_LINKED_ACCEPTED_ORDER"),
        ("SETTLEMENT", "Payments", "NO_PAYMENT_OBSERVED"
         if not payment_observed else "PAYMENT_UNATTRIBUTED_TO_CANONICAL_ORDER"),
        ("FULFILMENT", "Fulfilment", "NO_LINKED_DELIVERY_RECEIPT"),
        ("REALISED_REVENUE", "RevenueAccounting", "NO_RECOGNISED_REVENUE"
         if not gross else "REVENUE_AGGREGATE_NOT_ENTITY_ATTRIBUTED"),
        ("ECONOMIC_MEMORY", "Cortex / EconomicMemory", "NO_OUTCOME_MEMORY"
         if not memory_outcomes else "MEMORY_NOT_LINKED_TO_CUSTOMER_SETTLEMENT"),
    ]
    stages = [
        {"stage": stage, "existing_owner": owner, "source_status": state,
         "canonical_record_handoff_verified": False,
         "automatic_execution_authorized": False}
        for stage, owner, state in chain
    ]
    brain = relationships.get("buyer_evidence_brain")
    brain_status = (
        "SOURCE_LINKED_REVIEW_ONLY"
        if isinstance(brain, dict)
        and brain.get("schema_version") == "empire.buyer_evidence_brain.v1"
        and brain.get("mode") == "OBSERVE"
        and brain.get("execution_authority") == "NONE"
        else "NOT_PRESENT_IN_CURRENT_RECONCILED_SOURCE"
    )
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "generated_at": current.isoformat(), "sources": sources,
        "population_counts_are_independent_not_a_conversion_funnel": True,
        "evidence_population_counts": counts,
        "existing_inbound_buyer_reply_reviews": actionable_replies,
        "lifecycle_handoff_gates": stages,
        "buyer_evidence_brain_in_registry": brain_status,
        "canonical_entity_id_join_verified": False,
        "crm_tenant_link_verified_in_this_reader": False,
        "payment_observed_not_equivalent_to_attributed_revenue": payment_observed,
        "system_connected_for_observation": all(
            x["status"] == "CURRENT_OBSERVATION" for x in sources.values()
        ),
        # No cross-source canonical entity joins have been attested, so even
        # positive aggregate metrics do not close a particular buyer loop.
        "fully_verified_commercial_loop": False,
        "proposed_next_work": [
            {"owner": owner, "task": action, "automatic_execution_authorized": False}
            for owner, action in actions
        ],
        "dispatched_tasks": 0, "db_writes": False,
        "emails_sent": False, "payments_executed": False,
        "outbound_authorized": False, "execution_authority": "NONE",
    }
