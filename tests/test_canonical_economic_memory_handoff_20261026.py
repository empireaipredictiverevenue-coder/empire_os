"""V10 contract tests: owner-read-only feedback -> shadow Economic Memory."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from empire_os.canonical_economic_memory_handoff import (
    review_original_economic_memory_handoff,
)
from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
from tests.test_canonical_settlement_handoff_20261026 import (
    NOW, inputs, run, REVENUE, OTHER,
)

EVENT_REF = "canonical:commercial_events:" + REVENUE


class FakeGateway:
    def __init__(self, backend="empiredb"):
        self.backend = backend

    def snapshot(self):
        return SimpleNamespace(as_dict=lambda: {"primary_backend": self.backend})


def owner_feedback(financial):
    outcome = financial["commercial_outcome_ref"]
    proof = ("canonical:" + (
        "bsc_payment_evidence" if
        financial["settlement_source_reported"] == "direct_payment"
        else "bsc_escrow_evidence") + ":" +
        financial["settlement_evidence_id"])
    evidence = [outcome, EVENT_REF, proof]
    verified = dict(
        payment_verified=True, fulfilment_verified=True,
        recognized_revenue=True, actual_revenue_cents=12000,
        actual_cost_cents=7000, gross_profit_cents=5000,
        available_at="2026-10-26T13:50:00+00:00",
        outcome_recorded_at="2026-10-26T13:00:00+00:00",
    )
    packet = dict(
        tenant_id=financial["tenant_id"],
        entity_id=financial["entity_id"],
        label=dict(available=True, value=1, synthetic=False,
                   forecast_derived=False, outcome_ref=outcome,
                   evidence_refs=evidence),
        verification=verified,
        learning_lineage=dict(
            tenant_id=financial["tenant_id"], outcome_ref=outcome,
            opportunity_key=None, prediction_ref=None,
            decision_ref=None, execution_ref=None,
        ),
    )
    return dict(
        schema_version="empire.verified_outcome_feedback.v1",
        tenant_id=financial["tenant_id"],
        buyer_id=financial["buyer_id"],
        prospect_id=financial["prospect_id"],
        entity_id=financial["entity_id"],
        fulfilment_order_id=financial["fulfilment_order_id"],
        outcome_ref=outcome, conversion_outcome="won",
        verified_label=1, verified_outcome=True, synthetic=False,
        actual_revenue=True, actual_revenue_cents=12000,
        actual_cost_cents=7000, gross_profit_cents=5000,
        evidence_refs=evidence, cortex_packet=packet,
        available_at=verified["available_at"],
        outcome_recorded_at=verified["outcome_recorded_at"],
        causal_lineage=None, opportunity_key=None, prediction_ref=None,
        decision_ref=None, execution_ref=None, shadow_only=True,
        execution_authority="none",
    )


def setup(monkeypatch, *, mode="direct"):
    financial = run(inputs(mode))
    financial["status"] = "TENANT_SCOPED_FINANCIAL_LINEAGE_REVIEW_ONLY"
    feedback = owner_feedback(financial)
    repo = object.__new__(ExecutionBusDataRepository)
    repo._gateway = FakeGateway()

    def read(order_id, *, tenant_id, repo_root, as_of):
        assert order_id == financial["fulfilment_order_id"]
        assert tenant_id == financial["tenant_id"]
        assert as_of == NOW
        return deepcopy(feedback)

    repo.verified_outcome_feedback = read
    preview_calls = []

    def preview(**kwargs):
        preview_calls.append(kwargs)
        return dict(schema_version="empire.economic_memory.v1",
                    mode="OBSERVE", execution_authority="none",
                    accounting_authority="none",
                    commercial_authority="none",
                    promoted_learning=False,
                    model_weight_mutation_authorized=False,
                    outcome_memory_candidate_count=1,
                    outcome_conditioned_memory_count=1)

    monkeypatch.setattr(
        "empire_os.canonical_economic_memory_handoff.build_economic_memory_snapshot",
        preview,
    )
    return financial, feedback, repo, preview_calls


def review(financial, repo):
    return review_original_economic_memory_handoff(
        financial, repository=repo, tenant_id=financial["tenant_id"],
        repo_root="/srv/empire_os", as_of=NOW,
    )


@pytest.mark.parametrize("mode", ("direct", "escrow"))
def test_original_owner_shadow_handoff_never_authenticates_cash_or_writes(
    monkeypatch, mode
):
    financial, feedback, repo, calls = setup(monkeypatch, mode=mode)
    report = review(financial, repo)
    assert report["original_owner_feedback_consistent"] is True
    assert report["original_economic_memory_preview_candidate_count"] == 1
    assert report["original_economic_memory_preview_retrievable_count"] == 1
    assert report["original_revenue_event_ref"] == EVENT_REF
    assert report["reported_gross_profit_cents"] == 5000
    assert calls[0]["tenant_id"] == financial["tenant_id"]
    assert calls[0]["verified_feedback"][0]["outcome_ref"] == feedback["outcome_ref"]
    assert calls[0]["calibration_reviews"] == []
    assert calls[0]["department_work"] == []
    for key in ("original_feedback_independent_financial_attestation",
                "complete_reversal_census_verified_here",
                "bsc_finality_independently_verified_here",
                "buyer_funds_independently_verified_here",
                "economic_memory_persisted", "model_training_authorized",
                "payments_executed", "outbound_authorized", "database_writes"):
        assert report[key] is False


def test_injected_v9_receipt_never_becomes_real_memory(monkeypatch):
    financial, _, repo, calls = setup(monkeypatch)
    financial["status"] = "INJECTED_FINANCIAL_LINEAGE_COHERENCE_ONLY"
    with pytest.raises(ProspectHandoffHold, match="UNTRUSTED_OR_UNRECOGNIZED"):
        review(financial, repo)
    assert calls == []


@pytest.mark.parametrize("mutation,error", [
    (lambda f,b,r: f.update(tenant_id=OTHER), "ORIGINAL_VERIFIED_OUTCOME_READ_HELD"),
    (lambda f,b,r: f.update(revenue_event_consistent=False), "UNTRUSTED_OR_UNRECOGNIZED"),
    (lambda f,b,r: f.update(economic_memory_authorized=True), "UNTRUSTED_OR_UNRECOGNIZED"),
    (lambda f,b,r: f.update(outbound_authorized=True), "UNTRUSTED_OR_UNRECOGNIZED"),
    (lambda f,b,r: f.update(approved_price_cents=12001), "UNRECONCILED_ORIGINAL"),
    (lambda f,b,r: b.update(fulfilment_order_id=OTHER), "CROSS_ORDER"),
    (lambda f,b,r: b.update(buyer_id=OTHER), "CROSS_ORDER"),
    (lambda f,b,r: b.update(outcome_ref="canonical:commercial_outcomes:" + OTHER), "ORIGINAL_VERIFIED_OUTCOME_READ_HELD"),
    (lambda f,b,r: b["evidence_refs"].remove(EVENT_REF), "ORIGINAL_OUTCOME_REVENUE_EVENT"),
    (lambda f,b,r: b["evidence_refs"].remove(
        "canonical:bsc_payment_evidence:" + f["settlement_evidence_id"]
    ), "ORIGINAL_PAYMENT_PROOF"),
    (lambda f,b,r: b.update(gross_profit_cents=4999), "ORIGINAL_VERIFIED_OUTCOME_READ_HELD"),
    (lambda f,b,r: b.update(actual_cost_cents=7200), "ORIGINAL_VERIFIED_OUTCOME_READ_HELD"),
    (lambda f,b,r: b.update(actual_revenue_cents=12001), "ORIGINAL_VERIFIED_OUTCOME_READ_HELD"),
    (lambda f,b,r: b.update(conversion_outcome="lost"), "ORIGINAL_VERIFIED_OUTCOME_READ_HELD"),
    (lambda f,b,r: setattr(r, "_gateway", FakeGateway("supabase")), "CANONICAL_EMPIREDB"),
])
def test_rejects_cross_order_false_profit_missing_payment_or_spoofed_owner(
    monkeypatch, mutation, error
):
    financial, feedback, repo, calls = setup(monkeypatch)
    mutation(financial, feedback, repo)
    repo.verified_outcome_feedback = lambda *args, **kwargs: feedback
    with pytest.raises(ProspectHandoffHold, match=error):
        review(financial, repo)
    assert calls == []


def test_missing_owner_repository_or_unrecognized_original_event(monkeypatch):
    financial, feedback, repo, calls = setup(monkeypatch)
    with pytest.raises(ProspectHandoffHold, match="ORIGINAL_CANONICAL_OUTCOME_READER"):
        review_original_economic_memory_handoff(
            financial, repository=object(), tenant_id=financial["tenant_id"],
            repo_root="/srv/empire_os", as_of=NOW,
        )
    financial["recognized_revenue_event_ref"] = (
        "canonical:commercial_events:" + OTHER)
    with pytest.raises(ProspectHandoffHold, match="ORIGINAL_OUTCOME_REVENUE_EVENT"):
        review(financial, repo)
    assert calls == []
