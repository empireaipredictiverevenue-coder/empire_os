"""V10: connect V9 order/settlement continuity to ORIGINAL Economic Memory.

Bounded, read-only review. The caller must supply the existing authorized
ExecutionBusDataRepository; no caller-supplied feedback is accepted. This
does NOT attest chain finality, independent cash receipt, the reversal census,
external cost provenance, or authority to persist/learn from a candidate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from empire_os.canonical_settlement_handoff import SCHEMA as V9_SCHEMA
from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
from empire_os.outcome_feedback import validate_verified_feedback
from empire_os.economic_memory import build_economic_memory_snapshot

SCHEMA = "empire.canonical.settlement_to_economic_memory_handoff.v1"
ORDER_KEYS = ("tenant_id", "buyer_id", "prospect_id", "entity_id",
              "opportunity_id", "fulfilment_order_id")
FORBIDDEN_TRUE = (
    "payment_receipt_independently_verified_here",
    "blockchain_finality_independently_verified_here",
    "refund_and_dispute_census_complete_here",
    "actual_costs_independently_verified_here",
    "revenue_recognition_independently_verified_here",
    "economic_memory_authorized", "payments_executed",
    "outbound_authorized", "database_writes",
)


def _canonical_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (TypeError, ValueError, AttributeError):
        return False


def review_original_economic_memory_handoff(
    settlement: Mapping[str, Any],
    *,
    repository: ExecutionBusDataRepository,
    tenant_id: str,
    repo_root: str | Path,
    as_of: datetime,
) -> dict[str, Any]:
    """Perform one exact order's original-owner shadow preview, never write.

    The V9 reviewer does not independently certify external financial truth.
    Even a coherent original owner feedback packet and Economic Memory preview
    cannot bypass separate BSC, counterparty, reversal and revenue controls.
    """
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ProspectHandoffHold("AWARE_ECONOMIC_MEMORY_REVIEW_TIME_REQUIRED")
    now = as_of.astimezone(timezone.utc)
    if (not isinstance(settlement, Mapping)
            or settlement.get("schema_version") != V9_SCHEMA
            or settlement.get("status") != "TENANT_SCOPED_FINANCIAL_LINEAGE_REVIEW_ONLY"
            or settlement.get("mode") != "OBSERVE"
            or settlement.get("execution_authority") != "NONE"
            or settlement.get("ledger_payment_link_consistent") is not True
            or settlement.get("revenue_event_consistent") is not True
            or settlement.get("settlement_source_reported") not in
                ("direct_payment", "escrow_release")
            or any(settlement.get(k) is not False for k in FORBIDDEN_TRUE)):
        raise ProspectHandoffHold("UNTRUSTED_OR_UNRECOGNIZED_SETTLEMENT_HANDOFF")
    if (not _canonical_uuid(tenant_id)
            or settlement.get("tenant_id") != tenant_id
            or any(not _canonical_uuid(settlement.get(k)) for k in ORDER_KEYS)
            or not _canonical_uuid(settlement.get("payment_request_id"))
            or not _canonical_uuid(settlement.get("settlement_evidence_id"))
            or settlement.get("approved_price_cents") is None
            or type(settlement["approved_price_cents"]) is not int
            or settlement["approved_price_cents"] <= 0):
        raise ProspectHandoffHold("CROSS_TENANT_OR_UNSCOPED_MEMORY_IDENTITY")
    if (not isinstance(repo_root, (str, Path))
            or not str(repo_root).strip()):
        raise ProspectHandoffHold("ORIGINAL_REPOSITORY_ROOT_REQUIRED")
    if not isinstance(repository, ExecutionBusDataRepository):
        raise ProspectHandoffHold("ORIGINAL_CANONICAL_OUTCOME_READER_REQUIRED")
    try:
        backend = repository._gateway.snapshot().as_dict().get("primary_backend")
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ProspectHandoffHold("ORIGINAL_CANONICAL_GATEWAY_UNAVAILABLE") from exc
    if backend != "empiredb":
        raise ProspectHandoffHold("CANONICAL_EMPIREDB_REQUIRED")

    order_id = settlement["fulfilment_order_id"]
    # This is the only permitted source of feedback, never an injected packet.
    try:
        feedback = repository.verified_outcome_feedback(
            order_id, tenant_id=tenant_id, repo_root=Path(repo_root),
            as_of=now,
        )
        validate_verified_feedback(feedback, tenant_id=tenant_id, as_of=now)
    except (ValueError, TypeError, LookupError, KeyError, OSError, RuntimeError) as exc:
        raise ProspectHandoffHold("ORIGINAL_VERIFIED_OUTCOME_READ_HELD") from exc
    if not isinstance(feedback, Mapping):
        raise ProspectHandoffHold("ORIGINAL_VERIFIED_OUTCOME_READ_HELD")
    for key in ("tenant_id", "buyer_id", "prospect_id", "entity_id",
                "fulfilment_order_id"):
        if feedback.get(key) != settlement[key]:
            raise ProspectHandoffHold("CROSS_ORDER_BUYER_OR_TENANT_MEMORY_REJECTED")
    outcome_ref = settlement.get("commercial_outcome_ref")
    event_ref = settlement.get("recognized_revenue_event_ref")
    if (not isinstance(outcome_ref, str)
            or not outcome_ref.startswith("canonical:commercial_outcomes:")
            or feedback.get("outcome_ref") != outcome_ref
            or not isinstance(event_ref, str)
            or not event_ref.startswith("canonical:commercial_events:")
            or event_ref not in feedback.get("evidence_refs", ())
            or outcome_ref not in feedback.get("evidence_refs", ())):
        raise ProspectHandoffHold("ORIGINAL_OUTCOME_REVENUE_EVENT_LINEAGE_MISMATCH")
    payment_table = ("bsc_payment_evidence" if
                     settlement["settlement_source_reported"] == "direct_payment"
                     else "bsc_escrow_evidence")
    payment_ref = ("canonical:" + payment_table + ":"
                   + settlement["settlement_evidence_id"])
    if payment_ref not in feedback.get("evidence_refs", ()):
        raise ProspectHandoffHold("ORIGINAL_PAYMENT_PROOF_LINEAGE_MISMATCH")
    gross = feedback.get("actual_revenue_cents")
    cost = feedback.get("actual_cost_cents")
    profit = feedback.get("gross_profit_cents")
    if (feedback.get("conversion_outcome") != "won"
            or feedback.get("actual_revenue") is not True
            or feedback.get("verified_label") != 1
            or type(gross) is not int
            or gross != settlement["approved_price_cents"]
            or type(cost) is not int or cost < 0
            or type(profit) is not int or profit <= 0
            or type(settlement.get("reported_recognized_cost_cents")) is not int
            or type(settlement.get("reported_recognized_margin_cents")) is not int
            or cost != settlement["reported_recognized_cost_cents"]
            or profit != settlement["reported_recognized_margin_cents"]
            or profit != gross - cost):
        raise ProspectHandoffHold("UNRECONCILED_ORIGINAL_RECOGNIZED_ECONOMICS")

    # Existing Economic Memory makes a transient SHADOW preview. No refresh,
    # filesystem write, output JSON publication, dispatcher or model training.
    try:
        preview = build_economic_memory_snapshot(
            executive_evaluation={}, department_work=[],
            cortex_learning={"packets": [feedback["cortex_packet"]]},
            tenant_id=tenant_id, verified_feedback=[feedback],
            calibration_reviews=[], as_of=now,
        )
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ProspectHandoffHold("ORIGINAL_ECONOMIC_MEMORY_PREVIEW_HELD") from exc
    if (preview.get("schema_version") != "empire.economic_memory.v1"
            or preview.get("mode") != "OBSERVE"
            or preview.get("execution_authority") != "none"
            or preview.get("accounting_authority") != "none"
            or preview.get("commercial_authority") != "none"
            or preview.get("promoted_learning") is not False
            or preview.get("model_weight_mutation_authorized") is not False):
        raise ProspectHandoffHold("UNTRUSTED_ORIGINAL_MEMORY_PREVIEW")
    return {
        "schema_version": SCHEMA,
        "status": "ORIGINAL_SHADOW_MEMORY_COHERENCE_ONLY_NOT_FINANCIAL_FINALITY",
        "mode": "OBSERVE",
        "tenant_id": tenant_id,
        "fulfilment_order_id": order_id,
        "original_feedback_ref": outcome_ref,
        "original_revenue_event_ref": event_ref,
        "original_payment_evidence_ref": payment_ref,
        "reported_revenue_cents": gross,
        "reported_actual_cost_cents": cost,
        "reported_gross_profit_cents": profit,
        "original_owner_feedback_consistent": True,
        "original_economic_memory_preview_candidate_count":
            preview.get("outcome_memory_candidate_count", 0),
        "original_economic_memory_preview_retrievable_count":
            preview.get("outcome_conditioned_memory_count", 0),
        "original_feedback_independent_financial_attestation": False,
        "complete_reversal_census_verified_here": False,
        "bsc_finality_independently_verified_here": False,
        "buyer_funds_independently_verified_here": False,
        "economic_memory_persisted": False,
        "model_training_authorized": False,
        "payments_executed": False,
        "outbound_authorized": False,
        "database_writes": False,
        "execution_authority": "NONE",
        "next_original_owner": "RevenueRecognition",
        "next_original_action":
            "ATTEST_SETTLEMENT_REVERSALS_COST_CUSTODY_AND_PRODUCTION_TENANT_RPC",
    }
