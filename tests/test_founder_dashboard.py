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
