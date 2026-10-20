"""Offline TEST fixtures for exact tenant-scoped canonical outcomes.

Uses the original production verifier and its supported fixture builder; no
synthetic records are written into EmpireOS production databases or runtime.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from empire_os.authenticated_commercial_outcome_intelligence import (
    inspect_canonical_order_outcomes,
)
from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
from empire_os.outcome_feedback import (
    build_verified_outcome_feedback, validate_verified_feedback,
)
from test_verified_outcome_learning_continuity import twin as existing_owner_fixture

TENANT = "10000000-0000-4000-8000-000000000001"
ORDER = "30000000-0000-4000-8000-000000000001"
OTHER_ORDER = "30000000-0000-4000-8000-000000000002"
NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)


class BackendInfo:
    def as_dict(self):
        return {"primary_backend": "empiredb"}


class OriginalGateway:
    def snapshot(self):
        return BackendInfo()


def repository(monkeypatch, callback):
    repo = ExecutionBusDataRepository(OriginalGateway())
    monkeypatch.setattr(repo, "verified_outcome_feedback", callback, raising=False)
    return repo


def original_verified_feedback():
    data = existing_owner_fixture()
    data["tenant_id"] = TENANT
    data["outcomes"]["history"][0]["tenant_id"] = TENANT
    data["outcomes"]["history"][0]["fulfilment_order_id"] = ORDER
    data["outcomes"]["history"][0]["evidence"]["tenant_id"] = TENANT
    data["commercial"]["payment_evidence"][0]["tenant_id"] = TENANT
    data["commercial"]["payment_evidence"][0]["fulfilment_order_id"] = ORDER
    data["commercial"]["fulfilment_orders"][0]["id"] = ORDER
    data["commercial"]["fulfilment_orders"][0]["tenant_id"] = TENANT
    data["revenue_truth"]["tenant_id"] = TENANT
    data["revenue_truth"]["fulfilment_order_id"] = ORDER
    f = build_verified_outcome_feedback(data, tenant_id=TENANT, as_of=NOW)
    validate_verified_feedback(f, tenant_id=TENANT, as_of=NOW)
    return f


def call(repo, orders=None, **extra):
    return inspect_canonical_order_outcomes(
        repository=repo, tenant_id=TENANT, exact_order_ids=orders if orders is not None else [ORDER],
        repo_root="/synthetic-owner-worktree", now=NOW, **extra,
    )


def test_original_owner_verified_financial_outcome_becomes_reviewable(monkeypatch):
    feedback = original_verified_feedback()
    observed = []

    def canonical(order, **kwargs):
        observed.append((order, kwargs["tenant_id"], kwargs["as_of"]))
        return deepcopy(feedback)

    repo = repository(monkeypatch, canonical)
    result = call(repo)
    assert observed == [(ORDER, TENANT, NOW)]
    assert result["status"] == "CANONICAL_VERIFIED_ORDER_OUTCOMES"
    assert result["independently_validated_outcome_count"] == 1
    assert result["verified_won_outcome_count"] == 1
    assert result["recognized_revenue_cents_for_complete_selected_cohort"] == 1000
    assert result["realized_gross_profit_cents_for_complete_selected_cohort"] == -200
    assert result["verified_wins_with_actual_cost_and_profit_count"] == 1
    assert result["model_training_authorized"] is False
    assert result["outbound_authorized"] is False
    assert result["agent_tasks_created"] is False
    assert result["database_writes"] is False
    serialized = str(result)
    for secret in (TENANT, ORDER, "tenant-A", "buyer-1", "payment-1", "private@", "test-proof"):
        assert secret not in serialized


def test_unverified_source_failure_held_and_not_laundered_as_zero_revenue(monkeypatch):
    def unavailable(_order, **_kwargs):
        raise ValueError("hidden contact email and missing payment")
    report = call(repository(monkeypatch, unavailable))
    assert report["status"] == "CANONICAL_ORDER_EVIDENCE_PARTIAL_HOLD"
    assert report["missing_or_invalid_order_proof_count"] == 1
    assert report["recognized_revenue_cents_for_complete_selected_cohort"] is None
    assert report["realized_gross_profit_cents_for_complete_selected_cohort"] is None
    assert "hidden contact" not in str(report)


def test_one_out_of_two_unverified_does_not_extrapolate_total_sales(monkeypatch):
    f = original_verified_feedback()
    def reader(order, **_kwargs):
        if order == ORDER:
            return deepcopy(f)
        raise ValueError("missing canonical outcome")
    report = call(repository(monkeypatch, reader), orders=[ORDER, OTHER_ORDER])
    assert report["independently_validated_outcome_count"] == 1
    assert report["missing_or_invalid_order_proof_count"] == 1
    assert report["recognized_revenue_cents_for_complete_selected_cohort"] is None
    assert report["realized_gross_profit_cents_for_complete_selected_cohort"] is None
    assert report["no_general_market_conversion_rate_inferred"] is True


@pytest.mark.parametrize("mutation", [
    lambda f: f.update(synthetic=True),
    lambda f: f.update(tenant_id=OTHER_ORDER),
    lambda f: f.update(actual_revenue_cents=999999),
    lambda f: f.update(gross_profit_cents=99999),
    lambda f: f.update(fulfilment_order_id=OTHER_ORDER),
    lambda f: f["cortex_packet"]["verification"].update(payment_verified=False),
])
def test_forged_activated_claims_never_pass_original_validator(monkeypatch, mutation):
    f = original_verified_feedback()
    mutation(f)
    report = call(repository(monkeypatch, lambda *_a, **_kw: f))
    assert report["independently_validated_outcome_count"] == 0
    assert report["missing_or_invalid_order_proof_count"] == 1
    assert report["recognized_revenue_cents_for_complete_selected_cohort"] is None


def test_no_selected_orders_is_not_no_sales_across_market(monkeypatch):
    repo = repository(monkeypatch, lambda *_a, **_kw: pytest.fail("must not look up unspecified order"))
    result = call(repo, orders=[])
    assert result["status"] == "NO_EXPLICIT_ORDERS_SELECTED"
    assert result["selected_exact_order_count"] == 0
    assert result["recognized_revenue_cents_for_complete_selected_cohort"] is None


def test_invalid_scope_or_duplicate_prevents_any_repo_queries(monkeypatch):
    repo = repository(monkeypatch, lambda *_a, **_kw: pytest.fail("must not query invalid orders"))
    with pytest.raises(ValueError, match="duplicate"):
        call(repo, orders=[ORDER, ORDER])
    with pytest.raises(ValueError, match="UUID"):
        call(repo, orders=["Company Name"])
    with pytest.raises(ValueError, match="bounded"):
        call(repo, orders=[str(uuid4()) for _ in range(21)])
    with pytest.raises(ValueError, match="UUID"):
        inspect_canonical_order_outcomes(
            repository=repo, tenant_id="tenant-guessed", exact_order_ids=[ORDER],
            repo_root="/fake", now=NOW,
        )


def test_gateway_other_than_canonical_empiredb_rejected(monkeypatch):
    class WrongGateway:
        def snapshot(self):
            return type("X", (), {"as_dict": lambda s: {"primary_backend": "mock"}})()
    repo = ExecutionBusDataRepository(WrongGateway())
    monkeypatch.setattr(repo, "verified_outcome_feedback",
                        lambda *_a, **_kw: pytest.fail("no source read"), raising=False)
    with pytest.raises(ValueError, match="canonical EmpireDB"):
        call(repo)


def test_no_caller_supplied_boolean_can_enable_outreach_or_spend(monkeypatch):
    f = original_verified_feedback()
    repo = repository(monkeypatch, lambda *_a, **_kw: f)
    result = call(repo)
    assert result["no_link_to_historical_sales_threads_inferred"] is True
    assert result["no_buyer_capacity_activation_inferred"] is True
    assert result["model_training_authorized"] is False
    assert result["payments_executed"] is False


def test_original_owner_reader_uncommitted_module_fails_closed_without_invented_outcomes():
    # Simulate an existing canonical repository deployment where the owner
    # verified-order reader is not yet provided.
    repo = ExecutionBusDataRepository(OriginalGateway())
    repo.verified_outcome_feedback = None
    result = call(repo)
    assert result["status"] == "CANONICAL_OWNER_READER_NOT_DEPLOYED"
    assert result["original_verified_outcome_reader_available"] is False
    assert result["recognized_revenue_cents_for_complete_selected_cohort"] is None
    assert result["independently_validated_outcome_count"] == 0
    assert result["outbound_authorized"] is False
