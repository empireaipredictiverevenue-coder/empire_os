"""Read-only synthetic cockpit data for the ORIGINAL EmpireOS Founder Console.

Uses pre-existing fictional scenario fixtures and original Digital Twin/PRIME
fractal+physics engine. Never calls a model, Gmail, CRM, DB, an exchange,
external transport, sender, actual buyer or learned weight.
"""
from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
from empire_os.prime_situation_awareness_shadow import (
    REQUEST_CAPABILITY, review_prime_situation, founder_situation_status,
)

from empire_os.digital_twin_conversation_rehearsal import (
    rehearse_conversation, run_conversation_twin_gauntlet,
    founder_conversation_twin_status,
)
from empire_os.digital_twin_conversation_fractal_physics import (
    run_fractal_physics_gauntlet, founder_fractal_physics_status,
)
from empire_os.digital_twin_conversation_local_selfplay import cockpit_selfplay_shadow
from scripts.rehearse_prime_conversation_digital_twin_20261024 import (
    default_scenarios, cross_sector_scenarios,
)

SCHEMA = "empire.prime.original_private_digital_twin_cockpit.v1"
ORIGINAL_FIXTURES = default_scenarios() + cross_sector_scenarios()
ALLOWED = {s.scenario_id: s for s in ORIGINAL_FIXTURES}


def build_prime_digital_twin_cockpit(
    *, scenario_id: str = "pricing_resolution", fractal_depth: int = 2,
) -> dict[str, Any]:
    if type(scenario_id) is not str or scenario_id not in ALLOWED:
        raise ValueError("original_fictional_scenario_not_allowlisted")
    if type(fractal_depth) is not int or not 0 <= fractal_depth <= 2:
        raise ValueError("bounded_interactive_fractal_depth_required")
    selected = ALLOWED[scenario_id]
    original = rehearse_conversation(selected, show_dialogue=True)
    branch = run_fractal_physics_gauntlet([selected], max_depth=fractal_depth)
    universe = run_fractal_physics_gauntlet(ORIGINAL_FIXTURES, max_depth=2)
    overall = run_conversation_twin_gauntlet(ORIGINAL_FIXTURES)
    summary = founder_conversation_twin_status(overall)
    branch_summary = founder_fractal_physics_status(branch)
    universe_summary = founder_fractal_physics_status(universe)
    # Exposes a capability COVERAGE PLAN, not a connected assistant or source.
    situation = review_prime_situation(
        situation_key="fictional_prime_cockpit",
        request_code="SIMULATE_SCENARIO",
        observations=None, as_of=datetime.now(timezone.utc),
    )
    paths = []
    for item in branch["nodes"]:
        paths.append({
            "path": item["fractal_variation_path"] or "ROOT",
            "stress": item["physical_stress_exercised"],
            "depth": item["recursive_branch_depth"],
            "simulated_state": item["simulated_original_lifecycle_state_not_real_customer"],
            "latency_ms": item["synthetic_aggregate_latency_ms"],
            "latency_budget_ms": item["synthetic_latency_budget_ms"],
            "dropped_messages": item["simulated_dropped_utterance_count"],
            "loop_guard": item["synthetic_loop_guard_status"],
            "hold_reasons": list(item["hold_reasons"]),
            "scenario_expected_logic_matched": item["original_scenario_contract_pass"],
        })
    return {
        "schema_version": SCHEMA,
        "mode": "SIMULATION",
        "environment": "ISOLATED_SYNTHETIC_RESEARCH",
        "selected_scenario_id": scenario_id,
        "selected_scenario": {
            "fictional": True,
            "original_objection_code": original["detected_original_objection_code"],
            "outcome_state_not_provider_verified": original["simulated_final_state"],
            "simulated_dialogue": original["simulated_dialogue"],
            "synthetic_turn_count": original["simulated_turn_count"],
            "loop_guard": original["synthetic_loop_guard"],
            "logic_contract_passed": original["scenario_contract_pass"],
        },
        "scenario_options": [
            {"id": s.scenario_id, "name": s.scenario_id.replace("_", " ").title()}
            for s in ORIGINAL_FIXTURES
        ],
        "fractal_depth": fractal_depth,
        "selected_fractal": {
            "total_nodes": branch_summary["synthetic_cases_executed"],
            "safety_or_causal_holds": branch_summary["expected_causal_or_policy_holds"],
            "loop_stalls": branch_summary["synthetic_loop_stalls"],
            "branches": paths,
        },
        "all_synthetic_baseline": {
            "scripted_scenarios": summary["scenario_count"],
            "scripted_contract_passes": summary["scenario_contract_pass_count"],
            "fractal_nodes_at_depth_two": universe_summary["synthetic_cases_executed"],
            "expected_safety_holds": universe_summary["expected_causal_or_policy_holds"],
            "unresolved_loop_stalls": universe_summary["synthetic_loop_stalls"],
        },
        "local_model_selfplay": cockpit_selfplay_shadow(None),
        "situational_awareness": founder_situation_status(situation),
        "assistant_capability_map": [
            {
                "request_code": key,
                "original_agi_capability_registered": capability is not None,
                "feature_live": False,
                "execution_authority": "none",
            }
            for key, capability in sorted(REQUEST_CAPABILITY.items())
        ],
        "local_model_active_in_this_read_only_request": False,
        "local_model_inference_observed_as_success": False,
        "authorization_gate": "ORIGINAL_FOUNDER_CONSOLE_OWNER_AND_PRIVATE_INGRESS_REVIEW",
        "real_world_predictive_accuracy": None,
        "real_buyer_intent_verified": False,
        "recognized_revenue_cents": None,
        "simulation_output_not_revenue_evidence": True,
        "original_empiredb_writes": False,
        "real_messages_sent": False,
        "trades_executed": False,
        "model_weights_mutated": False,
        "execution_authority": "none",
    }
