"""Astra prioritises current, evidence-derived validated opportunities only.

The Ranker only reorders previously eligible internal evidence work. It never
creates buyer validation, a delivery authority, a new agent or a revenue claim.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.astra_executive import (
    CAPABILITY_COMPONENT, build_executive_snapshot, build_world_state,
)
from empire_os.astra_validated_workstream_ranking import rank_validated_workstreams
from empire_os.control_fabric import default_registry
from empire_os.departments import departments_for_component
from empire_os.opportunity_evidence_router import build_evidence_routes
from empire_os.opportunity_history import build_opportunity_history

NOW = datetime.now(timezone.utc)
BLOCK = "fulfilment_readiness_normalized_score_required"
MARKET_RESEARCH = "market:roofing:denver"
MARKET_VALIDATED = "market:roofing:austin"


def _candidate(key):
    return {
        "opportunity_key": key, "opportunity_class": "market_research",
        "niche": "roofing", "metro": key.rsplit(":", 1)[-1],
        "trigger": "observed_market_evidence",
        "offer_key": "managed_service",
    }


def _intake(key, *, validated=False, blocker=BLOCK):
    normalized = {
        "buyer_intent": {
            "semantic_class": "observed_stage",
            "observed_truth": True,
        }
    } if validated else {}
    return {
        "opportunity_key": key,
        "opportunity_class": "market_research",
        "offer_key": "managed_service",
        "evidence_count": 2,
        "factory_ready": False,
        "blockers": [blocker],
        "normalization": {"score_evidence": normalized},
    }


def _routes(*, validate=True):
    raw = build_evidence_routes(
        {"candidates": [
            _candidate(MARKET_RESEARCH),
            _candidate(MARKET_VALIDATED),
        ]},
        {"items": [
            _intake(MARKET_RESEARCH),
            _intake(MARKET_VALIDATED, validated=validate),
        ]},
    )
    raw["history"] = build_opportunity_history(raw)
    return raw


def _call(routes, *, now=None):
    specs = {item.name: item.authority for item in default_registry()}
    return rank_validated_workstreams(
        routes,
        capability_components=CAPABILITY_COMPONENT,
        component_authorities=specs,
        department_owners={
            component: departments_for_component(component)
            for component in set(CAPABILITY_COMPONENT.values())
        },
        now=now,
    )


def _world(routes, *, nba=None, quant=None):
    return build_world_state(
        predictive_status={},
        evidence_routes=routes,
        next_best_action=nba or {"actions": []},
        revenue_pulse={
            "recognized_revenue_truth": {"recognized_revenue_cents": 0}
        },
        quant_review=quant or {},
    )


def _plan(routes, *, nba=None, quant=None):
    return build_executive_snapshot(
        predictive_status={},
        evidence_routes=routes,
        next_best_action=nba or {"actions": []},
        revenue_pulse={
            "recognized_revenue_truth": {"recognized_revenue_cents": 0}
        },
        quant_review=quant or {},
    )


def test_real_router_history_ranks_validated_workstream_not_research_score():
    source = _routes()
    output = _call(source)
    assert output["status"] == "RANKED_FROM_CURRENT_DERIVED_VALIDATION"
    assert output["validated_opportunity_count"] == 1
    assert output["ranked_workstream_count"] == 1
    assert output["validated_with_existing_internal_route_count"] == 1
    assert output["route_priorities"] == [{
        "opportunity_key": MARKET_VALIDATED,
        "blocker": BLOCK,
        "target_component": "fulfilment_readiness",
        "capability": "commercial_product_catalog_and_fulfilment",
        "action": "resolve_verified_fulfilment_cost_capacity_and_runbook",
        "mode": "internal_analysis",
    }]
    workstream = output["workstreams"][0]
    assert workstream["rank"] == 1
    assert workstream["workstream"] == "fulfilment_readiness"
    assert workstream["validated_opportunity_count"] == 1
    assert workstream["opportunity_keys"] == [MARKET_VALIDATED]
    assert workstream["existing_internal_blocker_count"] == 1
    assert workstream["highest_derived_lifecycle_stage"] == "VALIDATE"
    assert workstream["authority_changed"] is False
    assert output["source_validation_is_not_buyer_acceptance"] is True
    assert output["automatic_external_execution_allowed"] is False
    assert output["commercial_authority"] == "none"
    assert output["execution_authority"] == "none"


def test_astra_plan_keeps_first_revenue_actions_then_ranks_validated_evidence():
    source = _routes()
    snap = _plan(source)
    assert snap["validated_opportunity_count"] == 1
    assert snap["validated_workstream_ranking"]["ranked_workstream_count"] == 1
    steps = [step for step in snap["plan"]
             if step["action"] == "resolve_verified_fulfilment_cost_capacity_and_runbook"]
    assert len(steps) == 2
    assert MARKET_VALIDATED in steps[0]["evidence_refs"][-1]
    assert MARKET_RESEARCH in steps[1]["evidence_refs"][-1]
    assert all(s["target_component"] == "fulfilment_readiness" for s in steps)
    assert all(s["commercial_decision_provenance"] is None for s in steps)
    assert snap["commercial_authority"] == "none"
    assert snap["external_execution_performed"] is False


def test_research_only_candidates_get_zero_ranked_promotions():
    source = _routes(validate=False)
    result = _call(source)
    assert result["validated_opportunity_count"] == 0
    assert result["route_priorities"] == []
    snap = _plan(source)
    assert snap["validated_opportunity_count"] == 0
    steps = [s for s in snap["plan"] if s["target_component"] == "fulfilment_readiness"]
    assert len(steps) == 2
    assert MARKET_RESEARCH in steps[0]["evidence_refs"][-1]


def test_untrusted_legacy_router_without_history_gets_no_priority_boost():
    source = _routes()
    del source["history"]
    result = _call(source)
    assert result["status"] == "MATCHING_CURRENT_HISTORY_REQUIRED"
    assert result["ranked_workstream_count"] == 0
    assert result["route_priorities"] == []


@pytest.mark.parametrize(("field", "value"), [
    ("mode", "EXECUTE"),
    ("execution_authority", "live"),
    ("automatic_external_execution_allowed", True),
    ("schema_version", "random.v9"),
])
def test_untrusted_current_route_snapshot_cannot_rank(field, value):
    source = _routes()
    source[field] = value
    assert _call(source)["ranked_workstream_count"] == 0


def test_current_router_snapshot_stale_or_future_never_ranks():
    source = _routes()
    assert _call(source, now=NOW + timedelta(hours=7))["route_priorities"] == []
    assert _call(source, now=NOW - timedelta(hours=1))["route_priorities"] == []


@pytest.mark.parametrize(("field", "value"), [
    ("mode", "EXECUTE"),
    ("execution_authority", "live"),
    ("commercial_stage_independently_verified", True),
    ("automatic_external_execution_allowed", True),
    ("previous_stage_never_promoted", False),
])
def test_history_cannot_import_new_authority(field, value):
    source = _routes()
    source["history"][field] = value
    assert _call(source)["status"] == "MATCHING_CURRENT_HISTORY_REQUIRED"


@pytest.mark.parametrize(("field", "value"), [
    ("active_in_latest_cycle", False),
    ("missed_cycles", 1),
    ("last_observed_stage", "PROVE"),
    ("opportunity_class", "community_pain"),
    ("tenant_id", "tenant:another"),
    ("stage_source", "INDEPENDENTLY_VERIFIED_PAYMENT"),
    ("execution_authority", "live"),
    ("last_seen_at", "2026-10-08T12:00:00+00:00"),
])
def test_stale_cross_scope_or_forged_validated_identity_cannot_rank(field, value):
    source = _routes()
    row = next(r for r in source["history"]["entries"]
               if r["opportunity_key"] == MARKET_VALIDATED)
    row[field] = value
    result = _call(source)
    assert result["status"] == "VALIDATED_LIFECYCLE_PROVENANCE_MISMATCH"
    assert result["validated_opportunity_count"] == 0


def test_ambiguous_duplicate_current_identity_aborts_ranking():
    source = _routes()
    source["items"].append(deepcopy(source["items"][-1]))
    source["opportunity_count"] = 3
    output = _call(source)
    assert output["status"] == "ROUTER_IDENTITY_DUPLICATE_OR_INVALID"
    assert output["route_priorities"] == []


def test_duplicate_history_identity_aborts_ranking():
    source = _routes()
    source["history"]["entries"].append(deepcopy(source["history"]["entries"][-1]))
    source["history"]["tracked_identity_count"] += 1
    output = _call(source)
    assert output["status"] == "ROUTER_HISTORY_IDENTITY_INVALID"


def test_route_action_must_match_canonical_existing_workstream_map():
    source = _routes()
    route = source["items"][1]["routes"][0]
    route["action"] = "send_cold_outreach_now"
    output = _call(source)
    assert output["validated_opportunity_count"] == 1
    assert output["ranked_workstream_count"] == 0
    assert output["route_priorities"] == []


def test_commercial_observation_route_does_not_rank_as_internal_evidence():
    source = _routes()
    item = source["items"][1]
    item["routes"] = [{
        "blocker": "buyer_intent_normalized_score_required",
        "capability": "conversation_os",
        "action": "observe_genuine_commercial_reply_terms_or_payment",
        "mode": "commercial_observation",
        "automatic_internal_work": True,
    }]
    output = _call(source)
    assert output["validated_opportunity_count"] == 1
    assert output["ranked_workstream_count"] == 0
    assert output["route_priorities"] == []


def test_authority_not_provided_by_existing_component_is_not_expanded():
    source = _routes()
    real = _call(source)
    assert real["ranked_workstream_count"] == 1
    specs = {item.name: item.authority for item in default_registry()}
    specs["fulfilment_readiness"] = "founder_gate"
    out = rank_validated_workstreams(
        source,
        capability_components=CAPABILITY_COMPONENT,
        component_authorities=specs,
        department_owners={
            component: departments_for_component(component)
            for component in set(CAPABILITY_COMPONENT.values())
        },
    )
    assert out["ranked_workstream_count"] == 0


def test_buyer_next_best_action_keeps_priority_over_validated_opportunity():
    source = _routes()
    buyer = {
        "actions": [{
            "entity_id": "company:1", "recommended_action": "verify_decision_maker",
            "reason": "buyer verification", "waiting_external": False,
            "founder_gate_required": False, "evidence": {},
        }],
    }
    snap = _plan(source, nba=buyer)
    assert snap["plan"][0]["action"] == "verify_decision_maker"
    assert snap["validated_opportunity_count"] == 1


def test_existing_quant_priority_remains_ahead_of_validated_opportunity():
    source = _routes()
    quant = {"missing_field_counts": {"probability_success": 1}}
    snap = _plan(source, quant=quant)
    assert snap["plan"][0]["action"] == "resolve_quant_input:probability_success"
    assert snap["validated_opportunity_count"] == 1


def test_forged_commercial_prove_stage_without_validated_flags_is_not_ranked():
    source = _routes()
    row = source["items"][1]
    row["lifecycle"]["current_stage"] = "PROVE"
    row["lifecycle"]["validated"] = True
    assert _call(source)["ranked_workstream_count"] == 0


def test_astra_ranking_can_process_zero_opportunities_without_leads():
    routes = build_evidence_routes({"candidates": []}, {"items": []})
    routes["history"] = build_opportunity_history(routes)
    result = _call(routes)
    assert result["validated_opportunity_count"] == 0
    assert result["workstreams"] == []
    assert result["commercial_authority"] == "none"



def test_ranking_does_not_move_same_signature_forged_action_ahead_of_canonical_action():
    source = _routes()
    original = source["items"][1]["routes"][0]
    manipulated = {**original, "action": "send_mail_or_post_lead_without_approval"}
    source["items"][1]["routes"] = [manipulated, original]
    snapshot = _plan(source)
    selected = [
        row for row in snapshot["plan"]
        if MARKET_VALIDATED in row["evidence_refs"][-1]
    ]
    assert selected[0]["action"] == "resolve_verified_fulfilment_cost_capacity_and_runbook"
    assert snapshot["validated_opportunity_count"] == 1
    assert snapshot["commercial_authority"] == "none"


def test_non_boolean_snapshot_count_cannot_claim_validated_candidates():
    source = _routes()
    source["opportunity_count"] = True
    result = _call(source)
    assert result["status"] == "ROUTER_ROWS_INVALID"
    assert result["route_priorities"] == []


def test_qualify_stage_with_forged_validated_flags_cannot_rank():
    source = _routes(validate=False)
    row = source["items"][1]
    row["lifecycle"]["validated"] = True
    row["lifecycle"]["commercial_validation_observed"] = True
    assert row["lifecycle"]["current_stage"] == "QUALIFY"
    result = _call(source)
    assert result["validated_opportunity_count"] == 0
    assert result["route_priorities"] == []


def test_observed_stage_needs_matching_history_timestamp():
    source = _routes()
    source["history"]["generated_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()
    result = _call(source)
    assert result["status"] == "MATCHING_CURRENT_HISTORY_REQUIRED"
    assert result["ranked_workstream_count"] == 0
