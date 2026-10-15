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
