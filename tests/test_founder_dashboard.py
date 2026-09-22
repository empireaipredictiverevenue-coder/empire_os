import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.founder_dashboard import build_founder_dashboard
from empire_os.founder_dashboard_api import create_founder_dashboard_router


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def make_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "BLUEPRINT_V6.md").write_text(
        """### Phase 3 — First Revenue — IMPLEMENTATION FROZEN / PRODUCTION PROOF GATES CARRIED FORWARD
3A Qualification ✅

### Phase 4 — Astra Operating Layer ← CURRENT
Observer ✅
Board ✅

### Phase 5 — Organic Growth Engine
Search foundation ✅
"""
    )
    write_json(
        root / "runtime/commercial_loop/latest.json",
        {
            "mode": "OBSERVE",
            "loop_complete": False,
            "blocker_state": "blocked",
            "highest_priority_blocker": "buyer_candidate_approved",
            "stages": [
                {"stage": "real_acquisition", "observed": True},
                {"stage": "buyer_candidate_approved", "observed": False},
            ],
        },
    )
    write_json(
        root / "runtime/astra/latest.json",
        {
            "mode": "OBSERVE",
            "operational_evidence": {
                "freshness": {"fresh": True, "reason": "operational_evidence_fresh"},
                "observed": {
                    "owned_inventory_count": 12189,
                    "qualified_unallocated_count": 5,
                    "active_buyer_capacity": 0,
                },
            },
            "operating_board": {
                "result": {
                    "items": [
                        {
                            "priority": 94,
                            "workstream": "source_health",
                            "recommended_job_type": "repair_real_data_sources",
                        }
                    ]
                }
            },
            "calibration": {"actual_revenue_cents": 0},
        },
    )
    write_json(
        root / "runtime/acquisition/latest.json",
        {
            "ok": True,
            "source": "overpass",
            "metro": "Austin, TX",
            "started_at": "2026-09-20T13:57:52+00:00",
            "real_data_only": True,
            "returncode": 0,
            "stdout_tail": "do not expose this log",
        },
    )
    write_json(
        root / "runtime/conversion/latest.json",
        {
            "observed_at": "2026-09-20T19:30:00+00:00",
            "mode": "OBSERVE",
            "source": "canonical_supabase",
            "min_sample_size": 20,
            "primary_bottleneck": None,
            "primary_bottleneck_rate": None,
            "experiment_candidate": None,
            "unknown_stages": ["visitor_to_lead"],
            "stages": [],
            "counts": {
                "delivered_outreach_to_reply": {
                    "entered": 5,
                    "converted": 0,
                }
            },
            "execution_authority": "none",
        },
    )
    write_json(
        root / "runtime/source_health/latest.json",
        {
            "source": "overpass",
            "metro": "Austin, TX",
            "mode": "OBSERVE",
            "endpoint_healthy": True,
            "end_to_end_healthy": False,
            "candidates_seen": 5,
            "quality_accepted": 5,
            "quality_rejected": 0,
            "canonical_writes": False,
            "blockers": ["canonical_ingest_not_authorized"],
            "errors": [],
            "observed_at": "2026-09-19T22:50:33+00:00",
        },
    )
    return root


def test_projection_separates_last_run_from_current_source_health(tmp_path):
    root = make_root(tmp_path)
    result = build_founder_dashboard(root)
    assert result["mode"] == "OBSERVE"
    assert result["acquisition"]["recorded_ok"] is True
    assert result["source_health"]["end_to_end_healthy"] is False
    assert "stdout_tail" not in result["acquisition"]
    assert result["commercial_loop"]["highest_priority_blocker"] == (
        "buyer_candidate_approved"
    )
    assert result["astra"]["observed"]["owned_inventory_count"] == 12189
    assert result["conversion"]["available"] is True
    assert result["conversion"]["counts"]["delivered_outreach_to_reply"] == {
        "entered": 5,
        "converted": 0,
    }


def test_phase_projection_marks_frozen_current_and_parallel(tmp_path):
    result = build_founder_dashboard(make_root(tmp_path))
    phases = {row["phase"]: row for row in result["phases"]}
    assert phases[3]["state"] == "implementation_frozen_proof_pending"
    assert phases[4]["state"] == "current_observe"
    assert phases[5]["state"] == "parallel_build"
    assert phases[4]["verified_markers"] == 2


def test_api_is_read_only_projection(tmp_path):
    app = FastAPI()
    app.include_router(create_founder_dashboard_router(make_root(tmp_path)))
    response = TestClient(app).get("/v1/founder-dashboard/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["side_effects"] == "none"
    assert body["execution_authority"] == "none"
    assert body["commercial_loop"]["available"] is True
    assert body["astra"]["available"] is True


def test_conversation_blocker_is_presented_as_external_wait(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root / "runtime/commercial_loop/latest.json",
        {
            "mode": "OBSERVE",
            "loop_complete": False,
            "blocker_state": "blocked",
            "highest_priority_blocker": "buyer_conversation",
            "stages": [
                {"stage": "buyer_candidate_approved", "observed": True},
                {"stage": "outbound_authorized", "observed": True},
                {"stage": "outbound_sent", "observed": True},
                {"stage": "buyer_conversation", "observed": False},
                {"stage": "commercial_terms", "observed": False},
            ],
        },
    )
    result = build_founder_dashboard(root)
    state = result["commercial_loop"]["operating_state"]
    assert state["class"] == "WAITING_EXTERNAL"
    assert state["next_event"] == "genuine_buyer_reply"
    assert state["founder_action_required"] is False


def test_dashboard_exposes_control_conveyor_and_founder_gate_state(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root / "runtime/commercial_loop/latest.json",
        {
            "mode": "OBSERVE",
            "loop_complete": False,
            "highest_priority_blocker": "commercial_terms",
            "stages": [
                {"stage": "buyer_conversation", "observed": True},
                {"stage": "commercial_terms", "observed": False},
                {"stage": "bsc_payment_request", "observed": False},
            ],
        },
    )
    result = build_founder_dashboard(root)
    assert result["control_conveyor"]["current_blocker"] == "commercial_terms"
    assert result["control_conveyor"]["authority"] == "founder_gate"
    assert result["founder_gate"] == {
        "required": True,
        "current_blocker": "commercial_terms",
        "owner_component": "commercial_terms",
        "next_event": "terms_candidate_created",
        "authority": "founder_gate",
    }


def test_dashboard_does_not_raise_founder_gate_for_external_wait(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root / "runtime/commercial_loop/latest.json",
        {
            "mode": "OBSERVE",
            "loop_complete": False,
            "highest_priority_blocker": "buyer_conversation",
            "stages": [
                {"stage": "outbound_sent", "observed": True},
                {"stage": "buyer_conversation", "observed": False},
            ],
        },
    )
    result = build_founder_dashboard(root)
    assert result["control_conveyor"]["authority"] == "internal_write"
    assert result["founder_gate"]["required"] is False



def test_dashboard_exposes_recovery_portfolio_without_commercial_authority(tmp_path):
    result = build_founder_dashboard(make_root(tmp_path))
    portfolio = result["recovery_portfolio"]
    assert portfolio["summary"]["product_count"] >= 10
    assert portfolio["summary"]["pricing_observed_count"] == 0
    assert portfolio["pricing_authority"] == "none"
    assert portfolio["execution_authority"] == "none"
    assert portfolio["actual_revenue"] is False

    rows = {row["key"]: row for row in portfolio["products"]}
    assert rows["permit_intelligence"]["state"] == "ACTIVE_BUILD"
    assert rows["property_intelligence"]["state"] == "ACTIVE_BUILD"
    assert rows["private_capital_rollup"]["state"] == "ACTIVE_BUILD"
    assert rows["oil_gas_intelligence"]["state"] == "INCUBATE"



def test_dashboard_exposes_governed_recovered_marketing_plans(tmp_path):
    result = build_founder_dashboard(make_root(tmp_path))
    portfolio = result["recovery_portfolio"]
    summary = portfolio["marketing_summary"]

    assert summary["plan_count"] >= 8
    assert summary["execution_authority"] == "none"
    assert summary["outbound_authority"] is False
    assert summary["publishing_authority"] is False
    assert summary["paid_spend_authority"] is False

    rows = {row["key"]: row for row in portfolio["marketing_plans"]}
    assert rows["permit_opportunity_gtm"]["state"] == "ACTIVE_BUILD"
    assert rows["private_capital_abm"]["state"] == "ACTIVE_BUILD"
    assert rows["oil_gas_research_gtm"]["state"] == "INCUBATE"



def test_dashboard_exposes_permit_intelligence_without_commercial_claims(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root / "runtime/acquisition/signal_inbox.json",
        {
            "permit-1": {
                "source": "permits_nyc",
                "status": "resolved",
                "metro": "NYC",
                "created_at": "2026-09-21T10:00:00+00:00",
                "last_seen_at": "2026-09-21T11:00:00+00:00",
                "url": "https://example.test/permit/1",
                "raw": {"job__": "1"},
            }
        },
    )

    result = build_founder_dashboard(root)
    permit = result["permit_intelligence"]

    assert permit["signal_count"] == 1
    assert permit["resolved_count"] == 1
    assert permit["evidence_state"] == "EVIDENCE_AVAILABLE"
    assert permit["pricing_observed"] is False
    assert permit["binding_terms_ready"] is False
    assert permit["actual_revenue"] is False
    assert permit["execution_authority"] == "none"



def test_dashboard_separates_property_evidence_from_private_capital_unknown(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root / "runtime/acquisition/signal_inbox.json",
        {
            "permit": {
                "source": "permits_nyc",
                "status": "resolved",
                "metro": "NYC",
                "created_at": "2026-09-21T10:00:00+00:00",
                "raw": {"job__": "1"},
            }
        },
    )

    result = build_founder_dashboard(root)
    prop = result["property_intelligence"]
    pe = result["private_capital_intelligence"]

    assert prop["evidence_state"] == "EVIDENCE_AVAILABLE"
    assert prop["permit_signal_count"] == 1
    assert prop["opportunity_count"] is None
    assert prop["actual_revenue"] is False

    assert pe["evidence_state"] == "UNKNOWN"
    assert pe["snapshot_available"] is False
    assert pe["deal_intent_observed"] is False
    assert pe["opportunity_count"] is None
    assert pe["actual_revenue"] is False



def test_dashboard_exposes_competitor_audience_runtime(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/competitive_intelligence/"
        / "competitor_audience_latest.json",
        {
            "schema_version": "empire.competitor_audience_runtime.v1",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "generated_at": "2026-09-22T11:00:00+00:00",
            "latest_observed_at": "2026-09-22T10:55:05+00:00",
            "canonical_signal_row_count": 3,
            "company_count": 2,
            "competitor_count": 1,
            "unique_evidence_count": 4,
            "stacked_company_count": 1,
            "max_evidence_stack": 3,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_enabled": False,
            "companies": [
                {
                    "entity_id": "entity-1",
                    "company_name": "Golden Spike Roofing Inc",
                    "company_website": "https://goldenspikeroofing.com",
                    "signal_rows": 2,
                    "competitors": ["elite-roofing-solar"],
                    "competitor_count": 1,
                    "unique_evidence_count": 3,
                    "stack_strength": 1.0,
                    "confidence": 0.9,
                    "research_candidate": True,
                    "buyer_intent": False,
                    "commercial_intent": False,
                    "outreach_enabled": False,
                    "execution_authority": "none",
                    "evidence": [],
                }
            ],
        },
    )

    result = build_founder_dashboard(root)
    audience = result["competitor_audience_intelligence"]

    assert audience["available"] is True
    assert audience["canonical_signal_row_count"] == 3
    assert audience["company_count"] == 2
    assert audience["unique_evidence_count"] == 4
    assert audience["stacked_company_count"] == 1
    assert audience["buyer_intent_inferred"] is False
    assert audience["commercial_intent_inferred"] is False
    assert audience["outreach_enabled"] is False
    assert audience["execution_authority"] == "none"



def test_dashboard_exposes_competitor_account_research(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/competitive_intelligence/"
        / "competitor_account_research_latest.json",
        {
            "schema_version": (
                "empire.competitor_account_research_batch.v1"
            ),
            "mode": "OBSERVE",
            "generated_at": "2026-09-22T12:10:00+00:00",
            "company_count": 2,
            "observation_count": 9,
            "brief_ready_count": 1,
            "additional_evidence_review_count": 1,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
            "actions": [
                {
                    "company_name": "Golden Spike Roofing Inc",
                    "research_rank": 1,
                    "requested_action": "deep_account_research",
                    "observation_count": 6,
                    "next_step": (
                        "account_research_brief_ready_for_review"
                    ),
                    "buyer_intent": False,
                    "commercial_intent": False,
                    "outreach_enabled": False,
                    "execution_authority": "none",
                }
            ],
        },
    )

    result = build_founder_dashboard(root)
    research = result["competitor_account_research"]

    assert research["available"] is True
    assert research["company_count"] == 2
    assert research["observation_count"] == 9
    assert research["brief_ready_count"] == 1
    assert research["buyer_intent_inferred"] is False
    assert research["commercial_intent_inferred"] is False
    assert research["outreach_enabled"] is False
    assert research["execution_authority"] == "none"



def test_dashboard_exposes_claim_critic_account_briefs(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/competitive_intelligence/"
        / "competitor_account_briefs_latest.json",
        {
            "schema_version": "empire.account_intelligence_brief_batch.v1",
            "mode": "OBSERVE",
            "brief_count": 1,
            "supported_claim_count": 3,
            "blocked_claim_count": 0,
            "all_published_claims_supported": True,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_enabled": False,
            "actual_revenue": False,
            "execution_authority": "none",
            "briefs": [{
                "entity_id": "entity-1",
                "company_name": "Golden Spike Roofing Inc",
                "claim_critic": {
                    "reviewed_count": 3,
                    "supported_count": 3,
                    "blocked_count": 0,
                    "all_published_claims_supported": True,
                    "blocked_claims": [],
                },
            }],
        },
    )

    result = build_founder_dashboard(root)
    briefs = result["competitor_account_briefs"]

    assert briefs["available"] is True
    assert briefs["brief_count"] == 1
    assert briefs["supported_claim_count"] == 3
    assert briefs["blocked_claim_count"] == 0
    assert briefs["all_published_claims_supported"] is True
    assert briefs["buyer_intent_inferred"] is False
    assert briefs["commercial_intent_inferred"] is False
    assert briefs["outreach_enabled"] is False
    assert briefs["actual_revenue"] is False
    assert briefs["execution_authority"] == "none"



def test_dashboard_exposes_buyer_state_evidence(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/buyer_state/"
        / "buyer_state_latest.json",
        {
            "schema_version": "empire.buyer_state_evidence_snapshot.v1",
            "mode": "OBSERVE",
            "entity_count": 2,
            "states": [
                "DISCOVERED",
                "ICP_MATCH",
                "SIGNAL_ACTIVE",
                "RESEARCHED",
                "READY",
                "CONTACTED",
                "ENGAGED",
                "CONVERSATION",
                "COMMERCIAL_INTENT",
                "TERMS",
                "PAYMENT_PENDING",
                "PAID",
                "FULFILLED",
                "EXPANSION",
            ],
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
            "entities": [
                {
                    "entity_id": "entity-1",
                    "company_name": "Golden Spike Roofing Inc",
                    "current_factual_state": "RESEARCHED",
                    "states": [],
                },
                {
                    "entity_id": "entity-2",
                    "company_name": "Colorado's Best Roofing",
                    "current_factual_state": "READY",
                    "states": [],
                },
            ],
        },
    )

    result = build_founder_dashboard(root)
    buyer_state = result["buyer_state_evidence"]

    assert buyer_state["available"] is True
    assert buyer_state["entity_count"] == 2
    assert buyer_state["buyer_intent_inferred"] is False
    assert buyer_state["commercial_intent_inferred"] is False
    assert buyer_state["outreach_enabled"] is False
    assert buyer_state["execution_authority"] == "none"



def test_dashboard_exposes_next_best_actions(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/next_best_action/"
        / "next_best_action_latest.json",
        {
            "schema_version": "empire.next_best_action_snapshot.v1",
            "mode": "OBSERVE",
            "action_count": 2,
            "founder_gate_count": 0,
            "waiting_external_count": 0,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_authorized": False,
            "payment_authorized": False,
            "execution_authority": "none",
            "actions": [
                {
                    "entity_id": "entity-1",
                    "company_name": "Golden Spike Roofing Inc",
                    "recommended_action": "research_more",
                    "mutation_authorized": False,
                    "external_execution_authorized": False,
                },
                {
                    "entity_id": "entity-2",
                    "company_name": "Colorado's Best Roofing",
                    "recommended_action": "verify_decision_maker",
                    "mutation_authorized": False,
                    "external_execution_authorized": False,
                },
            ],
        },
    )

    result = build_founder_dashboard(root)
    nba = result["next_best_actions"]

    assert nba["available"] is True
    assert nba["action_count"] == 2
    assert nba["founder_gate_count"] == 0
    assert nba["buyer_intent_inferred"] is False
    assert nba["commercial_intent_inferred"] is False
    assert nba["outreach_authorized"] is False
    assert nba["payment_authorized"] is False
    assert nba["execution_authority"] == "none"



def test_dashboard_exposes_account_buyer_digital_twins(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/account_twin/"
        / "account_twin_latest.json",
        {
            "schema_version": (
                "empire.account_buyer_digital_twin_snapshot.v1"
            ),
            "mode": "OBSERVE",
            "twin_count": 2,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_authorized": False,
            "payment_authorized": False,
            "execution_authority": "none",
            "twins": [
                {
                    "entity_id": "entity-1",
                    "identity": {
                        "company_name": "Golden Spike Roofing Inc"
                    },
                    "buyer_state": {
                        "current_factual_state": "RESEARCHED"
                    },
                    "uncertainty": {
                        "explicit": True,
                        "items": ["commercial_intent_not_observed"],
                    },
                },
                {
                    "entity_id": "entity-2",
                    "identity": {
                        "company_name": "Colorado's Best Roofing"
                    },
                    "buyer_state": {
                        "current_factual_state": "READY"
                    },
                    "uncertainty": {
                        "explicit": True,
                        "items": ["commercial_intent_not_observed"],
                    },
                },
            ],
        },
    )

    result = build_founder_dashboard(root)
    twins = result["account_buyer_digital_twins"]

    assert twins["available"] is True
    assert twins["twin_count"] == 2
    assert twins["buyer_intent_inferred"] is False
    assert twins["commercial_intent_inferred"] is False
    assert twins["outreach_authorized"] is False
    assert twins["payment_authorized"] is False
    assert twins["execution_authority"] == "none"



def test_dashboard_exposes_cortex_learning_loop(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/cortex_learning/"
        / "cortex_learning_latest.json",
        {
            "schema_version": "empire.cortex_learning_snapshot.v1",
            "mode": "OBSERVE",
            "packet_count": 2,
            "learning_ready_count": 0,
            "verified_customer_learning_count": 0,
            "reply_observed_count": 0,
            "forecast_used_as_outcome": False,
            "synthetic_commercial_label_count": 0,
            "model_weight_mutation_authorized": False,
            "execution_authority": "none",
            "packets": [
                {
                    "entity_id": "entity-1",
                    "company_name": "Golden Spike Roofing Inc",
                    "learning_ready": False,
                    "verified_customer_learning": False,
                    "label": {
                        "available": False,
                        "blockers": [
                            "verified_commercial_outcome_missing"
                        ],
                    },
                },
                {
                    "entity_id": "entity-2",
                    "company_name": "Colorado's Best Roofing",
                    "learning_ready": False,
                    "verified_customer_learning": False,
                    "label": {
                        "available": False,
                        "blockers": [
                            "verified_commercial_outcome_missing"
                        ],
                    },
                },
            ],
        },
    )

    result = build_founder_dashboard(root)
    cortex = result["cortex_learning_loop"]

    assert cortex["available"] is True
    assert cortex["packet_count"] == 2
    assert cortex["learning_ready_count"] == 0
    assert cortex["verified_customer_learning_count"] == 0
    assert cortex["forecast_used_as_outcome"] is False
    assert cortex["synthetic_commercial_label_count"] == 0
    assert cortex["model_weight_mutation_authorized"] is False
    assert cortex["execution_authority"] == "none"



def test_dashboard_exposes_competitor_market_scale(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/competitive_intelligence/"
        / "competitor_market_scale_latest.json",
        {
            "schema_version": "empire.competitor_market_scale.v1",
            "mode": "OBSERVE",
            "market_key": "denver-co-roofing",
            "configured_competitor_count": 9,
            "executed_competitor_count": 9,
            "company_count": 4,
            "unique_evidence_count": 12,
            "shared_audience_edge_count": 3,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "market_share_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
        },
    )

    result = build_founder_dashboard(root)
    scale = result["competitor_market_scale"]

    assert scale["available"] is True
    assert scale["market_key"] == "denver-co-roofing"
    assert scale["configured_competitor_count"] == 9
    assert scale["executed_competitor_count"] == 9
    assert scale["company_count"] == 4
    assert scale["unique_evidence_count"] == 12
    assert scale["shared_audience_edge_count"] == 3
    assert scale["buyer_intent_inferred"] is False
    assert scale["commercial_intent_inferred"] is False
    assert scale["market_share_inferred"] is False
    assert scale["outreach_enabled"] is False
    assert scale["execution_authority"] == "none"



def test_dashboard_exposes_competitor_market_opportunity(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/competitive_intelligence/"
        / "competitor_market_opportunity_latest.json",
        {
            "schema_version": "empire.competitor_market_opportunity.v1",
            "mode": "OBSERVE",
            "market_key": "denver-co-roofing",
            "resolved_company_count": 5,
            "observed_company_count": 1,
            "research_gap_company_count": 4,
            "underserved_audience_candidates": [
                {
                    "entity_id": "entity-colorado",
                    "company_name": "Colorado's Best Roofing",
                    "observed_evidence_count": 0,
                    "underserved_demand_inferred": False,
                    "revenue_opportunity_inferred": False,
                }
            ],
            "territory_heatmap": [{
                "metro": "denver, co",
                "resolved_company_count": 5,
                "company_with_competitor_evidence_count": 1,
                "company_without_competitor_evidence_count": 4,
                "evidence_coverage_ratio": 0.2,
                "heat_metric": "competitor_evidence_coverage_gap",
                "demand_heat_inferred": False,
            }],
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "market_share_inferred": False,
            "revenue_opportunity_inferred": False,
            "execution_authority": "none",
        },
    )

    result = build_founder_dashboard(root)
    market = result["competitor_market_opportunity"]

    assert market["available"] is True
    assert market["resolved_company_count"] == 5
    assert market["observed_company_count"] == 1
    assert market["research_gap_company_count"] == 4
    assert len(market["territory_heatmap"]) == 1
    assert market["buyer_intent_inferred"] is False
    assert market["commercial_intent_inferred"] is False
    assert market["market_share_inferred"] is False
    assert market["revenue_opportunity_inferred"] is False
    assert market["execution_authority"] == "none"



def test_dashboard_exposes_competitor_ecosystem(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/competitive_intelligence/"
        / "competitor_ecosystem_latest.json",
        {
            "schema_version": "empire.competitor_ecosystem_snapshot.v1",
            "mode": "OBSERVE",
            "company_count": 14,
            "homepage_observed_count": 10,
            "case_study_company_count": 4,
            "testimonial_company_count": 5,
            "partner_surface_company_count": 6,
            "surface_count": 22,
            "external_relationship_candidate_count": 7,
            "customer_relationship_inferred": False,
            "partner_relationship_inferred": False,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
            "companies": [],
        },
    )

    result = build_founder_dashboard(root)
    eco = result["competitor_ecosystem"]

    assert eco["available"] is True
    assert eco["company_count"] == 14
    assert eco["case_study_company_count"] == 4
    assert eco["testimonial_company_count"] == 5
    assert eco["partner_surface_company_count"] == 6
    assert eco["external_relationship_candidate_count"] == 7
    assert eco["buyer_intent_inferred"] is False
    assert eco["commercial_intent_inferred"] is False
    assert eco["outreach_enabled"] is False
    assert eco["execution_authority"] == "none"



def test_dashboard_exposes_competitor_public_review_overlap(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/competitive_intelligence/"
        / "competitor_public_review_overlap_latest.json",
        {
            "schema_version": "empire.competitor_public_review_overlap.v1",
            "mode": "OBSERVE",
            "company_count": 14,
            "company_with_review_profile_count": 8,
            "review_profile_count": 12,
            "review_platform_count": 4,
            "company_overlap_edge_count": 9,
            "review_platforms": [{
                "platform": "bbb",
                "company_count": 5,
                "companies": ["A", "B", "C", "D", "E"],
            }],
            "company_overlap_edges": [],
            "review_sentiment_inferred": False,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "market_share_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
        },
    )

    result = build_founder_dashboard(root)
    reviews = result["competitor_public_review_overlap"]

    assert reviews["available"] is True
    assert reviews["company_count"] == 14
    assert reviews["company_with_review_profile_count"] == 8
    assert reviews["review_profile_count"] == 12
    assert reviews["review_platform_count"] == 4
    assert reviews["company_overlap_edge_count"] == 9
    assert reviews["review_sentiment_inferred"] is False
    assert reviews["buyer_intent_inferred"] is False
    assert reviews["market_share_inferred"] is False
    assert reviews["execution_authority"] == "none"



def test_dashboard_exposes_competitor_search_presence(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/competitive_intelligence/"
        / "competitor_search_presence_latest.json",
        {
            "schema_version": "empire.competitor_search_presence.v1",
            "mode": "OBSERVE",
            "query_count": 6,
            "query_with_results_count": 5,
            "query_with_market_company_count": 4,
            "canonical_company_count": 14,
            "company_with_search_presence_count": 6,
            "observation_count": 12,
            "search_presence_available": True,
            "share_metric":
                "reciprocal_position_weighted_observed_search_presence",
            "market_share": None,
            "market_share_inferred": False,
            "demand_inferred": False,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
            "companies": [],
        },
    )

    result = build_founder_dashboard(root)
    search = result["competitor_search_presence"]

    assert search["available"] is True
    assert search["query_count"] == 6
    assert search["canonical_company_count"] == 14
    assert search["company_with_search_presence_count"] == 6
    assert search["observation_count"] == 12
    assert search["search_presence_available"] is True
    assert search["market_share"] is None
    assert search["market_share_inferred"] is False
    assert search["demand_inferred"] is False
    assert search["buyer_intent_inferred"] is False
    assert search["execution_authority"] == "none"



def test_dashboard_exposes_competitor_public_activity(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/competitive_intelligence/"
        / "competitor_public_activity_latest.json",
        {
            "schema_version": "empire.competitor_public_activity.v1",
            "mode": "OBSERVE",
            "company_count": 14,
            "homepage_observed_count": 14,
            "company_with_activity_count": 9,
            "observation_count": 20,
            "ads_offers_creative_company_count": 4,
            "hiring_company_count": 3,
            "event_company_count": 2,
            "public_activity_company_count": 7,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "market_share_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
            "companies": [],
        },
    )

    result = build_founder_dashboard(root)
    activity = result["competitor_public_activity"]

    assert activity["available"] is True
    assert activity["company_count"] == 14
    assert activity["company_with_activity_count"] == 9
    assert activity["ads_offers_creative_company_count"] == 4
    assert activity["hiring_company_count"] == 3
    assert activity["event_company_count"] == 2
    assert activity["public_activity_company_count"] == 7
    assert activity["buyer_intent_inferred"] is False
    assert activity["market_share_inferred"] is False
    assert activity["execution_authority"] == "none"



def test_dashboard_exposes_competitor_intelligence_feed(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root
        / "runtime/competitive_intelligence/"
        / "competitor_intelligence_feed_latest.json",
        {
            "schema_version": "empire.competitor_intelligence_feed.v1",
            "mode": "OBSERVE",
            "niche": "roofing",
            "metro": "denver, co",
            "canonical_company_count": 14,
            "feed_targets": [
                "tam_market_intelligence",
                "revenue_gps",
                "gtm",
                "search_intelligence",
            ],
            "tam": {
                "canonical_company_count": 14,
                "tam_size_inferred": False,
            },
            "revenue_gps": {
                "companies_with_research_context": 12,
                "demand_inferred": False,
                "revenue_opportunity_inferred": False,
            },
            "gtm": {
                "market_context_only": True,
                "prospect_created": False,
                "outreach_enabled": False,
                "execution_authority": "none",
            },
            "search_intelligence": {
                "canonical_competitor_domain_count": 14,
                "competitor_gap_inputs_available": True,
                "share_of_voice_available": False,
                "market_share_inferred": False,
            },
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "demand_inferred": False,
            "market_share_inferred": False,
            "revenue_opportunity_inferred": False,
            "prospect_created": False,
            "outreach_enabled": False,
            "execution_authority": "none",
        },
    )

    result = build_founder_dashboard(root)
    feed = result["competitor_intelligence_feed"]

    assert feed["available"] is True
    assert feed["canonical_company_count"] == 14
    assert feed["tam"]["canonical_company_count"] == 14
    assert feed["revenue_gps"]["demand_inferred"] is False
    assert feed["gtm"]["prospect_created"] is False
    assert feed["search_intelligence"][
        "competitor_gap_inputs_available"
    ] is True
    assert feed["execution_authority"] == "none"



def test_dashboard_exposes_real_commercial_funnel(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root / "runtime/commercial_funnel/latest.json",
        {
            "schema_version": "empire.founder_commercial_funnel.v1",
            "generated_at": "2026-09-22T15:00:00+00:00",
            "counts": {
                "prospect_acquisitions": 493,
                "buyer_reviews": 34,
                "buyer_reviews_approved": 32,
                "outbound_intents": 31,
                "outbound_delivered": 25,
                "commercial_replies": 0,
                "unsubscribe_replies": 1,
                "closer_cases": 0,
                "commercial_terms_reviews": 0,
                "commercial_terms_approved": 0,
                "payment_requests": 0,
                "verified_payment_evidence": 0,
                "fulfilment_orders": 0,
                "fulfilled_orders": 0,
                "commercial_outcomes": 0,
                "recognized_revenue_events": 0,
            },
            "outbound_status_counts": {"delivered": 25},
            "reply_classification_counts": {"unsubscribe": 1},
            "recognized_revenue_cents": 0,
            "realized_margin_cents": 0,
            "actual_revenue": False,
            "execution_authority": "none",
        },
    )

    result = build_founder_dashboard(root)
    funnel = result["commercial_funnel"]

    assert funnel["available"] is True
    assert funnel["counts"]["prospect_acquisitions"] == 493
    assert funnel["counts"]["outbound_delivered"] == 25
    assert funnel["current_stage"] == "outbound_delivered"
    assert funnel["next_event"] == "await_genuine_buyer_reply"
    assert funnel["actual_revenue"] is False
    assert funnel["execution_authority"] == "none"



def test_dashboard_exposes_revenue_pulse(tmp_path):
    root = make_root(tmp_path)
    write_json(
        root / "runtime/revenue_pulse/latest.json",
        {
            "schema_version": "empire.revenue-pulse.v3",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "pulse_state": "conversation_blocked",
            "highest_priority_blocker": "buyer_conversation",
            "blocker_state": "blocked",
            "current_window": {
                "label": "current_24h",
                "hours": 24,
                "acquisitions": 20,
                "qualified": 10,
                "buyer_reviews": 5,
                "delivered_outreach": 4,
                "commercial_replies": 0,
                "commercial_terms": 0,
                "verified_payments": 0,
                "fulfilments": 0,
                "recognized_revenue_cents": 0,
                "realized_gp_cents": 0,
                "evidence_refs": ["canonical:current"],
            },
            "conversion": {
                "delivered_outreach_to_commercial_reply": 0.0,
            },
            "leak_detection": {
                "method": "observed_zero_conversion_only",
                "prediction": False,
                "items": [{
                    "from_stage": "delivered_outreach",
                    "to_stage": "commercial_replies",
                    "entered": 4,
                    "converted": 0,
                    "state": "observed_zero_conversion",
                    "prediction": False,
                }],
            },
            "alerts": [{
                "kind": "conversion_gap",
                "stage": "commercial_replies",
                "prediction": False,
            }],
            "recognized_revenue_truth": {
                "recognized_revenue_cents": 0,
                "realized_gp_cents": 0,
                "forecast_included_in_truth": False,
            },
            "forecast": {
                "separate_from_revenue_truth": True,
                "items": [],
            },
        },
    )

    result = build_founder_dashboard(root)
    pulse = result["revenue_pulse"]

    assert pulse["available"] is True
    assert pulse["pulse_state"] == "conversation_blocked"
    assert pulse["current_window"]["delivered_outreach"] == 4
    assert pulse["current_window"]["commercial_replies"] == 0
    assert pulse["leak_detection"]["prediction"] is False
    assert pulse["alerts"][0]["stage"] == "commercial_replies"
    assert pulse["recognized_revenue_truth"][
        "recognized_revenue_cents"
    ] == 0
    assert pulse["recognized_revenue_truth"][
        "forecast_included_in_truth"
    ] is False
    assert pulse["execution_authority"] == "none"
