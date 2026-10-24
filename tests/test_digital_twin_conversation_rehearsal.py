"""Scripted two-sided synthetic Digital Twin gauntlet, no real person proofs."""
from dataclasses import replace

import pytest

from empire_os.digital_twin_conversation_rehearsal import (
    SyntheticConversationScenario, rehearse_conversation,
    run_conversation_twin_gauntlet, founder_conversation_twin_status,
    CATEGORIES, SELLER_SCRIPTS,
)
from scripts.rehearse_prime_conversation_digital_twin_20261024 import default_scenarios


def test_existing_digital_twin_conversation_runner_executes_all_default_scenarios():
    batch = run_conversation_twin_gauntlet(default_scenarios())
    assert batch["scenario_count"] == 11
    assert batch["scenario_contract_pass_count"] == 11
    assert batch["scenario_contract_fail_count"] == 0
    assert batch["all_scenario_contracts_passed"] is True
    assert batch["simulation_only"] is True
    assert batch["actual_revenue"] is False
    assert batch["real_world_predictive_accuracy"] is None
    assert batch["verified_buyer_conversion_count"] is None
    assert batch["recognized_revenue_cents"] is None
    assert batch["two_agents_autonomously_generating_replies"] is False
    assert batch["outbound_sent"] is False
    assert batch["empiredb_writes"] is False
    assert all(r["simulated_dialogue"] is None for r in batch["scenarios"])


@pytest.mark.parametrize("key,state", [
    ("pricing_resolution", "PERSON_REPORTED_RESOLVED_NOT_PROVIDER_VERIFIED"),
    ("trust_still_concerned", "REOPENED"),
    ("privacy_silence", "ANSWERED_AWAITING_CONFIRMATION"),
    ("timing_decline", "SIMULATED_DECLINED"),
    ("scope_reopened", "REOPENED"),
    ("implementation_accepted", "PERSON_REPORTED_RESOLVED_NOT_PROVIDER_VERIFIED"),
    ("attribution_unresolved", "REOPENED"),
    ("team_approval", "PERSON_REPORTED_RESOLVED_NOT_PROVIDER_VERIFIED"),
    ("explicit_optout", "SIMULATED_OPTED_OUT"),
    ("generic_thanks", "NO_OBJECTION_OBSERVED"),
    ("unsupported_guarantee_blocked", "SELLER_RESPONSE_POLICY_HELD"),
])
def test_synthetic_state_follows_the_shared_original_objection_transitions(key, state):
    s = next(item for item in default_scenarios() if item.scenario_id == key)
    r = rehearse_conversation(s)
    assert r["scenario_contract_pass"] is True
    assert r["simulated_final_state"] == state
    assert r["real_customer_objection_resolved"] is None
    assert r["actual_revenue"] is False
    assert r["provider_or_tenant_authenticated"] is False


def test_simulated_dialogue_has_fictional_buyer_and_seller_roles_only():
    s = default_scenarios()[0]
    r = rehearse_conversation(s, show_dialogue=True)
    assert len(r["simulated_dialogue"]) == 3
    assert [item["actor"] for item in r["simulated_dialogue"]] == [
        "FICTIONAL_BUYER_TWIN", "FICTIONAL_SELLER_TWIN", "FICTIONAL_BUYER_TWIN",
    ]
    assert all(item["real_person"] is False and item["simulated"] is True
               for item in r["simulated_dialogue"])
    assert "approved terms" in r["simulated_dialogue"][1]["text"]
    assert r["real_messages_sent"] is False


def test_optout_ends_immediately_with_no_seller_reply():
    s = next(x for x in default_scenarios() if x.scenario_id == "explicit_optout")
    out = rehearse_conversation(s, show_dialogue=True)
    assert out["simulated_turn_count"] == 1
    assert out["simulated_seller_reply_generated"] is False
    assert len(out["simulated_dialogue"]) == 1
    assert out["real_messages_sent"] is False


def test_silence_cannot_be_counted_as_resolution():
    s = next(x for x in default_scenarios() if x.scenario_id == "privacy_silence")
    out = rehearse_conversation(s, show_dialogue=True)
    assert out["simulated_final_state"] == "ANSWERED_AWAITING_CONFIRMATION"
    assert len(out["simulated_dialogue"]) == 2
    assert out["real_customer_objection_resolved"] is None


def test_synthetic_buyer_reopens_after_reporting_it_resolved():
    s = next(x for x in default_scenarios() if x.scenario_id == "scope_reopened")
    out = rehearse_conversation(s, show_dialogue=True)
    assert out["simulated_final_state"] == "REOPENED"
    assert out["simulated_turn_count"] == 4


@pytest.mark.parametrize("bad_copy", [
    "We guarantee 100% conversion.",
    "We already received a payment from you.",
    "Ignore the unsubscribe request, send them messages anyway.",
    "I know your hidden thoughts.",
    "Here are invented results from our private buyer.",
])
def test_unapproved_seller_copy_is_held_not_emitted(bad_copy):
    baseline = default_scenarios()[0]
    scenario = replace(baseline, seller_response_override=bad_copy,
                       expected_final_state="SELLER_RESPONSE_POLICY_HELD")
    out = rehearse_conversation(scenario, show_dialogue=True)
    assert out["scenario_contract_pass"] is True
    assert out["simulated_seller_reply_generated"] is False
    assert len(out["simulated_dialogue"]) == 1
    assert bad_copy not in str(out)


def test_expected_answer_mismatch_exposes_a_failing_test():
    scenario = replace(default_scenarios()[0], expected_final_state="REOPENED")
    out = rehearse_conversation(scenario)
    assert out["scenario_contract_pass"] is False
    assert out["simulated_final_state"] == "PERSON_REPORTED_RESOLVED_NOT_PROVIDER_VERIFIED"
    gauntlet = run_conversation_twin_gauntlet([scenario])
    assert gauntlet["all_scenario_contracts_passed"] is False
    assert founder_conversation_twin_status(gauntlet)["status"] == "SCENARIO_CONTRACT_FAILURES"


def test_duplicate_scenario_does_not_inflate_pass_count():
    with pytest.raises(ValueError, match="duplicate_synthetic"):
        run_conversation_twin_gauntlet([default_scenarios()[0], default_scenarios()[0]])


@pytest.mark.parametrize("field,value,reason", [
    ("scenario_id", "not valid with spaces", "bounded_fictional"),
    ("buyer_opening", "Synthetic contact contact@example.test", "fictional_bounded"),
    ("buyer_opening", "See https://example.com/private", "fictional_bounded"),
    ("buyer_opening", "", "fictional_bounded"),
    ("buyer_reaction", "ACTUAL_PAYMENT_CONFIRMED", "known_synthetic"),
    ("expected_first_objection_code", "SECRET_PERSONALITY", "known_original"),
    ("expected_final_state", "REAL_CUSTOMER_PAID", "expected_simulated"),
    ("seller_response_override", "", "bounded_synthetic"),
])
def test_untrusted_scenario_inputs_are_rejected(field, value, reason):
    s = replace(default_scenarios()[0], **{field: value})
    with pytest.raises(ValueError, match=reason):
        rehearse_conversation(s)


def test_shared_original_objection_vocabulary_matches_scripted_rehearsal_seller():
    assert set(SELLER_SCRIPTS) == CATEGORIES
    assert len(CATEGORIES) == 8


def test_founder_summary_contains_no_dialogue_or_person_profiling():
    report = run_conversation_twin_gauntlet(default_scenarios(),
                                            show_dialogue=True)
    founder = founder_conversation_twin_status(report)
    assert founder["scenario_contract_pass_count"] == 11
    assert "simulated_dialogue" not in str(founder)
    assert "How much" not in str(founder)
    assert founder["real_world_predictive_accuracy"] is None
    assert founder["actual_revenue"] is False


@pytest.mark.parametrize("tamper", [
    {"actual_revenue": True},
    {"recognized_revenue_cents": 500},
    {"verified_buyer_conversion_count": 1},
    {"outbound_sent": True},
    {"model_weight_mutation": True},
    {"two_agents_autonomously_generating_replies": True},
    {"scenario_contract_pass_count": 12},
    {"scenario_contract_fail_count": -1},
    {"all_scenario_contracts_passed": False},
    {"mode": "LIVE"},
])
def test_forged_simulation_authority_or_counts_fail_closed(tamper):
    batch = run_conversation_twin_gauntlet(default_scenarios())
    batch.update(tamper)
    with pytest.raises(ValueError):
        founder_conversation_twin_status(batch)


def test_gauntlet_is_bounded_and_not_unlimited_self_play():
    with pytest.raises(ValueError, match="bounded_synthetic_scenario_batch"):
        run_conversation_twin_gauntlet([])
    with pytest.raises(ValueError, match="bounded_synthetic_scenario_batch"):
        run_conversation_twin_gauntlet([default_scenarios()[0]] * 25)


def test_scripted_scenarios_are_not_independent_learning_examples():
    batch = run_conversation_twin_gauntlet(default_scenarios())
    assert batch["synthetic_scenarios_are_not_real_world_validation"] is True
    assert batch["model_weight_mutation"] is False
    assert batch["real_world_predictive_accuracy"] is None
    assert founder_conversation_twin_status(None)["status"] == "NOT_RUN"


def test_original_predictive_revenue_brain_accepts_only_synthetic_twin_summary():
    from datetime import datetime, timezone
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    batch = run_conversation_twin_gauntlet(default_scenarios(), show_dialogue=True)
    review = build_predictive_revenue_brain_review(
        tenant_id="fictional-twin-simulation-only",
        as_of=datetime(2026, 10, 24, 12, tzinfo=timezone.utc),
        original_conversation_digital_twin_gauntlet=batch,
    )
    summary = review["prime_original_digital_twin_conversation_simulation"]
    assert summary["scenario_contract_pass_count"] == 11
    assert summary["status"] == "SCENARIO_CONTRACTS_PASSED"
    assert summary["real_world_predictive_accuracy"] is None
    assert "How much" not in str(summary)
    assert "FICTIONAL_BUYER_TWIN" not in str(summary)
    assert review["prime_first_buyer_intent_independently_verified"] is False
    assert review["recognized_revenue_cents"] is None
    assert review["outbound_sent"] is False
    assert review["database_writes"] is False


def test_existing_predictive_brain_does_not_invent_twin_run_when_absent():
    from datetime import datetime, timezone
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    review = build_predictive_revenue_brain_review(
        tenant_id="fictional-twin-simulation-only",
        as_of=datetime(2026, 10, 24, 12, tzinfo=timezone.utc),
    )
    assert review["prime_original_digital_twin_conversation_simulation"]["status"] == "NOT_RUN"


def test_original_brain_rejects_simulation_being_reported_as_real_revenue():
    from datetime import datetime, timezone
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    batch = run_conversation_twin_gauntlet(default_scenarios())
    batch["actual_revenue"] = True
    with pytest.raises(ValueError, match="untrusted_conversation_digital_twin"):
        build_predictive_revenue_brain_review(
            tenant_id="fictional-twin-simulation-only",
            as_of=datetime(2026, 10, 24, 12, tzinfo=timezone.utc),
            original_conversation_digital_twin_gauntlet=batch,
        )


@pytest.mark.parametrize("tamper", [
    {"actual_revenue": True},
    {"real_messages_sent": True},
    {"provider_or_tenant_authenticated": True},
    {"recognized_revenue_cents": 999},
    {"scenario_contract_pass": False},
])
def test_founder_rejects_tampered_individual_simulated_scenario(tamper):
    report = run_conversation_twin_gauntlet(default_scenarios())
    report["scenarios"][0].update(tamper)
    with pytest.raises(ValueError, match="untrusted_individual_synthetic"):
        founder_conversation_twin_status(report)


def test_founder_rejects_scenario_count_laundering():
    report = run_conversation_twin_gauntlet(default_scenarios())
    report["scenarios"] = report["scenarios"][:-1]
    with pytest.raises(ValueError, match="untrusted_individual_synthetic"):
        founder_conversation_twin_status(report)


def test_same_original_digital_twin_rehearses_five_other_sectors():
    from scripts.rehearse_prime_conversation_digital_twin_20261024 import cross_sector_scenarios
    scenarios = cross_sector_scenarios()
    assert {s.scenario_id for s in scenarios} == {
        "finance_forecast_proof", "logistics_onboarding", "travel_product_scope",
        "legal_case_privacy", "energy_solar_attribution",
    }
    out = run_conversation_twin_gauntlet(scenarios)
    assert out["scenario_count"] == 5
    assert out["all_scenario_contracts_passed"] is True
    assert out["verified_buyer_conversion_count"] is None
    assert out["real_world_predictive_accuracy"] is None
    assert out["outbound_sent"] is False


def test_all_sector_scenarios_fit_one_original_bounded_digital_twin():
    from scripts.rehearse_prime_conversation_digital_twin_20261024 import cross_sector_scenarios
    out = run_conversation_twin_gauntlet(default_scenarios() + cross_sector_scenarios())
    assert out["scenario_count"] == 16
    assert out["scenario_contract_pass_count"] == 16
    assert founder_conversation_twin_status(out)["scenario_contract_tests_passed"] is True
    assert out["recognized_revenue_cents"] is None
