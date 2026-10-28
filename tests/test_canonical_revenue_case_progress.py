"""V11 original EmpireOS V7-V10 exact-order offline integration tests.

Every positive handoff starts from the existing V7/V8/V9/V10 repo fixtures.
Changing injected fixture labels to tenant-scoped statuses is only a test:
it does NOT certify a real signed tenant session or independent financial proof.
"""
from copy import deepcopy
import pytest

from empire_os.canonical_revenue_case_progress import (
    SCHEMA, review_one_canonical_revenue_case,
)
from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from empire_os.canonical_settlement_handoff import review_fulfilment_payment_settlement
from tests.test_canonical_fulfilment_handoff_20261026 import fixtures, NOW
from tests.test_canonical_settlement_handoff_20261026 import inputs, run
from tests import test_canonical_economic_memory_handoff_20261026 as v10

OTHER = "00000000-0000-0000-0000-0000000000e1"


def original_receipts(monkeypatch, *, mode="direct", with_revenue=True):
    accepted, order, outcome = fixtures()
    delivered, other_order, request, payment, extra = inputs(
        mode, with_revenue=with_revenue,
    )
    assert order["id"] == other_order["id"]
    assert accepted["buyer_acceptance_event_id"] == delivered["buyer_acceptance_event_id"]
    accepted["status"] = "SIGNED_TENANT_SCOPED_ACCEPTANCE_COHERENCE_REVIEW_ONLY"
    delivered["status"] = "TENANT_SCOPED_DELIVERY_COHERENCE_REVIEW_ONLY"
    settlement = review_fulfilment_payment_settlement(
        delivered, other_order, request, payment, as_of=NOW, **extra,
    )
    memory = None
    if with_revenue:
        financial, feedback, repo, preview_calls = v10.setup(monkeypatch, mode=mode)
        assert financial["commercial_outcome_ref"] == settlement["commercial_outcome_ref"]
        memory = v10.review(financial, repo)
        assert len(preview_calls) == 1
    receipts = dict(
        tenant_id=accepted["tenant_id"],
        fulfilment_order_id=accepted["fulfilment_order_id"],
        buyer_acceptance=accepted,
        delivery=delivered,
        settlement=settlement,
        economic_memory=memory,
    )
    return receipts


def result(**kwargs):
    return review_one_canonical_revenue_case(**kwargs)


def test_unobserved_case_is_read_only_and_requests_original_acceptance():
    _, order, _ = fixtures()
    report = result(tenant_id=order["tenant_id"], fulfilment_order_id=order["id"])
    assert report["schema_version"] == SCHEMA
    assert report["next_missing_stage"] == "BUYER_ACCEPTANCE"
    assert len(report["independent_evidence_requirements"]) == 6
    assert all(x["status"] == "NOT_ATTESTED_BY_THIS_REVIEW"
               for x in report["independent_evidence_requirements"])
    assert all(x["status"] == "NOT_OBSERVED" for x in report["source_handoff_stages"])
    for key in ("revenue_authorized", "revenue_recognized_here",
                "economic_memory_persisted", "eligible_for_learning",
                "model_training_authorized", "queue_mutated", "outbound_sent",
                "payments_executed", "database_writes"):
        assert report[key] is False


@pytest.mark.parametrize("mode", ("direct", "escrow"))
def test_exact_source_continuity_reaches_unattested_external_proof(monkeypatch, mode):
    receipts = original_receipts(monkeypatch, mode=mode)
    report = result(**receipts)
    assert report["next_missing_stage"] == "INDEPENDENT_EVIDENCE"
    assert report["source_reported_recognizer_event"] is True
    assert report["source_reported_shadow_memory"] is True
    assert report["next_original_owner"] == "RevenueRecognition"
    assert all(row["status"] == "SOURCE_REPORTED_COHERENCE_ONLY"
               for row in report["source_handoff_stages"])
    assert not report["payment_and_chain_finality_independently_verified_here"]
    assert not report["refund_and_dispute_census_complete_here"]
    assert report["revenue_recognized_here"] is False
    assert report["eligible_for_learning"] is False


def test_stage_progress_from_actual_original_handoffs(monkeypatch):
    all_receipts = original_receipts(monkeypatch)
    first = dict(all_receipts, buyer_acceptance=None, delivery=None,
                 settlement=None, economic_memory=None)
    for observed, expected in (
        ((), "BUYER_ACCEPTANCE"),
        (("buyer_acceptance",), "FULFILMENT"),
        (("buyer_acceptance", "delivery"), "SETTLEMENT_LEDGER"),
        (("buyer_acceptance", "delivery", "settlement"), "ECONOMIC_MEMORY_SHADOW"),
    ):
        kwargs = dict(first)
        for name in observed:
            kwargs[name] = all_receipts[name]
        report = result(**kwargs)
        assert report["next_missing_stage"] == expected
        assert report["revenue_authorized"] is False


def test_without_revenue_event_reports_recognizer_not_shadow(monkeypatch):
    receipts = original_receipts(monkeypatch, with_revenue=False)
    report = result(**receipts)
    assert report["next_missing_stage"] == "RECOGNIZER_EVENT"
    assert report["source_reported_recognizer_event"] is False


@pytest.mark.parametrize("missing", ("buyer_acceptance", "delivery", "settlement"))
def test_missing_parent_blocks_later_handoff(monkeypatch, missing):
    receipts = original_receipts(monkeypatch)
    receipts[missing] = None
    with pytest.raises(ProspectHandoffHold, match="DEPENDENT_REVENUE_HANDOFF_WITHOUT_PARENT"):
        result(**receipts)


@pytest.mark.parametrize("stage,field", [
    ("buyer_acceptance", "buyer_id"),
    ("delivery", "opportunity_id"),
    ("settlement", "prospect_id"),
    ("economic_memory", "entity_id"),
])
def test_exact_original_identity_mismatch_holds(monkeypatch, stage, field):
    receipts = original_receipts(monkeypatch)
    receipts[stage][field] = OTHER
    with pytest.raises(ProspectHandoffHold, match="CROSS_RECEIPT_ORIGINAL_COMMERCIAL_IDENTITY_MISMATCH"):
        result(**receipts)


@pytest.mark.parametrize("stage", ("buyer_acceptance", "delivery", "settlement", "economic_memory"))
def test_injected_status_cannot_be_presented_as_scoped_receipt(monkeypatch, stage):
    receipts = original_receipts(monkeypatch)
    receipts[stage]["status"] = "INJECTED_FIXTURE_ONLY"
    with pytest.raises(ProspectHandoffHold, match="INVALID_OR_UNTRUSTED_"):
        result(**receipts)


@pytest.mark.parametrize("stage", ("buyer_acceptance", "delivery", "settlement", "economic_memory"))
def test_source_claims_must_remain_observe(monkeypatch, stage):
    receipts = original_receipts(monkeypatch)
    receipts[stage]["database_writes"] = True
    with pytest.raises(ProspectHandoffHold, match="INVALID_OR_UNTRUSTED_"):
        result(**receipts)


def test_crossed_acceptance_event_is_rejected(monkeypatch):
    receipts = original_receipts(monkeypatch)
    receipts["delivery"]["buyer_acceptance_event_id"] = OTHER
    with pytest.raises(ProspectHandoffHold, match="UNTRUSTED_OR_CROSS_ACCEPTANCE_DELIVERY"):
        result(**receipts)


def test_other_commercial_outcome_fails(monkeypatch):
    receipts = original_receipts(monkeypatch)
    receipts["settlement"]["commercial_outcome_ref"] = "canonical:commercial_outcomes:" + OTHER
    with pytest.raises(ProspectHandoffHold, match="UNTRUSTED_OR_CROSS_DELIVERY_SETTLEMENT"):
        result(**receipts)


def test_other_payment_proof_fails(monkeypatch):
    receipts = original_receipts(monkeypatch)
    receipts["economic_memory"]["original_payment_evidence_ref"] = "canonical:bsc_payment_evidence:" + OTHER
    with pytest.raises(ProspectHandoffHold, match="UNTRUSTED_OR_UNRECONCILED_ECONOMIC_MEMORY_PREVIEW"):
        result(**receipts)


def test_same_total_other_actual_cost_receipt_does_not_pass(monkeypatch):
    receipts = original_receipts(monkeypatch)
    receipts["economic_memory"]["original_actual_cost_evidence_refs"][0] = (
        "canonical:commercial_evidence_registry:other-invoice"
    )
    with pytest.raises(ProspectHandoffHold, match="UNTRUSTED_OR_UNRECONCILED_ECONOMIC_MEMORY_PREVIEW"):
        result(**receipts)


@pytest.mark.parametrize("field,value", [
    ("approved_price_cents", True),
    ("reported_recognized_cost_cents", 10000.0),
    ("reported_recognized_margin_cents", -1),
])
def test_invalid_economics_does_not_claim_recognition(monkeypatch, field, value):
    receipts = original_receipts(monkeypatch)
    receipts["settlement"][field] = value
    with pytest.raises(ProspectHandoffHold, match="UNRECONCILED_ORIGINAL_RECOGNIZER_EVENT"):
        result(**receipts)


@pytest.mark.parametrize("field", ("economic_memory_persisted", "eligible_for_learning",
                                    "model_training_authorized"))
def test_false_learning_claim_must_not_be_promoted(monkeypatch, field):
    receipts = original_receipts(monkeypatch)
    receipts["economic_memory"][field] = True
    with pytest.raises(ProspectHandoffHold, match="UNTRUSTED_OR_UNRECONCILED_ECONOMIC_MEMORY_PREVIEW"):
        result(**receipts)


def test_stable_per_order_id_without_artifact_persistence(monkeypatch):
    receipts = original_receipts(monkeypatch)
    x, y = result(**receipts), result(**deepcopy(receipts))
    assert x["case_id"] == y["case_id"]
    assert x["queue_mutated"] is False
    assert x["database_writes"] is False
