"""Original Digital Twin multiscale scenario and synthetic transport invariants."""
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from empire_os.digital_twin_conversation_fractal_physics import (
    SyntheticChannelEnvelope, simulate_conversation_channel,
    run_fractal_physics_gauntlet, founder_fractal_physics_status,
    MAX_NODES,
)
from scripts.rehearse_prime_conversation_digital_twin_20261024 import (
    default_scenarios, cross_sector_scenarios,
)

ROOTS = default_scenarios()


def test_binary_recursive_expansion_has_exact_node_conservation():
    for depth, count in [(0, 11), (1, 33), (2, 77)]:
        packet = run_fractal_physics_gauntlet(ROOTS, max_depth=depth)
        assert packet["fractal_branch_factor"] == 2
        assert packet["expected_recursive_nodes"] == count
        assert packet["simulated_total_nodes"] == count
        assert packet["original_scenario_logic_failure_count"] == 0
        assert packet["all_original_scenario_contracts_passed"] is True
        assert packet["simulation_only"] is True
        assert packet["recognized_revenue_cents"] is None
        assert packet["real_world_predictive_accuracy"] is None
        assert packet["model_weight_mutation"] is False
        assert packet["empiredb_writes"] is False


def test_branch_path_prefixes_are_self_similar():
    result = run_fractal_physics_gauntlet(ROOTS[:1], max_depth=3)
    paths = [r["fractal_variation_path"] for r in result["nodes"]]
    assert set(paths) == {
        "", "L", "D", "LL", "LD", "DL", "DD",
        "LLL", "LLD", "LDL", "LDD", "DLL", "DLD", "DDL", "DDD",
    }
    assert sum(1 for p in paths if len(p) == 0) == 1
    assert sum(1 for p in paths if len(p) == 1) == 2
    assert sum(1 for p in paths if len(p) == 2) == 4
    assert sum(1 for p in paths if len(p) == 3) == 8


def test_77_original_conversation_cases_include_expected_stress_holds():
    packet = run_fractal_physics_gauntlet(ROOTS, max_depth=2)
    founder = founder_fractal_physics_status(packet)
    assert founder["synthetic_cases_executed"] == 77
    assert founder["synthetic_contract_failures"] == 0
    assert founder["expected_causal_or_policy_holds"] >= 44
    assert founder["real_world_predictive_accuracy"] is None
    assert founder["actual_revenue"] is False
    assert "How much" not in str(founder)


def test_16_cross_sector_and_original_cases_stay_one_shared_twin():
    roots = ROOTS + cross_sector_scenarios()
    packet = run_fractal_physics_gauntlet(roots, max_depth=2)
    assert len(roots) == 16
    assert packet["simulated_total_nodes"] == 112
    assert packet["original_scenario_logic_failure_count"] == 0
    assert packet["outbound_sent"] is False


def test_lost_seller_response_cannot_be_reinterpreted_as_buyer_confirmation():
    result = simulate_conversation_channel(
        ROOTS[0],
        envelope=SyntheticChannelEnvelope(
            drop_turn_indices=(1,), jitter_bound_ms=0,
        ),
    )
    assert result["simulated_utterance_count"] == 3
    assert result["simulated_dropped_utterance_count"] == 1
    assert result["simulated_delivered_utterance_count"] == 2
    assert result["synthetic_event_timing_causal"] is False
    assert result["simulation_status"] == "TRANSPORT_AND_POLICY_HOLD"
    assert "synthetic_message_loss_breaks_causal_conversation" in result["hold_reasons"]
    assert result["no_objection_resolution_credited_if_delivery_failed"] is True
    assert result["no_claim_of_actual_person_confirmation"] is True


def test_dropped_initial_buyer_objection_blocks_seller_evidence():
    result = simulate_conversation_channel(
        ROOTS[0],
        envelope=SyntheticChannelEnvelope(drop_turn_indices=(0,)),
    )
    assert result["simulation_status"] == "TRANSPORT_AND_POLICY_HOLD"
    assert result["synthetic_event_timing_causal"] is False
    assert result["actual_revenue"] is False


def test_physical_transport_timeouts_preserve_causality_hold():
    result = simulate_conversation_channel(
        ROOTS[0],
        envelope=SyntheticChannelEnvelope(
            one_way_latency_ms=500, jitter_bound_ms=0, timeout_budget_ms=800,
        ),
    )
    assert result["synthetic_aggregate_latency_ms"] == 1500
    assert result["simulation_status"] == "TRANSPORT_AND_POLICY_HOLD"
    assert "synthetic_transport_time_budget_exceeded" in result["hold_reasons"]
    assert result["synthetic_event_timing_causal"] is False
    assert result["recognized_revenue_cents"] is None


def test_latency_at_exact_budget_is_not_marked_as_timeout():
    result = simulate_conversation_channel(
        ROOTS[0],
        envelope=SyntheticChannelEnvelope(
            one_way_latency_ms=100, jitter_bound_ms=0, timeout_budget_ms=300,
        ),
    )
    assert result["synthetic_aggregate_latency_ms"] == 300
    assert result["synthetic_event_timing_causal"] is True
    assert result["hold_reasons"] == []


def test_deterministic_seed_replays_identical_jitter_for_same_case():
    profile = SyntheticChannelEnvelope(one_way_latency_ms=40,
                                       jitter_bound_ms=100, seed=504)
    a = simulate_conversation_channel(ROOTS[0], envelope=profile)
    b = simulate_conversation_channel(ROOTS[0], envelope=profile)
    assert a == b
    assert 120 <= a["synthetic_aggregate_latency_ms"] <= 420


def test_transport_disallows_unbounded_or_duplicate_drop_indices():
    for profile in (
        SyntheticChannelEnvelope(one_way_latency_ms=-1),
        SyntheticChannelEnvelope(jitter_bound_ms=-1),
        SyntheticChannelEnvelope(timeout_budget_ms=0),
        SyntheticChannelEnvelope(seed=-1),
        SyntheticChannelEnvelope(drop_turn_indices=(1, 1)),
        SyntheticChannelEnvelope(drop_turn_indices=(6,)),
        SyntheticChannelEnvelope(drop_turn_indices=(True,)),
    ):
        with pytest.raises(ValueError, match="bounded_dimensionally"):
            simulate_conversation_channel(ROOTS[0], envelope=profile)


def test_optout_never_creates_seller_message_even_under_packet_loss():
    optout = next(s for s in ROOTS if s.scenario_id == "explicit_optout")
    result = simulate_conversation_channel(
        optout, envelope=SyntheticChannelEnvelope(drop_turn_indices=(0,)),
    )
    assert result["simulated_utterance_count"] == 1
    assert result["simulated_delivered_utterance_count"] == 0
    assert result["simulation_status"] == "TRANSPORT_AND_POLICY_HOLD"
    assert result["simulated_original_lifecycle_state_not_real_customer"] == "SIMULATED_OPTED_OUT"
    assert result["real_messages_sent"] is False


def test_quote_injection_does_not_turn_a_base_price_question_into_optout():
    packet = run_fractal_physics_gauntlet(ROOTS[:1], max_depth=1)
    injected = next(n for n in packet["nodes"] if n["fractal_variation_path"] == "D")
    assert injected["original_objection_code"] == "PRICE_OR_BUDGET_QUESTION"
    assert injected["original_scenario_contract_pass"] is True
    assert injected["simulation_status"] == "TRANSPORT_AND_POLICY_HOLD"
    assert injected["recognized_revenue_cents"] is None


def test_policy_block_survives_multiscale_expansion():
    bad = next(s for s in ROOTS if s.scenario_id == "unsupported_guarantee_blocked")
    packet = run_fractal_physics_gauntlet([bad], max_depth=2)
    assert all(n["scripted_seller_policy_held"] is True for n in packet["nodes"])
    assert all(n["simulation_status"] == "TRANSPORT_AND_POLICY_HOLD" for n in packet["nodes"])
    assert all(n["actual_revenue"] is False for n in packet["nodes"])


def test_fractal_node_budget_limits_explosion():
    with pytest.raises(ValueError, match="bounded_fractal_node_budget"):
        run_fractal_physics_gauntlet(ROOTS, max_depth=3)
    with pytest.raises(ValueError, match="bounded_fractal_depth"):
        run_fractal_physics_gauntlet([ROOTS[0]], max_depth=8)
    with pytest.raises(ValueError, match="bounded_original_fictional_roots"):
        run_fractal_physics_gauntlet(ROOTS + cross_sector_scenarios() + ROOTS, max_depth=0)
    with pytest.raises(ValueError, match="fractal_gauntlet_requires_drop_free_baseline"):
        run_fractal_physics_gauntlet([ROOTS[0]],
                                    envelope=SyntheticChannelEnvelope(drop_turn_indices=(0,)))


def test_duplicate_root_blocks_fractal_coverage_inflation():
    with pytest.raises(ValueError, match="replayed_fictional_fractal_root"):
        run_fractal_physics_gauntlet([ROOTS[0], ROOTS[0]], max_depth=0)


def test_founder_unknown_when_not_run_is_not_failure_or_customer_validation():
    status = founder_fractal_physics_status(None)
    assert status["status"] == "NOT_RUN"
    assert status["synthetic_cases_executed"] is None
    assert status["real_world_predictive_accuracy"] is None
    assert status["execution_authority"] == "none"


@pytest.mark.parametrize("tamper", [
    {"actual_revenue": True},
    {"recognized_revenue_cents": 1500},
    {"verified_buyer_conversion_count": 1},
    {"outbound_sent": True},
    {"model_weight_mutation": True},
    {"empiredb_writes": True},
    {"simulation_only": False},
    {"real_world_predictive_accuracy": 0.98},
    {"simulated_total_nodes": 900},
    {"all_original_scenario_contracts_passed": False},
    {"original_scenario_logic_failure_count": 3},
])
def test_fractal_founder_rejects_forged_commercial_or_contract_claim(tamper):
    report = run_fractal_physics_gauntlet(ROOTS[:1], max_depth=1)
    report.update(tamper)
    with pytest.raises(ValueError):
        founder_fractal_physics_status(report)


@pytest.mark.parametrize("child_tamper", [
    {"actual_revenue": True},
    {"recognized_revenue_cents": 450},
    {"verified_buyer_conversion_count": 1},
    {"real_messages_sent": True},
    {"model_weight_mutation": True},
    {"original_scenario_contract_pass": False},
])
def test_fractal_founder_checks_child_rehearsal_claims(child_tamper):
    report = run_fractal_physics_gauntlet(ROOTS[:1], max_depth=1)
    report["nodes"][0].update(child_tamper)
    with pytest.raises(ValueError):
        founder_fractal_physics_status(report)


def test_fractal_uses_original_prime_brain_and_never_claims_sales():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    packet = run_fractal_physics_gauntlet(ROOTS, max_depth=2)
    brain = build_predictive_revenue_brain_review(
        tenant_id="fictional_twin_only",
        as_of=datetime(2026, 10, 24, tzinfo=timezone.utc),
        original_fractal_physics_conversation_gauntlet=packet,
    )
    status = brain["prime_original_fractal_physics_conversation_simulation"]
    assert status["synthetic_cases_executed"] == 77
    assert status["synthetic_contract_failures"] == 0
    assert status["real_world_predictive_accuracy"] is None
    assert brain["prime_first_buyer_intent_independently_verified"] is False
    assert brain["recognized_revenue_cents"] is None
    assert brain["database_writes"] is False


def test_original_brain_fractal_source_absent_is_not_an_implicit_run():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    review = build_predictive_revenue_brain_review(
        tenant_id="fictional_twin_only",
        as_of=datetime(2026, 10, 24, tzinfo=timezone.utc),
    )
    assert review["prime_original_fractal_physics_conversation_simulation"]["status"] == "NOT_RUN"
