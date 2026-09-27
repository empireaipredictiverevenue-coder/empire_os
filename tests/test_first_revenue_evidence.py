from empire_os.first_revenue_evidence import (
    compile_first_revenue_evidence,
)
from empire_os.first_revenue_proof import (
    assess_first_revenue_readiness,
)


def full_chain():
    return {
        "buyer": {
            "buyer_id": "buyer-1",
            "identity_verified_at": "2026-09-19T18:00:00+00:00",
            "commercial_terms_verified_at": "2026-09-19T18:05:00+00:00",
        },
        "outbound_intent": {
            "intent_id": "intent-1",
            "status": "approved",
            "approved_by": "operator-1",
            "approved_at": "2026-09-19T18:10:00+00:00",
        },
        "provider_events": [
            {
                "event_id": "event-sent",
                "event_type": "sent",
                "provider_verified": True,
            },
            {
                "event_id": "event-delivered",
                "event_type": "delivered",
                "signature_verified": True,
            },
        ],
        "agreement": {
            "agreement_id": "agreement-1",
            "status": "signed",
            "signed_at": "2026-09-19T18:20:00+00:00",
        },
        "payment": {
            "payment_id": "payment-1",
            "status": "verified",
            "chain": "bsc",
            "asset": "USDT",
            "verified_at": "2026-09-19T18:30:00+00:00",
        },
        "fulfilment": {
            "fulfilment_order_id": "order-1",
            "state": "delivered",
            "delivered_at": "2026-09-19T18:40:00+00:00",
        },
        "outcome": {
            "outcome_id": "outcome-1",
            "recorded_at": "2026-09-19T18:50:00+00:00",
        },
        "revenue_event": {
            "event_id": "revenue-1",
            "event_type": "revenue_recognized",
            "actual_revenue": True,
            "amount_cents": 25000,
        },
    }


def test_full_canonical_chain_proves_first_revenue():
    evidence = compile_first_revenue_evidence(**full_chain())
    readiness = assess_first_revenue_readiness(evidence)
    assert readiness.first_revenue_proven is True
    assert readiness.blockers == ()
    assert evidence.usdt_bsc_payment_verified is True
    assert evidence.revenue_recognized is True
    assert "payment:payment-1" in evidence.evidence_refs


def test_unverified_provider_events_do_not_count():
    chain = full_chain()
    chain["provider_events"] = [
        {
            "event_id": "event-1",
            "event_type": "delivered",
            "provider_verified": False,
            "signature_verified": False,
        }
    ]
    evidence = compile_first_revenue_evidence(**chain)
    assert evidence.send_evidence_verified is False
    assert evidence.delivery_evidence_verified is False


def test_wrong_chain_or_asset_does_not_verify_payment():
    chain = full_chain()
    chain["payment"] = {
        "payment_id": "payment-1",
        "status": "verified",
        "chain": "solana",
        "asset": "USDC",
        "verified_at": "2026-09-19T18:30:00+00:00",
    }
    evidence = compile_first_revenue_evidence(**chain)
    readiness = assess_first_revenue_readiness(evidence)
    assert evidence.usdt_bsc_payment_verified is False
    assert "usdt_bsc_payment_not_verified" in readiness.blockers


def test_actual_revenue_false_never_counts():
    chain = full_chain()
    chain["revenue_event"]["actual_revenue"] = False
    evidence = compile_first_revenue_evidence(**chain)
    readiness = assess_first_revenue_readiness(evidence)
    assert evidence.revenue_recognized is False
    assert readiness.first_revenue_proven is False
    assert "revenue_not_recognized" in readiness.blockers


def test_missing_records_stay_unknown_false():
    evidence = compile_first_revenue_evidence()
    readiness = assess_first_revenue_readiness(evidence)
    assert evidence.buyer_identity_verified is False
    assert evidence.outbound_intent_approved is False
    assert evidence.usdt_bsc_payment_verified is False
    assert readiness.first_revenue_proven is False
    assert evidence.evidence_refs == ("evidence:none",)


def test_approved_status_without_approval_evidence_is_not_approved():
    chain = full_chain()
    chain["outbound_intent"] = {
        "intent_id": "intent-1",
        "status": "approved",
    }
    evidence = compile_first_revenue_evidence(**chain)
    assert evidence.human_approval_recorded is False
    assert evidence.outbound_intent_approved is False


def test_outcome_requires_record_identity_and_observed_evidence():
    chain = full_chain()
    chain["outcome"] = {"outcome_id": "outcome-1"}
    evidence = compile_first_revenue_evidence(**chain)
    assert evidence.outcome_evidence_verified is False
