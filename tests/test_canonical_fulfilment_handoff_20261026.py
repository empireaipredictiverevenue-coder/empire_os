"""Exact accepted order → reported delivery/outcome continuity. Synthetic fixture only."""
from copy import deepcopy
from datetime import datetime, timezone
import pytest

from empire_os.canonical_buyer_acceptance_handoff import review_same_order_buyer_acceptance
from empire_os.canonical_fulfilment_handoff import review_accepted_order_delivery
from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from tests.test_canonical_buyer_acceptance_handoff_20261026 import (
    inputs, ORDER, TENANT, BUYER, ENTITY, PROSPECT, OPPORTUNITY, NOW,
)

OUTCOME="00000000-0000-0000-0000-0000000000a8"
OTHER="00000000-0000-0000-0000-0000000000b8"

def fixtures():
    l, order, review, events = inputs()
    accepted=review_same_order_buyer_acceptance(l,order,review,events,as_of=NOW)
    order.update(state="confirmed",delivered_at="2026-10-26T12:00:00+00:00",
                 confirmed_at="2026-10-26T12:30:00+00:00")
    outcome={
        "id":OUTCOME,"fulfilment_order_id":ORDER,
        "buyer_id":BUYER,"tenant_id":TENANT,"opportunity_id":OPPORTUNITY,
        "prospect_id":PROSPECT,"entity_id":ENTITY,
        "delivery_outcome":"confirmed","conversion_outcome":"unknown",
        "evidence_kind":"buyer_feedback",
        "evidence_reference":"buyer-feedback:fixture-001",
        "actor":"original-outcome-recorder",
        "idempotency_key":"outcome:fixture:0001",
        "evidence":{"buyer_id":BUYER,"fulfilment_order_id":ORDER},
        "recorded_at":"2026-10-26T13:00:00+00:00",
    }
    return accepted,order,[outcome]

def review(*args):
    return review_accepted_order_delivery(*args,as_of=NOW)

def test_exact_original_acceptance_to_same_order_outcome_coherence():
    v=review(*fixtures())
    assert v["delivery_record_coherence_verified"] is True
    assert v["reported_delivery_state"]=="confirmed"
    assert v["delivery_outcome_id"]==OUTCOME
    assert v["fulfilment_order_id"]==ORDER
    assert v["buyer_id"]==BUYER
    assert v["buyer_acceptance_event_id"]
    assert v["status"]=="INJECTED_DELIVERY_COHERENCE_TEST_ONLY"
    assert v["next_original_owner"]=="FulfilmentOperations"
    assert v["next_original_action"]=="VERIFY_INDEPENDENT_BUYER_CONFIRMATION_AND_DELIVERY_PROVIDER"
    for k in ("provider_delivery_independently_verified_here",
              "buyer_confirmation_independently_verified_here",
              "buyer_capacity_independently_verified_here",
              "settlement_verified","revenue_verified",
              "economic_memory_authorized","outbound_authorized",
              "fulfilment_authorized","database_writes"):
        assert v[k] is False

def test_delivered_without_confirmed_preserves_buyer_confirmation_hold():
    a,o,out=fixtures()
    o.update(state="delivered",confirmed_at=None)
    out[0]["delivery_outcome"]="delivered"
    v=review(a,o,out)
    assert v["reported_delivery_state"]=="delivered"
    assert v["buyer_confirmation_recorded_at"] is None
    assert v["next_original_action"]=="VERIFY_INDEPENDENT_DELIVERY_PROVIDER_AND_BUYER_RECEIPT"
    assert v["buyer_confirmation_independently_verified_here"] is False

@pytest.mark.parametrize("mutation,error",[
    (lambda a,o,x:a.update(schema_version="invented"),"UNTRUSTED_BUYER_ACCEPTANCE_HANDOFF"),
    (lambda a,o,x:a.update(outbound_authorized=True),"UNTRUSTED_BUYER_ACCEPTANCE_HANDOFF"),
    (lambda a,o,x:a.update(buyer_acceptance_event_id=None),"EXACT_ORIGINAL_ACCEPTANCE_EVENT_REQUIRED"),
    (lambda a,o,x:o.update(id=OTHER),"ACCEPTANCE_AND_FULFILMENT_IDENTITY_MISMATCH"),
    (lambda a,o,x:o.update(buyer_id=OTHER),"ACCEPTANCE_AND_FULFILMENT_IDENTITY_MISMATCH"),
    (lambda a,o,x:o.update(opportunity_id=OTHER),"ACCEPTANCE_AND_FULFILMENT_IDENTITY_MISMATCH"),
    (lambda a,o,x:o.update(state="accepted"),"ORDER_NOT_DELIVERED"),
    (lambda a,o,x:o.update(delivered_at="2026-10-26T10:00:00+00:00"),"DELIVERY_PRECEDES_BUYER_ACCEPTANCE"),
    (lambda a,o,x:o.update(confirmed_at="2026-10-26T11:30:00+00:00"),"CONFIRMATION_PRECEDES_DELIVERY"),
    (lambda a,o,x:o.update(delivered_at="2026-11-01T12:00:00+00:00"),"FUTURE_DELIVERY_EVIDENCE_HOLD"),
    (lambda a,o,x:x[0].update(fulfilment_order_id=OTHER),"MIXED_OUTCOME_ORDER_IDENTITIES"),
    (lambda a,o,x:x[0].update(tenant_id=OTHER),"MIXED_OUTCOME_TENANT_OR_BUYER_IDENTITY"),
    (lambda a,o,x:x[0].update(buyer_id=OTHER),"MIXED_OUTCOME_TENANT_OR_BUYER_IDENTITY"),
    (lambda a,o,x:x[0].update(id="arbitrary"),"EXACT_CANONICAL_OUTCOME_UUID_REQUIRED"),
    (lambda a,o,x:x[0].update(delivery_outcome="failed"),"ACTUAL_DELIVERY_EVIDENCE_NOT_ESTABLISHED"),
    (lambda a,o,x:x[0].update(evidence_kind="model"),"ACTUAL_DELIVERY_EVIDENCE_NOT_ESTABLISHED"),
    (lambda a,o,x:x[0].update(evidence_reference=""),"ACTUAL_DELIVERY_EVIDENCE_NOT_ESTABLISHED"),
    (lambda a,o,x:x[0].update(idempotency_key=""),"ACTUAL_DELIVERY_EVIDENCE_NOT_ESTABLISHED"),
    (lambda a,o,x:x[0].update(recorded_at="2026-10-26T11:00:00+00:00"),"OUTCOME_PREDATES_DELIVERY"),
    (lambda a,o,x:x[0].update(recorded_at="2026-10-26T12:15:00+00:00"),"CANONICAL_BUYER_CONFIRMATION_TIME_REQUIRED"),
    (lambda a,o,x:x[0]["evidence"].update(synthetic=True),"UNTRUSTED_DELIVERY_OUTCOME"),
    (lambda a,o,x:x[0]["evidence"].update(buyer_id=OTHER),"DELIVERY_EVIDENCE_IDENTITY_CONFLICT"),
])
def test_unsafe_or_mismatched_handoff_fails_closed(mutation,error):
    args=fixtures()
    mutation(*args)
    with pytest.raises(ProspectHandoffHold,match=error):
        review(*args)

def test_latest_rejection_cannot_be_hidden_by_earlier_success():
    a,o,rows=fixtures()
    rejected=deepcopy(rows[0])
    rejected.update(id=OTHER,recorded_at="2026-10-26T13:10:00+00:00",
                    delivery_outcome="rejected")
    with pytest.raises(ProspectHandoffHold,match="ACTUAL_DELIVERY_EVIDENCE_NOT_ESTABLISHED"):
        review(a,o,[rows[0],rejected])

def test_duplicate_outcome_receipt_is_not_multiple_confirmations():
    a,o,rows=fixtures()
    with pytest.raises(ProspectHandoffHold,match="DUPLICATE_CANONICAL_OUTCOME"):
        review(a,o,[rows[0],deepcopy(rows[0])])

def test_confirmed_order_without_outcome_receipt_is_held():
    a,o,rows=fixtures()
    with pytest.raises(ProspectHandoffHold,match="BOUNDED_EXACT_DELIVERY_OUTCOMES_REQUIRED"):
        review(a,o,[])


def test_same_timestamp_disagreeing_delivery_outcomes_cannot_select_winner():
    a,o,rows=fixtures()
    second=deepcopy(rows[0])
    second.update(id=OTHER,delivery_outcome="failed")
    with pytest.raises(ProspectHandoffHold,match="AMBIGUOUS_LATEST_DELIVERY_OUTCOME_CLOCK"):
        review(a,o,[rows[0],second])
