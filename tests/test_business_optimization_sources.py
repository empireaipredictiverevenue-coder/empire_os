from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.business_optimization_sources import (
    run_business_optimization_source_cycle,
)


NOW = datetime(2026, 10, 2, 23, 0, tzinfo=timezone.utc)


def _write(root: Path, rel: str, payload) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _policy(root: Path, workload: str) -> None:
    _write(
        root,
        f"runtime/business_optimization/policies/{workload}.json",
        {
            "status": "ACTIVE",
            "evidence_refs": ["policy:test"],
            "objective_field": "expected_gross_profit_cents",
            "resource_limits": {"capital": {"max": 1000}},
            "resource_field_map": {"capital": "expected_cost_cents"},
            "time_budget_ms": 1000,
        },
    )


def _sources(root: Path, *, available=True, factory_ready=True) -> None:
    _write(
        root,
        "runtime/opportunity_factory/value_latest.json",
        {
            "generated_at": "2026-10-02T22:59:00+00:00",
            "items": [
                {
                    "opportunity_key": "market:test:london",
                    "status": "AVAILABLE" if available else "UNAVAILABLE",
                    "expected_gross_profit_cents": 500,
                    "expected_cost_cents": 200,
                    "opportunity_class": "market_research",
                    "rank": 1,
                    "quant_input_evidence": {
                        "evidence_refs": ["evidence:value"]
                    },
                }
            ],
        },
    )
    _write(
        root,
        "runtime/opportunity_radar/latest.json",
        {
            "generated_at": "2026-10-02T22:59:00+00:00",
            "candidates": [
                {
                    "opportunity_key": "market:test:london",
                    "metro": "London",
                    "niche": "test",
                    "opportunity_factory_ready": factory_ready,
                    "evidence_refs": ["evidence:radar"],
                }
            ],
        },
    )


def test_source_cycle_does_not_enqueue_without_policy(tmp_path):
    _sources(tmp_path)

    result = run_business_optimization_source_cycle(tmp_path, now=NOW)

    row = result["workloads"]["portfolio_strategy"]
    assert row["source_adapter_implemented"] is True
    assert row["policy_ready"] is False
    assert row["automation_ready"] is False
    assert "optimization_policy_not_configured" in row["blockers"]
    assert result["enqueued_count"] == 0


def test_portfolio_source_enqueues_when_policy_and_economics_are_complete(
    tmp_path,
):
    _policy(tmp_path, "portfolio_strategy")
    _sources(tmp_path)

    result = run_business_optimization_source_cycle(tmp_path, now=NOW)

    row = result["workloads"]["portfolio_strategy"]
    assert row["source_ready"] is True
    assert row["automation_ready"] is True
    assert row["enqueued"] is True
    assert result["enqueued_count"] == 1
    queued = list(
        (
            tmp_path / "runtime/business_optimization/inbox"
        ).glob("*.json")
    )
    assert len(queued) == 1


def test_unchanged_source_does_not_reenqueue_every_heartbeat(tmp_path):
    _policy(tmp_path, "portfolio_strategy")
    _sources(tmp_path)

    first = run_business_optimization_source_cycle(tmp_path, now=NOW)
    second = run_business_optimization_source_cycle(tmp_path, now=NOW)

    assert first["enqueued_count"] == 1
    assert second["enqueued_count"] == 0
    assert second["workloads"]["portfolio_strategy"]["enqueue"][
        "status"
    ] == "UNCHANGED"


def test_market_expansion_requires_factory_ready_market_identity(tmp_path):
    _policy(tmp_path, "market_expansion")
    _sources(tmp_path, factory_ready=False)

    result = run_business_optimization_source_cycle(tmp_path, now=NOW)

    row = result["workloads"]["market_expansion"]
    assert row["source_ready"] is False
    assert row["automation_ready"] is False
    assert row["blocked_candidates"][0]["reason"] == (
        "source_evidence_incomplete"
    )
    assert "opportunity_factory_ready" in row["blocked_candidates"][0][
        "missing_fields"
    ]


def test_unavailable_economics_never_becomes_optimization_request(tmp_path):
    _policy(tmp_path, "portfolio_strategy")
    _sources(tmp_path, available=False)

    result = run_business_optimization_source_cycle(tmp_path, now=NOW)

    row = result["workloads"]["portfolio_strategy"]
    assert row["source_ready"] is False
    assert row["candidate_count"] == 0
    assert result["enqueued_count"] == 0
    assert result["unknown_is_zero"] is False


def test_all_domains_have_source_adapter_contract_but_need_policy(tmp_path):
    result = run_business_optimization_source_cycle(tmp_path, now=NOW)

    assert result["source_adapter_implemented_count"] == 12
    row = result["workloads"]["staff_capacity"]
    assert row["source_adapter_implemented"] is True
    assert row["automation_ready"] is False
    assert "optimization_policy_not_configured" in row["blockers"]


def test_generic_runtime_adapter_enqueues_marketing_budget_evidence(tmp_path):
    _write(
        tmp_path,
        "runtime/business_optimization/policies/marketing_budgets.json",
        {
            "status": "ACTIVE",
            "evidence_refs": ["policy:marketing"],
            "source_file": "runtime/marketing/channel_economics.json",
            "rows_path": "channels",
            "option_key_field": "channel_key",
            "entity_key_field": "channel_key",
            "objective_field": "expected_contribution_cents",
            "row_evidence_refs_field": "evidence_refs",
            "resource_limits": {"marketing_budget": {"max": 1000}},
            "resource_field_map": {
                "marketing_budget": "required_budget_cents"
            },
            "status_field": "status",
            "allowed_statuses": ["AVAILABLE"],
            "partition_field": "market",
            "metadata_fields": ["market"],
            "time_budget_ms": 1000,
        },
    )
    _write(
        tmp_path,
        "runtime/marketing/channel_economics.json",
        {
            "generated_at": "2026-10-02T22:58:00+00:00",
            "channels": [
                {
                    "channel_key": "search",
                    "status": "AVAILABLE",
                    "expected_contribution_cents": 700,
                    "required_budget_cents": 400,
                    "market": "UK",
                    "evidence_refs": ["forecast:search"],
                },
                {
                    "channel_key": "outbound",
                    "status": "AVAILABLE",
                    "expected_contribution_cents": 900,
                    "required_budget_cents": 500,
                    "market": "UK",
                    "evidence_refs": ["forecast:outbound"],
                },
            ],
        },
    )

    result = run_business_optimization_source_cycle(tmp_path, now=NOW)

    row = result["workloads"]["marketing_budgets"]
    assert row["source_adapter"] == "policy_mapped_runtime_evidence"
    assert row["source_ready"] is True
    assert row["automation_ready"] is True
    assert row["candidate_count"] == 2
    assert row["enqueued"] is True
    assert row["configured_source_file"] == (
        "runtime/marketing/channel_economics.json"
    )
    assert result["unknown_is_zero"] is False


def test_generic_runtime_adapter_rejects_source_outside_runtime(tmp_path):
    _write(
        tmp_path,
        "runtime/business_optimization/policies/staff_capacity.json",
        {
            "status": "ACTIVE",
            "evidence_refs": ["policy:staff"],
            "source_file": "../secret.json",
            "rows_path": "items",
            "option_key_field": "id",
            "entity_key_field": "id",
            "objective_field": "value",
            "time_budget_ms": 1000,
        },
    )

    result = run_business_optimization_source_cycle(tmp_path, now=NOW)

    row = result["workloads"]["staff_capacity"]
    assert row["source_ready"] is False
    assert "optimization_source_file_outside_runtime" in row["blockers"]
    assert row["automation_ready"] is False


def test_generic_adapter_preserves_unknown_objective_as_blocker(tmp_path):
    _write(
        tmp_path,
        "runtime/business_optimization/policies/inventory.json",
        {
            "status": "ACTIVE",
            "evidence_refs": ["policy:inventory"],
            "source_file": "runtime/inventory/economics.json",
            "rows_path": "items",
            "option_key_field": "inventory_key",
            "entity_key_field": "inventory_key",
            "objective_field": "expected_value_cents",
            "time_budget_ms": 1000,
        },
    )
    _write(
        tmp_path,
        "runtime/inventory/economics.json",
        {
            "generated_at": "2026-10-02T22:58:00+00:00",
            "items": [
                {
                    "inventory_key": "item-a",
                    "expected_value_cents": None,
                }
            ],
        },
    )

    result = run_business_optimization_source_cycle(tmp_path, now=NOW)

    row = result["workloads"]["inventory"]
    assert row["source_ready"] is False
    assert row["candidate_count"] == 0
    assert row["blocked_candidates"][0]["reason"] == (
        "source_evidence_incomplete"
    )
    assert row["automation_ready"] is False
    assert result["unknown_is_zero"] is False


def test_all_domains_support_canonical_internal_source_contract(tmp_path):
    result = run_business_optimization_source_cycle(tmp_path, now=NOW)

    assert result["source_adapter_implemented_count"] == 12
    assert all(
        row["source_adapter_implemented"] is True
        for row in result["workloads"].values()
    )


def test_generic_domain_source_contract_enqueues_when_policy_is_ready(tmp_path):
    from empire_os.business_optimization_sources import (
        publish_business_optimization_source,
    )

    _policy(tmp_path, "staff_capacity")
    published = publish_business_optimization_source(
        tmp_path,
        workload_type="staff_capacity",
        options=[
            {
                "option_key": "job-a::staff-1",
                "entity_key": "job-a",
                "objective_value": 500,
                "resource_usage": {"capital": 100},
                "evidence_refs": ["evidence:staff-fit"],
            }
        ],
        source_ref="staff_capacity:canonical:1",
        observed_at="2026-10-02T22:59:00+00:00",
        evidence_refs=["evidence:staff-capacity"],
    )

    assert published["status"] == "AVAILABLE"
    result = run_business_optimization_source_cycle(tmp_path, now=NOW)
    row = result["workloads"]["staff_capacity"]
    assert row["source_ready"] is True
    assert row["automation_ready"] is True
    assert row["enqueued"] is True

def test_source_readiness_summary_reports_truthful_global_counts(tmp_path):
    result = run_business_optimization_source_cycle(tmp_path, now=NOW)

    assert result["source_adapter_implemented_count"] == 12
    assert result["ready_workload_count"] == 0
    assert result["blocked_workload_count"] == 12
    assert result["generated_request_count"] == 0
    assert result["synthetic_economics_generated"] is False
