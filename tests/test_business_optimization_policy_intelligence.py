import json
from datetime import datetime, timezone

from empire_os.business_optimization_policy_intelligence import (
    refresh_business_optimization_policy_intelligence,
)


NOW = datetime(2026, 10, 2, 23, 0, tzinfo=timezone.utc)


def _write(root, rel, payload):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_policy_intelligence_batches_all_domains_and_never_guesses(tmp_path):
    result = refresh_business_optimization_policy_intelligence(
        tmp_path,
        now=NOW,
    )

    assert result["status"] == "AVAILABLE"
    assert result["workload_count"] == 12
    assert result["batch_refresh"] is True
    assert result["manual_domain_by_domain_scan_required"] is False
    assert result["synthetic_constraints_generated"] is False
    assert result["synthetic_economics_generated"] is False
    assert result["automatic_business_action_allowed"] is False
    assert result["execution_authority"] == "none"


def test_verified_price_ladder_does_not_become_fake_pricing_objective(tmp_path):
    _write(
        tmp_path,
        "runtime/commercial_catalog/pricing_verification_latest.json",
        {
            "approval_reference": "founder_approval:test",
            "pricing_matches_approved_policy": True,
            "checks": [
                {
                    "product_code": "a",
                    "amount_cents": 100,
                    "matches_policy": True,
                }
            ],
        },
    )

    result = refresh_business_optimization_policy_intelligence(
        tmp_path,
        now=NOW,
    )
    pricing = result["workloads"]["pricing"]

    assert pricing["state"] == "EVIDENCE_PARTIAL"
    assert pricing["observations"]["approved_price_ladder_verified"] is True
    assert (
        "alternative_price_scenario_demand_and_conversion_economics_required"
        in pricing["blockers"]
    )
    assert pricing["auto_activation_safe"] is False


def test_unconfigured_cash_budget_blocks_capital_and_marketing(tmp_path):
    _write(
        tmp_path,
        "runtime/departments/budget/latest.json",
        {
            "policy_configured": False,
            "cash_spend_authority": False,
            "budget_override_authority": False,
        },
    )

    result = refresh_business_optimization_policy_intelligence(
        tmp_path,
        now=NOW,
    )

    for workload in ("capital_allocation", "marketing_budgets"):
        assert (
            "explicit_budget_limit_policy_required"
            in result["workloads"][workload]["blockers"]
        )
        assert result["workloads"][workload][
            "auto_activation_safe"
        ] is False


def test_active_policy_is_preserved_not_reinvented(tmp_path):
    _write(
        tmp_path,
        "runtime/business_optimization/policies/inventory.json",
        {
            "status": "ACTIVE",
            "time_budget_ms": 1000,
            "evidence_refs": ["inventory-policy:evidence"],
        },
    )

    result = refresh_business_optimization_policy_intelligence(
        tmp_path,
        now=NOW,
    )
    inventory = result["workloads"]["inventory"]

    assert inventory["state"] == "ACTIVE_POLICY"
    assert inventory["policy_active"] is True
    assert inventory["blockers"] == []
    assert inventory["auto_activation_safe"] is False


def test_missing_opportunity_economics_blocks_strategy_and_expansion(tmp_path):
    _write(
        tmp_path,
        "runtime/opportunity_factory/value_latest.json",
        {
            "items": [
                {
                    "opportunity_key": "x",
                    "status": "UNAVAILABLE",
                    "expected_gross_profit_cents": None,
                    "quant_input_evidence": {},
                }
            ]
        },
    )
    _write(
        tmp_path,
        "runtime/opportunity_radar/latest.json",
        {
            "candidates": [
                {
                    "opportunity_key": "x",
                    "opportunity_factory_ready": False,
                }
            ]
        },
    )

    result = refresh_business_optimization_policy_intelligence(
        tmp_path,
        now=NOW,
    )

    assert (
        "normalized_opportunity_economics_required"
        in result["workloads"]["portfolio_strategy"]["blockers"]
    )
    assert (
        "market_identity_and_factory_readiness_required"
        in result["workloads"]["market_expansion"]["blockers"]
    )
