import pytest

from empire_os.zero_cash_operating_policy import (
    ZeroCashCandidate,
    evaluate_zero_cash_candidates,
)


def candidate(**overrides):
    values = {
        "action_key": "sell_permit_intelligence",
        "product_code": "permit_intelligence",
        "binding_terms_ready": True,
        "incremental_cash_requirement_cents": 0,
        "total_cost_cents": None,
        "requires_paid_acquisition": False,
        "uses_owned_or_public_evidence": True,
        "evidence_refs": ("catalog:permit", "permit:public"),
    }
    values.update(overrides)
    return ZeroCashCandidate(**values)


def evaluate(items, **overrides):
    values = {
        "available_cash_cents": 0,
        "reserved_cash_cents": 0,
        "cash_evidence_ref": "cash:verified:0",
        "budget_authorized": False,
        "budget_evidence_ref": None,
    }
    values.update(overrides)
    return evaluate_zero_cash_candidates(items, **values)


def test_zero_incremental_cash_action_is_eligible_without_claiming_zero_cost():
    result = evaluate([candidate()])[0]

    assert result.decision == "ELIGIBLE_ZERO_INCREMENTAL_CASH"
    assert result.total_cost_known is False
    assert result.zero_incremental_cash_means_zero_total_cost is False
    assert result.spend_execution is False
    assert result.execution_authority == "none"


def test_forecast_revenue_never_becomes_available_cash():
    result = evaluate([
        candidate(
            action_key="paid_ppc",
            incremental_cash_requirement_cents=5000,
            total_cost_cents=5000,
            requires_paid_acquisition=True,
        )
    ])[0]

    assert result.decision == "BLOCKED_INSUFFICIENT_CASH"
    assert result.forecast_revenue_used_as_cash is False


def test_reserved_cash_cannot_be_reused():
    result = evaluate([
        candidate(
            action_key="paid_ppc",
            incremental_cash_requirement_cents=4000,
            total_cost_cents=4000,
            requires_paid_acquisition=True,
        )
    ],
        available_cash_cents=10000,
        reserved_cash_cents=8000,
        cash_evidence_ref="cash:10000",
        budget_authorized=True,
        budget_evidence_ref="budget:ppc",
    )[0]

    assert result.verified_spendable_cash_cents == 2000
    assert result.decision == "BLOCKED_INSUFFICIENT_CASH"


def test_paid_action_requires_budget_authority_even_with_cash():
    result = evaluate([
        candidate(
            action_key="paid_ppc",
            incremental_cash_requirement_cents=4000,
            total_cost_cents=4000,
            requires_paid_acquisition=True,
        )
    ],
        available_cash_cents=10000,
        reserved_cash_cents=0,
        cash_evidence_ref="cash:10000",
        budget_authorized=False,
        budget_evidence_ref=None,
    )[0]

    assert result.decision == "BLOCKED_BUDGET_AUTHORITY"


def test_paid_action_can_be_recommended_with_verified_cash_and_budget():
    result = evaluate([
        candidate(
            action_key="paid_ppc",
            incremental_cash_requirement_cents=4000,
            total_cost_cents=4000,
            requires_paid_acquisition=True,
        )
    ],
        available_cash_cents=10000,
        reserved_cash_cents=0,
        cash_evidence_ref="cash:10000",
        budget_authorized=True,
        budget_evidence_ref="budget:ppc",
    )[0]

    assert result.decision == "ELIGIBLE_WITH_VERIFIED_CASH"
    assert result.spend_execution is False


def test_unknown_cash_requirement_stays_unknown():
    result = evaluate([
        candidate(incremental_cash_requirement_cents=None)
    ])[0]

    assert result.decision == "UNKNOWN_CASH_REQUIREMENT"
    assert "incremental_cash_requirement_unknown" in result.blockers


def test_unverified_product_is_blocked_even_when_zero_incremental_cash():
    result = evaluate([
        candidate(binding_terms_ready=False)
    ])[0]

    assert result.decision == "BLOCKED_PRODUCT_NOT_READY"


def test_paid_acquisition_cannot_claim_zero_incremental_cash():
    with pytest.raises(ValueError, match="paid acquisition"):
        evaluate([
            candidate(
                requires_paid_acquisition=True,
                incremental_cash_requirement_cents=0,
            )
        ])
