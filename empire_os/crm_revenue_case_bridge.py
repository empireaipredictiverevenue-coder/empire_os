"""V11 original signed CRM exact-order -> revenue case bridge (READ ONLY).

Reuses the original owner-signed/tenant-scoped SECURITY DEFINER lineage RPC
and the existing original Revenue CRM tenant-scoped prospect view. No raw
orders, binding tables, second login, new RPC, queue or payment writer.
Owner HELD RPC remains required; never manufacture a scoped order from a view.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from empire_os.canonical_revenue_case_progress import review_one_canonical_revenue_case
from empire_os.crm_scoped_lineage_reader import review_signed_scoped_lineage
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
from empire_os.revenue_crm_transport import (
    PostgresRevenueCrmRepository,
    RevenueCrmTransportError,
)

SCHEMA = "empire.crm.signed_order_to_revenue_case.v1"
CRM_LINEAGE_SCHEMA = "empire.crm.scoped_lineage_review.v1"
CANONICAL_LINEAGE_STATUS = "EXACT_TENANT_SCOPED_RECEIPT_OBSERVED_NOT_PROMOTED"
REPORTED_ORDER_STATES = frozenset({
    "raw", "qualified", "matched", "offered", "accepted", "delivered",
    "confirmed", "invoiced", "paid", "settled", "outcome_captured",
    "rejected", "cancelled",
})


def _uuid(value: Any) -> str:
    if not isinstance(value, str):
        raise ProspectHandoffHold("EXACT_CANONICAL_CRM_CASE_IDS_REQUIRED")
    try:
        if str(UUID(value)) != value:
            raise ValueError("noncanonical UUID")
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProspectHandoffHold("EXACT_CANONICAL_CRM_CASE_IDS_REQUIRED") from exc
    return value


def _private_founder_case_view(case: dict[str, Any]) -> dict[str, Any]:
    """Minimal, non-PII display model; NOT authentication or route authority.

    Called only AFTER the original signed CRM reader returns a scoped order.
    Never expose UUIDs, bearer, DSN, source payloads or payment references.
    The API/console owner must separately enforce its real session boundary.
    """
    if (case.get("authenticated_crm_order_observed") is not True
            or case.get("authenticated_crm_signed_membership_verified") is not True
            or case.get("authenticated_crm_tenant_scope_verified") is not True
            or case.get("mode") != "OBSERVE"
            or case.get("execution_authority") != "NONE"
            or case.get("revenue_recognized_here") is not False
            or case.get("eligible_for_learning") is not False
            or case.get("database_writes") is not False):
        raise ProspectHandoffHold("ORIGINAL_CRM_FOUNDER_VIEW_NOT_AUTHENTICATED")
    stages = case.get("source_handoff_stages")
    if (not isinstance(stages, list) or len(stages) != 5
            or any(not isinstance(s, dict)
                   or s.get("status") not in ("NOT_OBSERVED", "SOURCE_REPORTED_COHERENCE_ONLY")
                   or not isinstance(s.get("stage"), str)
                   for s in stages)):
        raise ProspectHandoffHold("ORIGINAL_CRM_FOUNDER_STAGES_UNTRUSTED")
    return {
        "schema_version": "empire.crm.founder_revenue_case_view.v1",
        "status": "SIGNED_ORDER_OBSERVED_FINANCIAL_PROOF_UNATTESTED",
        "mode": "OBSERVE",
        "case_ref": case["case_id"],
        "reported_order_state": case.get("original_crm_order_state_reported"),
        "next_missing_stage": case["next_missing_stage"],
        "next_original_owner": case["next_original_owner"],
        "next_original_action": case["next_original_action"],
        "stages": [{"stage": item["stage"], "status": item["status"]} for item in stages],
        "independent_evidence_attested_here": False,
        "recognized_revenue_verified_here": False,
        "economic_memory_training_authorized": False,
        "database_writes": False,
        "outbound_sent": False,
        "execution_authority": "NONE",
    }


def review_signed_crm_revenue_case(
    *,
    signed_crm_bearer: str,
    crm_verifier: SignedCrmTenantVerifier,
    dedicated_crm_dsn: str,
    prospect_id: str,
    opportunity_id: str,
    fulfilment_order_id: str,
    as_of: datetime,
) -> dict[str, Any]:
    """Read exactly one owner-authorised existing order, then show V11 gaps.

    This is an integration gate, not an alternative authority or a public API.
    No injected DB factory or caller-supplied stage receipt is accepted.
    A held/uninstalled CRM RPC prevents even a positive order source report.
    """
    prospect = _uuid(prospect_id)
    opportunity = _uuid(opportunity_id)
    order = _uuid(fulfilment_order_id)
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ProspectHandoffHold("AWARE_CRM_REVENUE_CASE_TIME_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ProspectHandoffHold("ORIGINAL_SIGNED_CRM_VERIFIER_REQUIRED")

    # All signature, active membership, fixed role, session_user-bound tenant
    # and owner-reviewed security-definer provenance tests live in ONE owner.
    scoped = review_signed_scoped_lineage(
        signed_crm_bearer=signed_crm_bearer,
        crm_verifier=crm_verifier,
        dedicated_crm_dsn=dedicated_crm_dsn,
        prospect_id=prospect,
        opportunity_id=opportunity,
        evidence_id=order,
        evidence_kind="order",
        as_of=as_of,
    )
    if (not isinstance(scoped, dict)
            or scoped.get("schema_version") != CRM_LINEAGE_SCHEMA
            or scoped.get("status") != CANONICAL_LINEAGE_STATUS
            or scoped.get("mode") != "OBSERVE"
            or scoped.get("receipt_kind") != "order"
            or scoped.get("receipt_id") != order
            or scoped.get("prospect_id") != prospect
            or scoped.get("opportunity_id") != opportunity
            or scoped.get("signed_crm_membership_verified") is not True
            or scoped.get("original_db_tenant_scope_checked") is not True
            or scoped.get("real_database_connector_used") is not True
            or scoped.get("source_rights_verified") is not False
            or scoped.get("buyer_terms_verified") is not False
            or scoped.get("buyer_capacity_verified") is not False
            or scoped.get("settlement_verified") is not False
            or scoped.get("recognised_revenue_verified") is not False
            or scoped.get("database_writes") is not False
            or scoped.get("outbound_authorized") is not False
            or scoped.get("execution_authority") != "NONE"):
        raise ProspectHandoffHold("ORIGINAL_SIGNED_ORDER_RPC_NOT_ATTESTED")
    tenant = _uuid(scoped.get("tenant_id"))
    buyer = _uuid(scoped.get("buyer_id"))
    entity = _uuid(scoped.get("entity_id"))

    # Reuse only the ORIGINAL CRM protected prospect view through the existing
    # tenant/session_user checked transport. No SELECT on raw orders or links.
    try:
        row = PostgresRevenueCrmRepository(
            dedicated_crm_dsn, tenant_id=tenant,
        ).prospect(prospect)
    except RevenueCrmTransportError as exc:
        raise ProspectHandoffHold("ORIGINAL_TENANT_SCOPED_PROSPECT_VIEW_UNAVAILABLE") from exc
    if row is None:
        raise ProspectHandoffHold("EXACT_ORIGINAL_CRM_PROSPECT_VIEW_ROW_REQUIRED")
    if (not isinstance(row, dict)
            or str(row.get("tenant_id")) != tenant
            or str(row.get("prospect_id")) != prospect
            or str(row.get("buyer_id")) != buyer
            or str(row.get("fulfilment_order_id")) != order):
        raise ProspectHandoffHold("CRM_VIEW_AND_SIGNED_ORDER_IDENTITY_MISMATCH")

    state = row.get("fulfilment_state")
    if state is not None and (not isinstance(state, str)
                             or state not in REPORTED_ORDER_STATES):
        raise ProspectHandoffHold("INVALID_ORIGINAL_CRM_ORDER_STATE")
    # No V7 acceptance/V8 delivery/V9 settlement evidence was read here.
    # These cannot be deduced from a CRM view's 'paid' or 'settled' text.
    case = review_one_canonical_revenue_case(
        tenant_id=tenant, fulfilment_order_id=order,
    )
    case.update(
        authenticated_crm_order_observed=True,
        authenticated_crm_signed_membership_verified=True,
        authenticated_crm_tenant_scope_verified=True,
        original_crm_order_state_reported=state,
        original_crm_prospect_id=prospect,
        original_crm_buyer_id=buyer,
        original_crm_entity_id=entity,
        original_crm_opportunity_id=opportunity,
    )
    return {
        "schema_version": SCHEMA,
        "status": "ORIGINAL_SIGNED_CRM_ORDER_OBSERVED_REVIEW_ONLY",
        "mode": "OBSERVE",
        "tenant_id": tenant,
        "fulfilment_order_id": order,
        "crm_order_source": "ORIGINAL_SIGNED_TENANT_RPC_AND_TENANT_SCOPED_PROSPECT_VIEW",
        "revenue_case": case,
        "founder_case_view": _private_founder_case_view(case),
        "original_crm_owner_rpc_approved_by_this_bridge": False,
        "real_buyer_terms_independently_verified_here": False,
        "external_delivery_verified_here": False,
        "external_payment_verified_here": False,
        "recognized_revenue_verified_here": False,
        "crm_mutation_authorized": False,
        "model_training_authorized": False,
        "outbound_sent": False,
        "payments_executed": False,
        "database_writes": False,
        "execution_authority": "NONE",
    }
