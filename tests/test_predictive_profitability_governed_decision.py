"""Read-only accounting truth and opportunity-level hypothesis separation."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.predictive_profitability_governed_decision import (
    review_existing_global_economics_truth,
    review_existing_global_economics_truth_runtime,
    build_profitability_governed_decision,
)
from test_predictive_profitability_playbooks import review as book

NOW = datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc)
T = (NOW-timedelta(minutes=4)).isoformat()


def aggregates():
    pulse = {
        "schema_version": "empire.revenue-pulse.v3", "mode": "OBSERVE",
        "execution_authority": "none", "execution_allowed": False,
        "payment_mutation": False, "revenue_mutation": False,
        "accounting_mutation": False, "generated_at": T,
        "recognized_revenue_truth": {
            "forecast_included_in_truth": False,
            "recognized_revenue_cents": 12345,
            "realized_gp_cents": -500,
        },
        "private_buyer_email": "private@buyer.example",
    }
    memory = {
        "schema_version": "empire.economic_memory.v1", "mode": "OBSERVE",
        "execution_authority": "none", "commercial_authority": "none",
        "accounting_authority": "none",
        "model_weight_mutation_authorized": False,
        "forecast_used_as_outcome": False,
        "synthetic_outcomes_allowed": False, "promoted_learning": False,
        "shadow_decisions_receive_causal_credit": False,
        "generated_at": (NOW-timedelta(minutes=3)).isoformat(),
        "outcome_conditioned_memory_count": 0,
        "calibration_evidence_count": 0,
        "decision_outcome_attribution_count": 0,
        "outcome_conditioned_memories": [],
        "calibration_evidence": [],
        "decision_outcome_attributions": [],
        "private_plan_id": "my-private-plan-id",
    }
    return pulse, memory


def truth():
    p, m = aggregates()
    return review_existing_global_economics_truth(p, m, as_of=NOW)


def test_company_wide_actual_gp_must_not_become_opportunity_actual_or_error():
    t = truth()
    assert t["status"] == "GLOBAL_ECONOMIC_SNAPSHOT_REVIEWED_NO_OPPORTUNITY_ATTRIBUTION"
    assert t["global_recognized_revenue_minor_from_pulse"] == 12345
    assert t["global_realized_gp_minor_from_pulse"] == -500
    assert t["single_opportunity_realized_gp_minor"] is None
    assert t["original_forecast_prediction_error_minor"] is None
    assert t["source_snapshots_are_same_business_cohort"] is False
    assert t["economic_memory_calibration_evidence_count"] == 0
    assert t["economic_memory_outcome_conditioned_count"] == 0
    assert "private@buyer.example" not in json.dumps(t)
    assert "my-private-plan-id" not in json.dumps(t)


def test_governed_decision_gives_thresholds_and_existing_owner_actions_only():
    x = build_profitability_governed_decision(book(), truth())
    assert x["status"] == "HYPOTHETICAL_DECISION_RESEARCH_ONLY"
    assert x["company_wide_realized_gp_minor_separate"] == -500
    assert x["opportunity_realized_gp_minor"] is None
    assert x["original_pilot_prediction_error_minor"] is None
    assert x["original_prediction_registry_matched"] is False
    assert x["source_owner_payment_authenticated_for_opportunity"] is False
    assert x["hypothetical_base_break_even_conversion_rate"] > 0
    assert x["hypothetical_base_break_even_unit_price_minor"] > 0
    assert x["negative_downside_hypothesis"] is True
    assert x["cash_cap_exceeded_in_hypothesis"] is True
    assert x["decision_release_gate"] == (
        "HOLD_NO_REGISTERED_PREDICTION_OR_AUTHENTICATED_PAID_OUTCOME")
    assert any(a["playbook_key"]=="VERIFY_FIRST_PAYER" for a in x["playbook_owner_actions"])
    assert all(not a["sent_to_execution_bus"] for a in x["playbook_owner_actions"])
    assert x["automatic_spend_or_pricing_change"] is False
    assert x["economic_memory_feedback_written"] is False
    assert x["execution_authority"] == "none"


@pytest.mark.parametrize("mutate,code", [
    (lambda p,m:p.update(execution_allowed=True),"UNTRUSTED_REVENUE_PULSE_AUTHORITY"),
    (lambda p,m:p["recognized_revenue_truth"].update(forecast_included_in_truth=True),"FORECAST_LEAKED_INTO_REVENUE_TRUTH"),
    (lambda p,m:p["recognized_revenue_truth"].update(realized_gp_cents=True),"INVALID_CANONICAL_AGGREGATE_ECONOMICS"),
    (lambda p,m:p["recognized_revenue_truth"].update(recognized_revenue_cents=-1),"INVALID_CANONICAL_AGGREGATE_ECONOMICS"),
    (lambda p,m:m.update(model_weight_mutation_authorized=True),"UNTRUSTED_ECONOMIC_MEMORY_AUTHORITY"),
    (lambda p,m:m.update(promoted_learning=True),"UNTRUSTED_ECONOMIC_MEMORY_AUTHORITY"),
    (lambda p,m:m.update(calibration_evidence_count=1),"ECONOMIC_MEMORY_COUNT_ROWS_DISAGREE"),
    (lambda p,m:m.update(decision_outcome_attribution_count="one"),"INVALID_ECONOMIC_MEMORY_COUNTS"),
    (lambda p,m:p.update(generated_at=(NOW+timedelta(minutes=1)).isoformat()),"SOURCE_EPOCH_STALE_FUTURE_OR_SKEWED"),
    (lambda p,m:m.update(generated_at=(NOW-timedelta(hours=9)).isoformat()),"SOURCE_EPOCH_STALE_FUTURE_OR_SKEWED"),
])
def test_untrusted_revenue_source_or_fabricated_learning_holds(mutate,code):
    p,m=aggregates()
    mutate(p,m)
    x=review_existing_global_economics_truth(p,m,as_of=NOW)
    assert x["status"]=="ECONOMIC_TRUTH_SOURCE_HOLD"
    assert x["hold_code"]==code
    assert x["global_realized_gp_minor_from_pulse"] is None
    assert x["single_opportunity_realized_gp_minor"] is None
    assert x["database_writes"] is False


def test_source_hold_routes_to_finance_not_private_outreach():
    p,m=aggregates()
    p["payment_mutation"] = True
    bad=review_existing_global_economics_truth(p,m,as_of=NOW)
    result=build_profitability_governed_decision(book(),bad)
    assert result["company_wide_recognized_revenue_minor_separate"] is None
    assert result["playbook_owner_actions"][0]["existing_owner"] == "finance_and_economic_memory"
    assert result["playbook_owner_actions"][0]["playbook_key"] == "RESTORE_CANONICAL_ECONOMIC_TRUTH"
    assert result["playbook_owner_actions"][0]["sent_to_execution_bus"] is False
    assert result["opportunity_level_profitability_rank_authorized"] is False


def test_book_claiming_live_forecast_or_execution_rejected():
    safe=book()
    for attr,val in (
        ("original_forecast_registered",True),
        ("actual_gross_profit_verified",True),
        ("spend_authorized",True),
        ("scenario_set_exhaustive_or_calibrated",True),
    ):
        bad=deepcopy(safe)
        bad[attr]=val
        with pytest.raises(ValueError):
            build_profitability_governed_decision(bad,truth())


def test_runtime_reads_allowlisted_snapshots_only(tmp_path):
    p,m=aggregates()
    a=tmp_path/"runtime/revenue_pulse/latest.json"
    b=tmp_path/"runtime/economic_memory/latest.json"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.write_text(json.dumps(p))
    b.write_text(json.dumps(m))
    (a.parent/"other_private.json").write_text("IGNORE_PRIVATE_EMAIL")
    r=review_existing_global_economics_truth_runtime(tmp_path,as_of=NOW)
    assert r["status"]=="GLOBAL_ECONOMIC_SNAPSHOT_REVIEWED_NO_OPPORTUNITY_ATTRIBUTION"
    assert "IGNORE_PRIVATE_EMAIL" not in json.dumps(r)
    b.unlink()
    h=review_existing_global_economics_truth_runtime(tmp_path,as_of=NOW)
    assert h["hold_code"]=="UNAVAILABLE_MEMORY_SOURCE"


def test_break_even_thresholds_are_hypotheses_not_actual_conversion():
    r = book()
    row = r["scenario_rows"][1]
    assert row["required_conversion_rate_to_break_even_hypothetical"] == pytest.approx(0.05161290,abs=1e-8)
    assert row["required_unit_price_minor_to_break_even_hypothetical"] == pytest.approx(6666.6667,abs=0.001)
    assert row["break_even_conversion_feasible_within_probability_one"] is True
    assert row["expected_contribution_per_attempt_minor_hypothetical"] == 370
    assert r["original_forecast_registered"] is False
    assert r["original_pilot_design_sha256"]


def test_break_even_unavailable_when_all_buyers_refund_or_no_attempts():
    from test_predictive_profitability_playbooks import plan, pilot
    from empire_os.predictive_profitability_playbooks import review_profitability_playbook
    p = pilot()
    x = plan(p)
    for s in x["scenarios"]:
        s["refund_rate"] = 1.0
        s["qualified_attempts"] = 0
    out = review_profitability_playbook(p,x,as_of=datetime(2026,10,19,22,30,tzinfo=timezone.utc))
    assert all(r["required_conversion_rate_to_break_even_hypothetical"] is None
               for r in out["scenario_rows"])
    assert all(r["required_unit_price_minor_to_break_even_hypothetical"] is None
               for r in out["scenario_rows"])
    assert out["actual_gross_profit_verified"] is False
