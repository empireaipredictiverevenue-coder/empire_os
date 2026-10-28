"""Bridge exact tenant-scoped order receipt to existing persisted terms parser.

All rows are isolated fixture-only; never claims buyer capacity or settlement.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
import pytest

from empire_os.canonical_buyer_acceptance_handoff import (
    review_same_order_buyer_acceptance,
)
from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold

NOW=datetime(2026,10,26,14,0,tzinfo=timezone.utc)
TENANT="00000000-0000-0000-0000-0000000000a1"
BUYER="00000000-0000-0000-0000-0000000000a2"
PROSPECT="00000000-0000-0000-0000-000000000001"
ENTITY="00000000-0000-0000-0000-000000000002"
OPPORTUNITY="00000000-0000-0000-0000-000000000003"
ORDER="00000000-0000-0000-0000-0000000000a4"
REVIEW="00000000-0000-0000-0000-0000000000a5"
APPROVAL="00000000-0000-0000-0000-0000000000a6"
ACCEPTANCE="00000000-0000-0000-0000-0000000000a7"

def inputs():
    context={"tenant_id":TENANT,"buyer_id":BUYER,"prospect_id":PROSPECT,
             "entity_id":ENTITY,"opportunity_id":OPPORTUNITY}
    sha="a"*64
    terms={"currency":"USD","settlement_asset":"USDT",
           "settlement_chain":"BSC","price_cents":12000}
    order={**context,"id":ORDER,"state":"accepted","price_cents":12000,
           "commercial_payload":{
               "commercial_terms_review_id":REVIEW,
               "commercial_terms_sha256":sha,"commercial_terms":terms,
               "terms_approved_by":"approved-reviewer",
               "terms_approved_at":"2026-10-26T10:00:00+00:00",
               "buyer_acceptance_kind":"signed_agreement",
               "buyer_acceptance_reference":"signed:fixture-buybox-1",
               "buyer_acceptance_recorded_by":"buyer-receipt-verifier",
               "buyer_accepted_at":"2026-10-26T11:00:00+00:00",
           }}
    review={**context,"id":REVIEW,"fulfilment_order_id":ORDER,
            "status":"approved","price_cents":12000,"terms":terms,
            "commercial_terms_sha256":sha,"decided_by":"approved-reviewer",
            "proposed_at":"2026-10-26T09:00:00+00:00",
            "decided_at":"2026-10-26T10:00:00+00:00"}
    events=[
      {**context,"id":APPROVAL,"event_type":"approved",
       "review_id":REVIEW,"fulfilment_order_id":ORDER,
       "actor":"approved-reviewer",
       "occurred_at":"2026-10-26T10:01:00+00:00",
       "payload":{"commercial_terms_sha256":sha}},
      {**context,"id":ACCEPTANCE,"event_type":"accepted",
       "review_id":REVIEW,"fulfilment_order_id":ORDER,
       "actor":"buyer-receipt-verifier",
       "occurred_at":"2026-10-26T11:01:00+00:00",
       "payload":{"evidence_kind":"signed_agreement",
                  "evidence_reference":"signed:fixture-buybox-1",
                  "commercial_terms_sha256":sha,
                  "accepted_at":"2026-10-26T11:00:00+00:00"}}
    ]
    lineage={**context,"schema_version":"empire.crm.scoped_lineage_review.v1",
             "mode":"OBSERVE","receipt_kind":"order","receipt_id":ORDER,
             "status":"INJECTED_SCOPED_RPC_TEST_ONLY","execution_authority":"NONE",
             "outbound_authorized":False,"database_writes":False,
             "buyer_terms_verified":False,"settlement_verified":False,
             "recognised_revenue_verified":False}
    return lineage,order,review,events

def test_valid_same_order_acceptance_evidence_reuses_original_materializer():
    args=inputs()
    result=review_same_order_buyer_acceptance(*args,as_of=NOW)
    assert result["original_persisted_terms_internal_coherence"] is True
    assert result["buyer_id"]==BUYER
    assert result["scoped_order_receipt_id"]==ORDER
    assert result["buyer_acceptance_event_id"]==ACCEPTANCE
    assert result["status"]=="INJECTED_ACCEPTANCE_COHERENCE_TEST_ONLY"
    for field in ("independent_buyer_capacity_verified_here",
                  "external_acceptance_source_independently_authenticated_here",
                  "delivery_verified","payment_verified",
                  "settlement_verified","realised_revenue_verified",
                  "outbound_authorized","fulfilment_authorized","database_writes"):
        assert result[field] is False

@pytest.mark.parametrize("mutate,reason",[
    (lambda l,o,r,e:l.update(receipt_kind="event"),"UNTRUSTED_SCOPED_ORDER_LINEAGE"),
    (lambda l,o,r,e:l.update(outbound_authorized=True),"UNTRUSTED_SCOPED_ORDER_LINEAGE"),
    (lambda l,o,r,e:l.update(buyer_id="00000000-0000-0000-0000-0000000000b2"),"EXACT_ORDER_IDENTITY_CONTINUITY_REQUIRED"),
    (lambda l,o,r,e:o.update(opportunity_id="00000000-0000-0000-0000-0000000000b3"),"EXACT_ORDER_IDENTITY_CONTINUITY_REQUIRED"),
    (lambda l,o,r,e:o.update(id="00000000-0000-0000-0000-0000000000b4"),"EXACT_ORDER_IDENTITY_CONTINUITY_REQUIRED"),
    (lambda l,o,r,e:r.update(status="pending"),"EXACT_APPROVED_TERMS_ORDER_REQUIRED"),
    (lambda l,o,r,e:r.update(price_cents=13000),"ORIGINAL_PERSISTED_TERMS_CONTRACT_FAILED"),
    (lambda l,o,r,e:o["commercial_payload"].update(buyer_acceptance_reference="unmatched"),"ORIGINAL_PERSISTED_TERMS_CONTRACT_FAILED"),
    (lambda l,o,r,e:e[1].update(actor="different"),"ORIGINAL_PERSISTED_TERMS_CONTRACT_FAILED"),
    (lambda l,o,r,e:e[1]["payload"].update(commercial_terms_sha256="b"*64),"ORIGINAL_PERSISTED_TERMS_CONTRACT_FAILED"),
    (lambda l,o,r,e:e.append(deepcopy(e[1])),"ORIGINAL_PERSISTED_TERMS_CONTRACT_FAILED"),
    (lambda l,o,r,e:o.update(state="offered"),"ORIGINAL_PERSISTED_TERMS_CONTRACT_FAILED"),
])
def test_mixed_identity_stale_terms_or_unsupported_receipt_never_promotes(mutate,reason):
    args=inputs()
    mutate(*args)
    with pytest.raises(ProspectHandoffHold,match=reason):
        review_same_order_buyer_acceptance(*args,as_of=NOW)

def test_existing_terms_approval_is_not_buyer_acceptance():
    lineage,order,review,events=inputs()
    order["state"]="offered"
    for key in ("buyer_acceptance_kind","buyer_acceptance_reference",
                "buyer_acceptance_recorded_by","buyer_accepted_at"):
        order["commercial_payload"].pop(key)
    events=events[:1]
    with pytest.raises(ProspectHandoffHold,match="CANONICAL_BUYER_ACCEPTANCE_NOT_RECORDED"):
        review_same_order_buyer_acceptance(
            lineage,order,review,events,as_of=NOW,
        )

def test_future_acceptance_or_forecast_evidence_fails_closed():
    args=inputs()
    args[3][1]["occurred_at"]="2026-11-01T00:00:00+00:00"
    with pytest.raises(ProspectHandoffHold,match="ORIGINAL_PERSISTED_TERMS_CONTRACT_FAILED"):
        review_same_order_buyer_acceptance(*args,as_of=NOW)
    args=inputs()
    args[3][1]["synthetic"]=True
    with pytest.raises(ProspectHandoffHold,match="ORIGINAL_PERSISTED_TERMS_CONTRACT_FAILED"):
        review_same_order_buyer_acceptance(*args,as_of=NOW)
