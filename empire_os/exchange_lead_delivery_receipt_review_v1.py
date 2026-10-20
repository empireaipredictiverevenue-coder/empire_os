"""Strict join contract for Exchange per-lead delivery and usage evidence.

All inputs are untrusted offline/review copies until independently obtained
from canonical EmpireDB with tenant/RLS and delivery-provider authority.
Even a structurally valid customer acceptance is never automatically a sale,
an entitled seat, an outbound delivery, payment or recognized MRR.
"""
from __future__ import annotations
from collections.abc import Mapping
from datetime import datetime,timezone
from typing import Any
from uuid import UUID
import re

from empire_os.phase4_exchange_mrr_products import EXCHANGE_MRR_PRODUCTS

SCHEMA="empire.exchange.lead_delivery_receipt_review.v1"
PRODUCTS={p.product_code:p for p in EXCHANGE_MRR_PRODUCTS}
HEX64=re.compile(r"^[0-9a-f]{64}$")
MAX_CAPACITY=10000


def _identity(value:Any)->bool:
    if type(value) is not str:
        return False
    try:
        return str(UUID(value))==value
    except ValueError:
        return False


def _at(value:Any)->datetime|None:
    if type(value) is not str:
        return None
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError,ValueError):
        return None


def _result(blockers:list[str],*,consistent:bool=False)->dict[str,Any]:
    return {
        "schema_version":SCHEMA,
        "state":("CROSS_RECEIPT_DELIVERY_SHAPE_CONSISTENT_NOT_AUTHENTICATED"
                 if consistent else "HOLD"),
        "blockers":sorted(set(blockers)),
        "canonical_source_rows_independently_authenticated":False,
        "canonical_tenant_and_rls_verified":False,
        "buyer_entitlement_activated":False,
        "customer_delivery_executed":False,
        "customer_delivery_claimed":False,
        "buyer_acceptance_accepted_as_verified_revenue":False,
        "lead_event_billed":False,
        "lead_usage_revenue_recognized_cents":0,
        "monthly_subscription_mrr_changed_cents":0,
        "no_personal_details_emitted":True,
        "canonical_replay_prevented_by_authoritative_writer":False,
        "buyer_qualified_tier_skips_privacy_or_rights":False,
        "database_writes":False,
        "outbound_messages_sent":0,
        "execution_authority":"none",
    }


def review_exchange_lead_delivery_receipts(
    *,
    entitlement:Mapping[str,Any],
    inventory:Mapping[str,Any],
    allocation:Mapping[str,Any],
    acknowledgement:Mapping[str,Any],
    now:datetime|None=None,
)->dict[str,Any]:
    if not all(isinstance(x,Mapping) for x in
               (entitlement,inventory,allocation,acknowledgement)):
        return _result(["missing_required_canonical_receipt"])
    current=now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("timezone_aware_now_required")
    current=current.astimezone(timezone.utc)
    blockers=[]
    e_buyer=entitlement.get("buyer_id")
    e_id=entitlement.get("entitlement_id")
    i_id=inventory.get("inventory_id")
    a_id=allocation.get("allocation_id")
    if not all(_identity(x) for x in (e_buyer,e_id,i_id,a_id)):
        blockers.append("canonical_record_identity_missing")
    if (allocation.get("buyer_id")!=e_buyer
            or acknowledgement.get("buyer_id")!=e_buyer
            or allocation.get("entitlement_id")!=e_id):
        blockers.append("buyer_entitlement_allocation_identity_mismatch")
    if (allocation.get("inventory_id")!=i_id
            or acknowledgement.get("inventory_id")!=i_id
            or acknowledgement.get("allocation_id")!=a_id):
        blockers.append("lead_allocation_delivery_ack_identity_mismatch")
    plan=PRODUCTS.get(entitlement.get("product_code"))
    if (plan is None or entitlement.get("membership_status")!="active"
            or entitlement.get("payment_period_settled") is not True):
        blockers.append("authentic_active_membership_entitlement_required")
    start=_at(entitlement.get("period_start"))
    end=_at(entitlement.get("period_end"))
    if not start or not end or not start<=current<end:
        blockers.append("membership_period_missing_or_expired")
    corridor=allocation.get("corridor_key")
    corridors=entitlement.get("authorized_corridor_keys")
    if (not isinstance(corridor,str) or len(corridor)>170
            or not corridor.startswith("corridor:")
            or not isinstance(corridors,list)
            or len(corridors)>25
            or corridor not in corridors
            or len(set(str(x) for x in corridors))!=len(corridors)
            or plan is None
            or (plan.corridor_limit is not None and
                len(corridors)>plan.corridor_limit)
            or inventory.get("corridor_key")!=corridor):
        blockers.append("exact_corridor_or_plan_entitlement_mismatch")

    if (inventory.get("source_rights_verified") is not True
            or inventory.get("third_party_transfer_permitted") is not True
            or inventory.get("retention_and_deletion_terms_verified") is not True):
        blockers.append("lead_source_and_transfer_rights_missing")
    kind=inventory.get("lead_origin_kind")
    if kind not in ("first_party_consumer_opt_in","contracted_partner_consumer_opt_in","verified_business_enquiry"):
        blockers.append("research_signal_not_a_deliverable_lead")
    if kind in ("first_party_consumer_opt_in","contracted_partner_consumer_opt_in") and (
            inventory.get("individual_notice_and_opt_in_verified") is not True
            or inventory.get("named_or_allowed_recipient_scope_verified") is not True):
        blockers.append("individual_recipient_specific_consented_transfer_missing")
    if (inventory.get("canonical_dedupe_and_suppression_clear") is not True
            or inventory.get("person_or_company_scope_verified") is not True
            or inventory.get("jurisdiction_and_territory_eligible") is not True):
        blockers.append("canonical_identity_or_suppression_review_missing")
    if (inventory.get("high_risk_sensitive_personal_data") is not False
            or inventory.get("revocation_observed") is not False):
        blockers.append("revoked_or_sensitive_person_data_hold")

    cap=entitlement.get("capacity_remaining")
    if type(cap) is not int or not 1<=cap<=MAX_CAPACITY:
        blockers.append("verified_buyer_capacity_required")
    if (allocation.get("state") not in ("reserved","delivered")
            or allocation.get("reservation_unique_in_canonical_db") is not True
            or allocation.get("exclusivity_or_nonexclusive_rights_clear") is not True):
        blockers.append("canonical_idempotent_reservation_not_verified")
    if (allocation.get("delivery_channel") not in ("email","webhook","api","private_feed")
            or plan is None
            or allocation.get("delivery_channel") not in
                (plan.delivery_modes if plan else ())
            or allocation.get("authenticated_destination_verified") is not True):
        blockers.append("authenticated_plan_eligible_delivery_not_verified")

    delivery_at=_at(acknowledgement.get("delivered_at"))
    ack_at=_at(acknowledgement.get("acknowledged_at"))
    if (allocation.get("state")!="delivered"
            or acknowledgement.get("delivery_state")!="acknowledged"
            or not delivery_at or not ack_at or not delivery_at<=ack_at<=current):
        blockers.append("authenticated_delivery_acknowledgement_missing")
    if (acknowledgement.get("buyer_event_decision")!="accepted"
            or acknowledgement.get("buyer_acceptance_reason_reviewed") is not True
            or acknowledgement.get("rejection_and_dispute_window_reviewed") is not True):
        blockers.append("buyer_acceptance_and_dispute_event_missing")
    if (type(acknowledgement.get("agreed_usage_charge_cents")) is not int
            or acknowledgement["agreed_usage_charge_cents"]<=0
            or acknowledgement.get("usage_terms_sha256")!=entitlement.get("usage_terms_sha256")
            or not isinstance(entitlement.get("usage_terms_sha256"),str)
            or not HEX64.fullmatch(entitlement["usage_terms_sha256"])):
        blockers.append("usage_price_contract_and_acceptance_missing")
    if blockers:
        return _result(blockers)
    return _result([
        "independent_canonical_delivery_and_buyer_ack_retrieval_required",
        "recheck_live_allocation_uniqueness_and_no_replay_before_release",
        "payment_and_accepted_event_independent_usage_settlement_required",
    ],consistent=True)
