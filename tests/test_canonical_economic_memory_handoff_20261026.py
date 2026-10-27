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
# Reuse the ORIGINAL queue/worker fixture (real persisted DONE receipt and
# selection identity), not a fabricated "completed" decision.
from tests.test_runtime_causal_lineage_continuity import completed

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
    evidence = [outcome, EVENT_REF, proof,
                *financial["reported_actual_cost_evidence_refs"]]
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
    assert report["original_actual_cost_evidence_refs"] == financial[
        "reported_actual_cost_evidence_refs"]
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


def test_actual_existing_memory_builder_accepts_only_shadow_candidate(monkeypatch):
    from empire_os.economic_memory import (
        build_economic_memory_snapshot as original_builder,
    )
    import empire_os.canonical_economic_memory_handoff as handoff

    financial, feedback, repo, _ = setup(monkeypatch)
    monkeypatch.setattr(handoff, "build_economic_memory_snapshot", original_builder)
    report = review(financial, repo)
    assert report["original_economic_memory_preview_candidate_count"] == 1
    assert report["original_economic_memory_preview_retrievable_count"] == 1
    assert report["economic_memory_persisted"] is False
    assert report["original_feedback_independent_financial_attestation"] is False
    assert report["model_training_authorized"] is False



def test_v10_rejects_profitable_feedback_with_wrong_cost_receipt(monkeypatch):
    # Both financial packets can be internally consistent; their actual
    # costs and margin must ALSO agree across the original-source boundary.
    financial, feedback, repo, calls = setup(monkeypatch)
    assert financial["reported_recognized_cost_cents"] == 7000
    assert financial["reported_recognized_margin_cents"] == 5000
    feedback["actual_cost_cents"] = 6000
    feedback["gross_profit_cents"] = 6000
    feedback["cortex_packet"]["verification"]["actual_cost_cents"] = 6000
    feedback["cortex_packet"]["verification"]["gross_profit_cents"] = 6000
    repo.verified_outcome_feedback = lambda *args, **kwargs: feedback
    with pytest.raises(ProspectHandoffHold, match="UNRECONCILED_ORIGINAL_RECOGNIZED_ECONOMICS"):
        review(financial, repo)
    assert calls == []


def _attach_original_completed_work(monkeypatch, financial, feedback, repo, work):
    """Use a real queue-generated fixture, never fabricate decision identities."""
    from empire_os.decision_identity import causal_lineage_from_work
    from tests.test_runtime_causal_lineage_continuity import KEY
    work = deepcopy(work)
    work["tenant_id"] = financial["tenant_id"]
    provenance = work["commercial_decision_provenance"]
    provenance["tenant_id"] = financial["tenant_id"]
    provenance["opportunity_id"] = financial["opportunity_id"]
    causal = causal_lineage_from_work(
        work, tenant_id=financial["tenant_id"], opportunity_key=KEY,
        opportunity_id=financial["opportunity_id"],
    )
    feedback["causal_lineage"] = deepcopy(causal)
    for key in ("opportunity_key", "prediction_ref", "decision_ref", "execution_ref"):
        feedback[key] = causal[key]
    learning = feedback["cortex_packet"]["learning_lineage"]
    learning.update(
        {key: causal[key] for key in
         ("opportunity_key", "prediction_ref", "decision_ref", "execution_ref")}
    )
    learning["causal_lineage"] = deepcopy(causal)
    repo.verified_outcome_feedback = lambda *args, **kwargs: deepcopy(feedback)
    monkeypatch.setattr(
        "empire_os.canonical_economic_memory_handoff.DepartmentWorkQueue.read_completed_work",
        staticmethod(lambda repo_root, work_id: deepcopy(work)),
    )
    return work, causal


def test_original_completed_work_creates_shadow_causal_attribution_without_authority(
    monkeypatch, completed,
):
    from empire_os.economic_memory import (
        build_economic_memory_snapshot as original_builder,
    )
    import empire_os.canonical_economic_memory_handoff as handoff

    financial, feedback, repo, _ = setup(monkeypatch)
    original, causal = _attach_original_completed_work(
        monkeypatch, financial, feedback, repo, completed,
    )
    monkeypatch.setattr(
        handoff, "build_economic_memory_snapshot", original_builder,
    )
    report = review(financial, repo)
    assert report["original_completed_work_lineage_consistent"] is True
    assert report["original_shadow_causal_attribution_count"] == 1
    assert report["original_shadow_decision_attribution_count"] == 1
    assert report["causal_learning_eligibility_independently_verified_here"] is False
    assert report["eligible_for_learning"] is False
    assert report["economic_memory_persisted"] is False
    assert causal["execution_ref"] == "department_work:" + original["id"]


def test_missing_canonical_completed_work_holds_before_memory_preview(
    monkeypatch, completed,
):
    from empire_os.department_work_queue import DepartmentWorkQueueError

    financial, feedback, repo, calls = setup(monkeypatch)
    _attach_original_completed_work(
        monkeypatch, financial, feedback, repo, completed,
    )
    monkeypatch.setattr(
        "empire_os.canonical_economic_memory_handoff.DepartmentWorkQueue.read_completed_work",
        staticmethod(lambda *args: (_ for _ in ()).throw(
            DepartmentWorkQueueError("completed work missing"),
        )),
    )
    with pytest.raises(ProspectHandoffHold, match="ORIGINAL_COMPLETED_CAUSAL_WORK_HELD"):
        review(financial, repo)
    assert calls == []


def test_wrong_work_scope_holds_before_memory_preview(monkeypatch, completed):
    financial, feedback, repo, calls = setup(monkeypatch)
    work, _ = _attach_original_completed_work(
        monkeypatch, financial, feedback, repo, completed,
    )
    work["tenant_id"] = OTHER
    monkeypatch.setattr(
        "empire_os.canonical_economic_memory_handoff.DepartmentWorkQueue.read_completed_work",
        staticmethod(lambda *args: deepcopy(work)),
    )
    with pytest.raises(ProspectHandoffHold, match="ORIGINAL_COMPLETED_CAUSAL_WORK_HELD"):
        review(financial, repo)
    assert calls == []


def test_unattributed_shadow_outcome_must_not_claim_causal_credit(monkeypatch):
    financial, _, repo, calls = setup(monkeypatch)
    report = review(financial, repo)
    assert report["original_completed_work_lineage_consistent"] is False
    assert report["original_shadow_causal_attribution_count"] == 0
    assert report["original_shadow_decision_attribution_count"] == 0
    assert report["eligible_for_learning"] is False
    assert calls[0]["department_work"] == []


def test_injected_causal_attribution_in_preview_rejected(monkeypatch):
    financial, _, repo, calls = setup(monkeypatch)
    def bad_preview(**kwargs):
        return dict(schema_version="empire.economic_memory.v1", mode="OBSERVE",
                    execution_authority="none", accounting_authority="none",
                    commercial_authority="none", promoted_learning=False,
                    model_weight_mutation_authorized=False,
                    plan_outcome_attribution_count=1,
                    decision_outcome_attribution_count=1)
    monkeypatch.setattr(
        "empire_os.canonical_economic_memory_handoff.build_economic_memory_snapshot",
        bad_preview,
    )
    with pytest.raises(ProspectHandoffHold, match="ORIGINAL_CAUSAL_ATTRIBUTION_PREVIEW_MISMATCH"):
        review(financial, repo)


def test_preview_causal_attribution_must_name_exact_original_work(
    monkeypatch, completed,
):
    financial, feedback, repo, _ = setup(monkeypatch)
    work, causal = _attach_original_completed_work(
        monkeypatch, financial, feedback, repo, completed,
    )
    def wrong_preview(**kwargs):
        expected = dict(
            tenant_id=financial["tenant_id"], outcome_ref=feedback["outcome_ref"],
            work_id=OTHER,  # not the real persisted completed work
        )
        return dict(
            schema_version="empire.economic_memory.v1", mode="OBSERVE",
            execution_authority="none", accounting_authority="none",
            commercial_authority="none", promoted_learning=False,
            model_weight_mutation_authorized=False,
            plan_outcome_attribution_count=1,
            decision_outcome_attribution_count=1,
            plan_outcome_attributions=[expected],
            decision_outcome_attributions=[
                {**expected, "decision_ref": causal["decision_ref"]},
            ],
        )
    monkeypatch.setattr(
        "empire_os.canonical_economic_memory_handoff.build_economic_memory_snapshot",
        wrong_preview,
    )
    with pytest.raises(
        ProspectHandoffHold, match="ORIGINAL_CAUSAL_ATTRIBUTION_PREVIEW_MISMATCH",
    ):
        review(financial, repo)


@pytest.mark.parametrize("mutation,reason", [
    (lambda f,b: f.update(reported_actual_cost_evidence_refs=[]),
     "MISSING_OR_DUPLICATE_ORIGINAL_COST_PROVENANCE"),
    (lambda f,b: f.update(reported_actual_cost_evidence_refs=[
        f["reported_actual_cost_evidence_refs"][0]]*2),
     "MISSING_OR_DUPLICATE_ORIGINAL_COST_PROVENANCE"),
    (lambda f,b: f["reported_actual_cost_evidence_refs"].__setitem__(
        0, "canonical:commercial_evidence_registry:other-invoice"),
     "ORIGINAL_COST_RECEIPT_LINEAGE_MISMATCH"),
    (lambda f,b: b["evidence_refs"].remove(
        f["reported_actual_cost_evidence_refs"][0]),
     "ORIGINAL_COST_RECEIPT_LINEAGE_MISMATCH"),
    (lambda f,b: b["cortex_packet"]["label"]["evidence_refs"].remove(
        f["reported_actual_cost_evidence_refs"][0]),
     "ORIGINAL_COST_RECEIPT_LINEAGE_MISMATCH"),
    (lambda f,b: b["evidence_refs"].append(
        "canonical:commercial_evidence_registry:unrelated-cost"),
     "ORIGINAL_COST_RECEIPT_LINEAGE_MISMATCH"),
])
def test_v10_requires_exact_original_cost_registry_evidence(
    monkeypatch, mutation, reason,
):
    financial, feedback, repo, calls = setup(monkeypatch)
    mutation(financial, feedback)
    repo.verified_outcome_feedback = lambda *args, **kwargs: deepcopy(feedback)
    with pytest.raises(ProspectHandoffHold, match=reason):
        review(financial, repo)
    assert calls == []
