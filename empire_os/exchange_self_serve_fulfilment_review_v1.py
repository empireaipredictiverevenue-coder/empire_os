"""Evidence-only self-serve Exchange fulfilment and recurring-membership review.

The existing /buy self-serve flow records interest, not a paid order.
This module cannot activate a subscription, allocate or deliver a lead,
query EmpireDB, bill, acknowledge payment or recognise actual MRR.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from empire_os.lead_exchange_live_inventory import build_lead_exchange_live_inventory
from empire_os.exchange_a2a_research_signal_bridge_v1 import summarise_a2a_for_exchange
from empire_os.phase4_exchange_mrr_products import (
    EXCHANGE_MRR_PRODUCTS,
    EXCHANGE_BASE_USAGE_PRICES_CENTS,
)

SCHEMA = "empire.exchange.self_serve_fulfilment_mrr_review.v1"
PRICE_CODES = frozenset(row.product_code for row in EXCHANGE_MRR_PRODUCTS)

# Proof gates are separate for the subscription-access product and *each*
# underlying consumer-lead event; no lower-tier discount skips legal rights.
SUBSCRIPTION_GATES = (
    "verified_buyer_identity_and_tenant_authority",
    "accepted_product_terms_and_clear_access_scope",
    "canonical_empiredb_subscription_and_entitlement_receipt",
    "approved_usdt_bsc_payment_and_independent_settlement_receipt",
    "renewal_invoice_schedule_and_dunning_or_expiry_controls",
    "cancellation_refund_dispute_and_no_supply_disclosure",
)
DELIVERY_GATES = (
    "permitted_first_party_or_contractually_licensed_source",
    "person_specific_notice_consent_and_transfer_rights_where_applicable",
    "recipient_purpose_and_jurisdiction_match",
    "canonical_identity_duplicate_opt_out_and_suppression_check",
    "fresh_inventory_quality_and_buyer_requested_type_match",
    "verified_active_buyer_capacity_and_corridor_or_territory",
    "exclusive_reservation_and_allocation_idempotency_check",
    "approved_destination_authentication_and_transport_health",
    "recorded_delivery_acknowledgement_and_rejection_window",
    "accepted_billable_event_and_independent_usage_settlement",
)

def _hold(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "state": "HOLD",
        "reason": reason,
        "execution_authority": "none",
        "subscription_activation_authorized": False,
        "lead_delivery_authorized": False,
        "automatic_allocation_authorized": False,
        "recognized_mrr_cents": 0,
        "actual_customer_cash_verified_cents": 0,
        "lead_revenue_verified_cents": 0,
        "database_writes": False,
        "external_messages_sent": 0,
    }


def build_exchange_self_serve_fulfilment_review(
    exchange_snapshot: Mapping[str, Any],
    *,
    interest_receipt: Mapping[str, Any] | None = None,
    a2a_owner_queue: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Produce metadata-only operator plan from existing snapshot + optional buyer interest.

    Even a valid canonical projection or self-reported interest receipt grants
    no subscription/payment/identity/consent/fulfilment authority.
    """
    if not isinstance(exchange_snapshot, Mapping):
        return _hold("canonical_exchange_snapshot_missing")
    if (exchange_snapshot.get("schema_version") != "empire.commercial_exchange_snapshot.v1"
            or exchange_snapshot.get("canonical_backend") != "empiredb"
            or exchange_snapshot.get("source") != "canonical_empiredb_projection"
            or exchange_snapshot.get("mode") != "OBSERVE"
            or exchange_snapshot.get("execution_authority") != "none"
            or exchange_snapshot.get("automatic_external_delivery") is not False):
        return _hold("untrusted_exchange_snapshot")
    if (type(exchange_snapshot.get("inventory_count")) is not int
            or type(exchange_snapshot.get("buyer_seat_count")) is not int):
        return _hold("invalid_exchange_counts")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("timezone_aware_now_required")
    projection = build_lead_exchange_live_inventory(
        exchange_snapshot, now=current,
    )
    if projection.get("state") not in (
        "FRESH_CANONICAL_SNAPSHOT", "STALE_CANONICAL_SNAPSHOT",
    ):
        return _hold("exchange_aggregate_validation_failed")

    product = None
    tier_code = None
    intent = "NO_BUYER_INTEREST_RECEIPT_ATTACHED"
    if interest_receipt is not None:
        if not isinstance(interest_receipt, Mapping):
            return _hold("invalid_buyer_interest_record")
        tier_code = interest_receipt.get("tier_code")
        product = next(
            (x for x in EXCHANGE_MRR_PRODUCTS if x.product_code == tier_code),
            None,
        )
        if (product is None or interest_receipt.get("decision") != "interest_recorded"
                or interest_receipt.get("pricing_binding") is not False
                or interest_receipt.get("seat_activated") is not False
                or interest_receipt.get("commercial_terms_verified") is not False
                or interest_receipt.get("capacity_verified") is not False
                or interest_receipt.get("actual_revenue") is not False
                or interest_receipt.get("delivery_preference") not in
                    {"email", "webhook", "api", "phone"}):
            return _hold("buyer_interest_must_not_impersonate_paid_order")
        intent = "BUYER_STATED_NON_BINDING_INTEREST"
    plans = [{
        "product_code": row.product_code,
        "monthly_membership_price_cents": row.monthly_price_cents,
        "monthly_price_currency": "USD",
        "corridor_limit": row.corridor_limit,
        "delivery_modes": list(row.delivery_modes),
        "binding_terms_ready": row.binding_terms_ready,
        "membership_is_guaranteed_lead_volume": False,
        "billable_event_price_is_additional_to_membership": True,
        "paid_or_active_customer_subscriptions_verified": 0,
    } for row in EXCHANGE_MRR_PRODUCTS]
    eligibility = {
        "canonical_selected_research_inventory": projection["selected_inventory_records"],
        "missing_evidence_inventory": projection["evidence_hold_records"],
        "no_buyer_capacity_waitlist": projection["buyer_capacity_waitlist_records"],
        "allocation_candidate_records": projection["allocation_candidate_records"],
        "allocated_records": projection["allocated_records"],
        "buyer_seat_records": projection["buyer_seat_records"],
        "verified_active_capacity_seat_records": projection["active_capacity_seat_records"],
        "delivery_ready_now": projection["delivery_ready_now"],
        "fresh": projection["snapshot_fresh"],
    }
    blockers = list(SUBSCRIPTION_GATES) + list(DELIVERY_GATES)
    if not projection["snapshot_fresh"]:
        blockers.insert(0, "fresh_canonical_empiredb_market_snapshot")
    if projection["allocation_candidate_records"] == 0:
        blockers.insert(0, "no_current_allocation_candidate")
    if projection["active_capacity_seat_records"] == 0:
        blockers.insert(0, "no_verified_active_buyer_capacity")
    if interest_receipt is None:
        blockers.insert(0, "no_individual_buyer_interest_receipt")
    elif product and interest_receipt["delivery_preference"] not in product.delivery_modes:
        blockers.insert(0, "requested_delivery_mode_outside_selected_tier")

    return {
        "schema_version": SCHEMA,
        "state": "OPERATOR_REVIEW_ONLY",
        "source": "read_only_canonical_exchange_aggregate",
        "source_snapshot_at": exchange_snapshot.get("observed_at"),
        "buyer_interest_state": intent,
        "requested_product_code": tier_code,
        "requested_product_monthly_price_cents": (
            product.monthly_price_cents if product else None
        ),
        "requested_delivery_mode_supported": (
            interest_receipt["delivery_preference"] in product.delivery_modes
            if product else None
        ),
        "plan_catalog": plans,
        "usage_class_base_prices_cents_catalog_not_binding": dict(
            EXCHANGE_BASE_USAGE_PRICES_CENTS,
        ),
        "canonical_inventory": eligibility,
        "a2a_research_only": summarise_a2a_for_exchange(a2a_owner_queue),
        "subscription_lifecycle": [
            "INTEREST_RECORDED_NOT_BILLED",
            "BUYER_IDENTITY_AND_TERMS_REVIEW",
            "PENDING_PAYMENT_INVOICE",
            "INDEPENDENT_BSC_SETTLEMENT_RECONCILED",
            "CANONICAL_SUBSCRIPTION_ENTITLEMENT_REVIEW",
            "ACTIVE_MEMBERSHIP_ACCESS",
            "RENEWAL_DUE_OR_PAST_DUE",
            "PAUSED_EXPIRED_OR_CANCELLED",
        ],
        "per_lead_fulfilment_lifecycle": [
            "RIGHTS_AND_CONSENT_EVIDENCE",
            "IDENTITY_DEDUPE_AND_SUPPRESSION",
            "TERRITORY_AND_BUYER_CAPACITY",
            "IDEMPOTENT_RESERVATION",
            "AUTHORIZED_DELIVERY_AND_ACK",
            "BUYER_ACCEPT_REJECT_WINDOW",
            "ACTUAL_USAGE_SETTLEMENT_AND_REFUNDS",
        ],
        "subscription_gate_proofs_not_provided": list(SUBSCRIPTION_GATES),
        "per_lead_gate_proofs_not_provided": list(DELIVERY_GATES),
        "blockers": list(dict.fromkeys(blockers)),
        "membership_is_not_guaranteed_lead_volume": True,
        "buyer_qualified_discount_may_reduce_commercial_review_not_privacy_or_source_rights": True,
        "subscription_and_usage_billing_must_be_separate": True,
        "legacy_sqlite_billing_not_accepted": True,
        "payment_rail": "USDT_BSC",
        "usdt_bsc_monthly_renewal_requires_new_verified_payment_event": True,
        "no_authentic_subscription_or_payment_proofs_accepted": True,
        "actual_contract_subscriptions_verified": 0,
        "recognized_mrr_cents": 0,
        "actual_customer_cash_verified_cents": 0,
        "lead_revenue_verified_cents": 0,
        "subscription_activation_authorized": False,
        "lead_delivery_authorized": False,
        "automatic_allocation_authorized": False,
        "external_messages_sent": 0,
        "database_writes": False,
        "execution_authority": "none",
        "next_owner": "existing_commercial_exchange_checkout_crm_payment_and_fulfilment_owners",
    }
