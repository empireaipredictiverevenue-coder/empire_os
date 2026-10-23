"""Contract regressions for the OBSERVE Predictive Revenue brain integration."""
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.permit_intelligence_runtime import PERMIT_SOURCES
from empire_os.permit_product_integration import build_permit_product_integration
from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review

NOW = datetime(2026, 10, 23, 18, 0, tzinfo=timezone.utc)
TENANT = "tenant-a"


def storm_candidate(**updates):
    value = {
        "opportunity_key": "storm:unique",
        "tenant_id": TENANT,
        "event_id": "storm-1",
        "event_truth_class": "OBSERVED",
        "evaluated_at": (NOW - timedelta(minutes=30)).isoformat(),
        "evidence_refs": ["noaa:event:1"],
        "execution_authority": "none",
        "commercial_ready": False,
        "revenue_inferred": False,
        "actual_revenue": False,
    }
    value.update(updates)
    return value


def storm_snapshot(*rows):
    return {
        "schema_version": "empire.storm_opportunity_snapshot.v1",
        "mode": "OBSERVE",
        "generated_at": NOW.isoformat(),
        "execution_authority": "none",
        "automatic_external_execution_allowed": False,
        "candidates": list(rows),
    }


def permit_integration():
    source = sorted(PERMIT_SOURCES)[0]
    return build_permit_product_integration(
        tenant_id=TENANT,
        as_of=NOW,
        permit_signals=[{
            "source": source, "tenant_id": TENANT,
            "raw": {"id": "permit-42"},
            "last_seen_at": (NOW - timedelta(hours=1)).isoformat(),
            "url": "https://example.org/permit/42",
            "metro": "Dallas, TX", "evidence_class": "OBSERVED",
        }],
    )


def deal(**updates):
    row = {
        "tenant_id": TENANT,
        "deal_id": "deal-1",
        "stage": "PROPOSAL",
        "currency": "GBP",
        "value_cents": 123456,
        "updated_at": (NOW - timedelta(hours=1)).isoformat(),
        "evidence_refs": ["crm:deal:1"],
    }
    row.update(updates)
    return row


def review(**updates):
    return build_predictive_revenue_brain_review(tenant_id=TENANT, as_of=NOW, **updates)


def test_combines_original_storm_and_permit_via_jev_without_revenue():
    result = review(
        storm_snapshot=storm_snapshot(storm_candidate()),
        permit_integration=permit_integration(),
    )
    assert result["opportunity_count"] == 2
    assert len(result["storm_research"]) == 1
    assert len(result["permit_research"]) == 1
    for item in (*result["storm_research"], *result["permit_research"]):
        assert item["recommendation"] == "RESEARCH_REQUIRED"
        assert item["actual_revenue"] is False
        assert item["expected_revenue_cents"] is None
        assert item["execution_authority"] == "none"
        assert "probability_not_backed_by_verified_outcomes" in item["blockers"]
    assert result["astra_dispatch_executed"] is False
    assert result["recognized_revenue_cents"] is None
    assert result["database_writes"] is False
    assert result["payment_executed"] is False


def test_pipeline_exact_cents_no_fake_probability_or_mrr():
    result = review(crm_deals=[deal()])
    bucket = result["crm_pipeline"]["currency_groups"][0]
    assert bucket["open_pipeline_cents"] == 123456
    assert bucket["modeled_open_pipeline_cents"] is None
    assert bucket["unknown_probability_count"] == 1
    assert bucket["recognized_revenue_cents"] is None
    assert bucket["mrr_cents"] is None
    assert bucket["p90_forecast_cents"] is None


def test_weighted_velocity_is_labeled_caller_supplied_projection():
    bucket = review(crm_deals=[deal(
        value_cents=100001, win_probability_basis_points=7000,
        probability_evidence_refs=["crm:historic-cohort"],
        cycle_days=14,
    )])["crm_pipeline"]["currency_groups"][0]
    assert bucket["modeled_open_pipeline_cents"] == 70001
    assert bucket["modeled_daily_velocity_cents"] == 5000
    assert bucket["model_inputs_independently_verified"] is False
    assert bucket["recognized_revenue_cents"] is None


def test_stage_closed_won_is_never_recognized_revenue():
    bucket = review(crm_deals=[deal(
        stage="CLOSED_WON", value_cents=25_000_00,
        actual_revenue=True, payment_verified=True,
    )])["crm_pipeline"]["currency_groups"][0]
    assert bucket["closed_won_contract_cents"] == 25_000_00
    assert bucket["closed_won_count"] == 1
    assert bucket["open_pipeline_cents"] == 0
    assert bucket["recognized_revenue_cents"] is None


def test_partial_probability_coverage_disables_aggregate():
    bucket = review(crm_deals=[
        deal(deal_id="1", value_cents=300,
             win_probability_basis_points=10000,
             probability_evidence_refs=["cohort:1"], cycle_days=1),
        deal(deal_id="2", value_cents=100),
    ])["crm_pipeline"]["currency_groups"][0]
    assert bucket["modeled_deal_count"] == 1
    assert bucket["unknown_probability_count"] == 1
    assert bucket["modeled_open_pipeline_cents"] is None
    assert bucket["modeled_daily_velocity_cents"] is None


def test_mixed_currencies_not_combined():
    groups = review(crm_deals=[
        deal(deal_id="a", currency="GBP"),
        deal(deal_id="b", currency="USDT"),
    ])["crm_pipeline"]["currency_groups"]
    assert [g["currency"] for g in groups] == ["GBP", "USDT"]
    assert [g["open_pipeline_cents"] for g in groups] == [123456, 123456]


@pytest.mark.parametrize("kwargs", [
    {"crm_deals": [deal(tenant_id="tenant-b")]},
    {"crm_deals": [deal(value_cents=10.5)]},
    {"crm_deals": [deal(value_cents=-1)]},
    {"crm_deals": [deal(win_probability_basis_points=12000, probability_evidence_refs=["x"])]},
    {"crm_deals": [deal(win_probability_basis_points=7000)]},
    {"crm_deals": [deal(updated_at=NOW + timedelta(minutes=1))]},
    {"crm_deals": [deal(), deal()]},
    {"crm_deals": [deal(stage="ACTUAL_REVENUE")]},
    {"storm_snapshot": storm_snapshot(storm_candidate(tenant_id="other"))},
    {"storm_snapshot": storm_snapshot(storm_candidate(evidence_refs=[]))},
    {"storm_snapshot": storm_snapshot(storm_candidate(
        evaluated_at=NOW + timedelta(hours=1)
    ))},
    {"storm_snapshot": storm_snapshot(storm_candidate(
        execution_authority="execute_bounded"
    ))},
    {"storm_snapshot": storm_snapshot(storm_candidate(
        commercial_ready=True
    ))},
    {"storm_snapshot": storm_snapshot(storm_candidate(
        revenue_inferred=True
    ))},
    {"storm_snapshot": storm_snapshot(storm_candidate(
        payment_authority="execute_bounded"
    ))},
])
def test_fail_closed_on_scope_origin_arithmetic_and_authority(kwargs):
    with pytest.raises(ValueError):
        review(**kwargs)


def test_repeatable_and_input_is_not_mutated():
    item = storm_candidate()
    snapshot = storm_snapshot(item)
    original = dict(item)
    first = review(storm_snapshot=snapshot, crm_deals=[deal()])
    second = review(storm_snapshot=snapshot, crm_deals=[deal()])
    assert first == second
    assert item == original


def test_no_actions_with_empty_inputs():
    result = review()
    assert result["opportunity_count"] == 0
    assert result["crm_pipeline"]["source_rows"] == 0
    assert result["recognized_revenue_cents"] is None
    assert result["execution_authority"] == "none"
