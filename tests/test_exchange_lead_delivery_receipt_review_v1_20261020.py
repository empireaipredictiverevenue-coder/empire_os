"""Self-serve seat delivery and usage cannot turn researched sites into leads."""
from copy import deepcopy
from datetime import datetime,timezone
import json
import pytest

from empire_os.exchange_lead_delivery_receipt_review_v1 import (
    review_exchange_lead_delivery_receipts,
)

NOW=datetime(2026,10,20,18,45,tzinfo=timezone.utc)
BUYER="22222222-2222-4222-8222-222222222222"
ENTITLEMENT="33333333-3333-4333-8333-333333333333"
INVENTORY="44444444-4444-4444-8444-444444444444"
ALLOCATION="55555555-5555-4555-8555-555555555555"
CORRIDOR="corridor:v1:roofing:tampa:qualified_lead:lead"

def fixture():
    return dict(
        entitlement=dict(
            entitlement_id=ENTITLEMENT,buyer_id=BUYER,
            product_code="exchange_seat_starter",
            membership_status="active",payment_period_settled=True,
            period_start="2026-10-01T00:00:00Z",
            period_end="2026-11-01T00:00:00Z",
            authorized_corridor_keys=[CORRIDOR],
            capacity_remaining=1,
            usage_terms_sha256="f"*64,
        ),
        inventory=dict(
            inventory_id=INVENTORY,corridor_key=CORRIDOR,
            lead_origin_kind="first_party_consumer_opt_in",
            source_rights_verified=True,third_party_transfer_permitted=True,
            retention_and_deletion_terms_verified=True,
            individual_notice_and_opt_in_verified=True,
            named_or_allowed_recipient_scope_verified=True,
            canonical_dedupe_and_suppression_clear=True,
            person_or_company_scope_verified=True,
            jurisdiction_and_territory_eligible=True,
            high_risk_sensitive_personal_data=False,
            revocation_observed=False,
            private_contact="never-echo-me@example.com",
        ),
        allocation=dict(
            allocation_id=ALLOCATION,buyer_id=BUYER,
            entitlement_id=ENTITLEMENT,inventory_id=INVENTORY,
            corridor_key=CORRIDOR,state="delivered",
            reservation_unique_in_canonical_db=True,
            exclusivity_or_nonexclusive_rights_clear=True,
            delivery_channel="email",authenticated_destination_verified=True,
        ),
        acknowledgement=dict(
            allocation_id=ALLOCATION,inventory_id=INVENTORY,
            buyer_id=BUYER,
            delivery_state="acknowledged",
            delivered_at="2026-10-20T15:00:00Z",
            acknowledged_at="2026-10-20T15:01:00Z",
            buyer_event_decision="accepted",
            buyer_acceptance_reason_reviewed=True,
            rejection_and_dispute_window_reviewed=True,
            agreed_usage_charge_cents=5900,
            usage_terms_sha256="f"*64,
        ),
    )


def assess(**data):
    return review_exchange_lead_delivery_receipts(now=NOW,**data)


def test_synthetic_delivery_cross_join_cannot_claim_revenue_or_contact():
    x=assess(**fixture())
    assert x["state"]=="CROSS_RECEIPT_DELIVERY_SHAPE_CONSISTENT_NOT_AUTHENTICATED"
    assert x["buyer_entitlement_activated"] is False
    assert x["buyer_acceptance_accepted_as_verified_revenue"] is False
    assert x["customer_delivery_executed"] is False
    assert x["lead_usage_revenue_recognized_cents"]==0
    assert x["monthly_subscription_mrr_changed_cents"]==0
    serialized=json.dumps(x)
    assert "never-echo-me" not in serialized
    assert BUYER not in serialized and INVENTORY not in serialized


@pytest.mark.parametrize("label,change,blocked",[
    ("expired",lambda d:d["entitlement"].update(period_end="2026-10-19T00:00:00Z"),"membership_period_missing_or_expired"),
    ("unpaid",lambda d:d["entitlement"].update(payment_period_settled=False),"authentic_active_membership_entitlement_required"),
    ("seat_wrong_corridor",lambda d:d["entitlement"].update(authorized_corridor_keys=["corridor:v1:other:us:qualified_lead:lead"]),"exact_corridor_or_plan_entitlement_mismatch"),
    ("wrong_buyer",lambda d:d["allocation"].update(buyer_id=INVENTORY),"buyer_entitlement_allocation_identity_mismatch"),
    ("no_source_rights",lambda d:d["inventory"].update(third_party_transfer_permitted=False),"lead_source_and_transfer_rights_missing"),
    ("research_only",lambda d:d["inventory"].update(lead_origin_kind="public_business_research"),"research_signal_not_a_deliverable_lead"),
    ("optin_missing",lambda d:d["inventory"].update(individual_notice_and_opt_in_verified=False),"individual_recipient_specific_consented_transfer_missing"),
    ("recipient_missing",lambda d:d["inventory"].update(named_or_allowed_recipient_scope_verified=False),"individual_recipient_specific_consented_transfer_missing"),
    ("consent_revoked",lambda d:d["inventory"].update(revocation_observed=True),"revoked_or_sensitive_person_data_hold"),
    ("sensitive",lambda d:d["inventory"].update(high_risk_sensitive_personal_data=True),"revoked_or_sensitive_person_data_hold"),
    ("duplicate",lambda d:d["inventory"].update(canonical_dedupe_and_suppression_clear=False),"canonical_identity_or_suppression_review_missing"),
    ("no_capacity",lambda d:d["entitlement"].update(capacity_remaining=0),"verified_buyer_capacity_required"),
    ("not_reserved",lambda d:d["allocation"].update(reservation_unique_in_canonical_db=False),"canonical_idempotent_reservation_not_verified"),
    ("wrong_delivery",lambda d:d["allocation"].update(delivery_channel="api"),"authenticated_plan_eligible_delivery_not_verified"),
    ("unacked",lambda d:d["acknowledgement"].update(delivery_state="pending"),"authenticated_delivery_acknowledgement_missing"),
    ("not_accepted",lambda d:d["acknowledgement"].update(buyer_event_decision="rejected"),"buyer_acceptance_and_dispute_event_missing"),
    ("bad_price",lambda d:d["acknowledgement"].update(agreed_usage_charge_cents=0),"usage_price_contract_and_acceptance_missing"),
])
def test_entitlement_rights_delivery_and_usage_fail_closed(label,change,blocked):
    data=fixture()
    change(data)
    x=assess(**data)
    assert x["state"]=="HOLD",label
    assert blocked in x["blockers"],(label,x["blockers"])
    assert x["lead_usage_revenue_recognized_cents"]==0


def test_no_automatic_rights_for_buyer_qualified_tier():
    data=fixture()
    data["inventory"]["lead_origin_kind"]="contracted_partner_consumer_opt_in"
    data["inventory"]["individual_notice_and_opt_in_verified"]=False
    assert assess(**data)["state"]=="HOLD"


def test_missing_input_holds_and_naive_now_rejected():
    data=fixture()
    data["inventory"]=None
    assert assess(**data)["state"]=="HOLD"
    with pytest.raises(ValueError,match="timezone_aware_now_required"):
        review_exchange_lead_delivery_receipts(
            **fixture(),now=datetime(2026,10,20),
        )
