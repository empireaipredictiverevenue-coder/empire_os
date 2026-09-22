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
