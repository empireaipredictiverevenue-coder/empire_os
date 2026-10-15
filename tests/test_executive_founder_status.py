from datetime import datetime, timedelta, timezone
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.executive_founder_status import read_executive_founder_status
from empire_os.founder_ops_api import create_founder_ops_router
from empire_os.founder_dashboard_service import build_founder_dashboard_service

NOW = datetime(2026, 10, 15, 13, 15, tzinfo=timezone.utc)


def plan():
    return {
        "schema_version": "empire.astra.executive.v2",
        "mode": "OBSERVE",
        "generated_at": NOW.isoformat(),
        "executive_commercial_roles": {
            "schema_version": "empire.executive.commercial_observer.v1",
            "mode": "OBSERVE",
            "as_of": NOW.isoformat(),
            "execution_authority": "none",
            "outbound_enabled": False,
            "production_changes": False,
            "review_state": "HISTORICAL_REVIEW_ONLY",
            "observed_systemd": {
                "department_cycle": "FAILED", "astra_dispatcher": "SUCCEEDED"
            },
            "opportunity_proof": {"status": "STALE"},
            "founder_mailbox_observer": {"status": "ERROR"},
            "existing_relationship_registry": {
                "status": "GMAIL_SNAPSHOT_HOLD",
                "total_relationships": 238,
                "suppression_review_count": 9,
                "mailbox_current": False,
                "review_queue": [
                    {"company": "Person A", "email": "private@example.com"}
                ],
            },
            "review": {
                "chief_of_staff": {
                    "top_three_next_actions": [
                        {
                            "owner": "coo",
                            "action": "RESTORE_VERIFIED_DEPARTMENT_FINALISATION",
                            "external_action_authorized": False,
                            "evidence_refs": ["journal:ops"],
                        },
                        {
                            "owner": "business_development",
                            "action": "OBTAIN_HUMAN_BUYING_BRIEF",
                            "partner": "AceLeads",
                            "external_action_authorized": False,
                        },
                    ],
                },
                "coo": {"tasks": [{"action": "INCIDENT"}]},
            },
        },
    }


def read(tmp_path, document=None):
    path = tmp_path / "astra_latest.json"
    path.write_text(json.dumps(plan() if document is None else document))
    return read_executive_founder_status(path, as_of=NOW)


def test_safe_dashboard_projection_shows_actual_gates_only(tmp_path):
    status = read(tmp_path)
    assert status["available"] is True
    assert status["status"] == "EVIDENCE_HOLD"
    assert status["coo"]["opportunity_proof"] == "STALE"
    assert status["coo"]["mailbox_observer"] == "ERROR"
    assert status["business_development"]["existing_relationship_count"] == 238
    assert status["business_development"]["suppression_review_count"] == 9
    assert status["business_development"]["mailbox_current"] is False
    assert [row["owner"] for row in status["chief_of_staff"]["top_three_review_actions"]] == [
        "coo", "business_development"
    ]
    assert status["emails_sent"] is False
    assert status["production_release_authorized"] is False
    assert "private@example.com" not in str(status)


def test_missing_and_corrupt_report_fail_closed(tmp_path):
    assert read_executive_founder_status(tmp_path / "none", as_of=NOW)["available"] is False
    path = tmp_path / "report"
    path.write_text("bad-json")
    assert read_executive_founder_status(path, as_of=NOW)["status"] == "SNAPSHOT_UNAVAILABLE"


def test_unactivated_and_stale_astora_not_marked_healthy(tmp_path):
    raw = plan()
    del raw["executive_commercial_roles"]
    assert read(tmp_path, raw)["status"] == "NOT_ACTIVATED"
    raw = plan()
    raw["generated_at"] = (NOW - timedelta(days=2)).isoformat()
    assert read(tmp_path, raw)["status"] == "SNAPSHOT_STALE"


def test_forged_authority_and_stale_overlay_are_rejected(tmp_path):
    d = plan()
    d["executive_commercial_roles"]["outbound_enabled"] = True
    assert read(tmp_path, d)["status"] == "OVERLAY_UNTRUSTED"
    d = plan()
    d["executive_commercial_roles"]["as_of"] = (NOW-timedelta(hours=4)).isoformat()
    assert read(tmp_path, d)["status"] == "OVERLAY_UNTRUSTED"


def test_unknown_roles_and_actions_in_brief_fail_closed(tmp_path):
    d = plan()
    d["executive_commercial_roles"]["review"]["chief_of_staff"]["top_three_next_actions"][0]["owner"] = "external_sender"
    assert read(tmp_path, d)["status"] == "OVERLAY_UNTRUSTED"
    d = plan()
    d["executive_commercial_roles"]["review"]["chief_of_staff"]["top_three_next_actions"][0]["action"] = "SEND_MAIL"
    assert read(tmp_path, d)["status"] == "OVERLAY_UNTRUSTED"


def test_review_only_is_not_live_release_even_when_health_is_green(tmp_path):
    d = plan()
    overlay = d["executive_commercial_roles"]
    overlay["observed_systemd"]["department_cycle"] = "SUCCEEDED"
    overlay["opportunity_proof"]["status"] = "FRESH"
    overlay["founder_mailbox_observer"]["status"] = "HEALTHY"
    overlay["existing_relationship_registry"]["status"] = "OBSERVE_REVIEW"
    status = read(tmp_path, d)
    assert status["status"] == "REVIEW_ONLY_NO_RELEASE_AUTHORITY"
    assert status["production_release_authorized"] is False


def test_unauthorized_link_or_unbounded_file_refused(tmp_path):
    real = tmp_path / "real.json"
    real.write_text(json.dumps(plan()))
    link = tmp_path / "linked.json"
    link.symlink_to(real)
    assert read_executive_founder_status(link, as_of=NOW)["available"] is False
    large = tmp_path / "giant.json"
    large.write_text(" " * 1_500_001)
    assert read_executive_founder_status(large, as_of=NOW)["available"] is False


def test_founder_ops_api_get_is_readonly_and_wired_to_snapshot(tmp_path, monkeypatch):
    path = tmp_path / "executive.json"
    live_fixture = plan()
    actual_now = datetime.now(timezone.utc).isoformat()
    live_fixture["generated_at"] = actual_now
    live_fixture["executive_commercial_roles"]["as_of"] = actual_now
    path.write_text(json.dumps(live_fixture))
    app = FastAPI()
    app.include_router(create_founder_ops_router(
        snapshot_path=tmp_path / "other.json",
        executive_snapshot_path=path,
    ))
    before = path.read_bytes()
    response = TestClient(app).get("/v1/founder-ops/executive-roles/status")
    assert response.status_code == 200
    body = response.json()
    assert body["coo"]["department_cycle"] == "FAILED"
    assert body["chief_of_staff"]["top_three_review_actions"][1]["partner"] == "AceLeads"
    assert path.read_bytes() == before


def test_existing_founder_service_contains_route():
    schema = build_founder_dashboard_service().openapi()
    assert "/v1/founder-ops/executive-roles/status" in schema["paths"]


def test_naive_clock_rejected(tmp_path):
    with pytest.raises(ValueError):
        read_executive_founder_status(tmp_path / "x", as_of=datetime(2026, 10, 15))



def test_stale_commercial_mailbox_keeps_full_health_claim_held(tmp_path):
    d = plan()
    overlay = d["executive_commercial_roles"]
    overlay["observed_systemd"]["department_cycle"] = "SUCCEEDED"
    overlay["opportunity_proof"]["status"] = "FRESH"
    overlay["founder_mailbox_observer"]["status"] = "HEALTHY"
    output = read(tmp_path, d)
    assert output["status"] == "EVIDENCE_HOLD"
    assert output["business_development"]["new_replies_verified"] is False


def test_founder_console_distinguishes_provider_read_from_identity_proof(tmp_path):
    d = plan()
    d["executive_commercial_roles"]["founder_mailbox_observer"]["status"] = "PROVIDER_ONLY"
    d["executive_commercial_roles"]["observed_systemd"]["department_cycle"] = "SUCCEEDED"
    d["executive_commercial_roles"]["opportunity_proof"]["status"] = "FRESH"
    d["executive_commercial_roles"]["existing_relationship_registry"]["status"] = "OBSERVE_REVIEW"
    status = read(tmp_path, d)
    assert status["available"] is True
    assert status["coo"]["mailbox_observer"] == "PROVIDER_ONLY"
    assert status["status"] == "EVIDENCE_HOLD"
    assert status["business_development"]["new_replies_verified"] is False
    assert status["business_development"]["mailbox_current"] is False


def test_founder_projection_surfaces_real_buyer_terms_hold_without_sensitive_data(tmp_path):
    from empire_os.executive_buyer_capacity_review import review_buyer_capacity

    d = plan()
    sample = {
        "schema_version": "empire.buyer_capacity_readiness.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "allocation_executed": False, "allocation_ready": False,
        "payment_action": False, "revenue_recognition": False,
        "observed_at": NOW.isoformat(), "buyers_seen": 1057,
        "reviewed": 1, "market_defined": 107,
        "positive_capacity_configured": 121,
        "delivery_destination_present": 485,
        "capacity_verified": 0, "terms_verified": 0,
        "delivery_verified": 0, "commercially_activated": 0,
        "fully_activated": 0,
        "confidential_buyer_email": "SENSITIVE_DO_NOT_EXPOSE",
    }
    d["executive_commercial_roles"]["downstream_buyer_capacity"] = (
        review_buyer_capacity(sample, as_of=NOW)
    )
    r = read(tmp_path, d)
    assert r["available"] is True
    cap = r["business_development"]["downstream_buyer_capacity"]
    assert cap["status"] == "NO_VERIFIED_COMMERCIAL_CAPACITY"
    assert cap["buyers_seen"] == 1057
    assert cap["terms_verified"] == 0
    assert cap["capacity_verified"] == 0
    assert cap["publisher_payout_can_be_quoted"] is False
    assert cap["specific_buybox_verified"] is False
    assert cap["lead_delivery_authorized"] is False
    assert "SENSITIVE_DO_NOT_EXPOSE" not in json.dumps(r)


def test_forged_buyer_capacity_authority_holds_entire_founder_projection(tmp_path):
    d = plan()
    d["executive_commercial_roles"]["downstream_buyer_capacity"] = {
        "schema_version": "empire.executive.buyer_capacity_review.v1",
        "status": "AGGREGATE_CAPACITY_NOT_SPECIFIC_BUYBOX",
        "mode": "OBSERVE", "execution_authority": "none",
        "specific_buybox_verified": True,
        "publisher_payout_can_be_quoted": True,
        "lead_delivery_authorized": False, "payment_execution": False,
        "counts": {"buyers_seen": 100, "capacity_verified": 1,
                   "terms_verified": 1, "delivery_verified": 1,
                   "commercially_activated": 1},
    }
    assert read(tmp_path, d)["status"] == "OVERLAY_UNTRUSTED"


def test_founder_api_accepts_bounded_buyer_terms_task_but_never_dispatches(tmp_path):
    d = plan()
    d["executive_commercial_roles"]["review"]["chief_of_staff"]["top_three_next_actions"][0] = {
        "owner": "business_development",
        "action": "VERIFY_DOWNSTREAM_BUYER_TERMS_CAPACITY",
        "external_action_authorized": False,
    }
    projection = read(tmp_path, d)
    assert projection["available"] is True
    assert projection["chief_of_staff"]["top_three_review_actions"][0]["action"] == (
        "VERIFY_DOWNSTREAM_BUYER_TERMS_CAPACITY"
    )
    assert projection["emails_sent"] is False
    assert projection["lead_delivery_authorized"] is False
    assert projection["production_release_authorized"] is False
