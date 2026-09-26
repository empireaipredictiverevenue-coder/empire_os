from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.astra_api import create_astra_router


def client():
    app = FastAPI()
    app.include_router(create_astra_router())
    return TestClient(app)


def snapshot(**overrides):
    data = {
        "execution_mode": "observe",
        "actual_revenue_cents": 0,
        "premium_ai_budget_cents": 0,
        "replies_waiting": 0,
        "failed_jobs": 0,
        "owned_inventory_count": 8,
        "qualified_unallocated_count": 2,
        "active_buyer_capacity": 3,
        "buyer_candidates_due": 0,
        "outbound_domain_verified": True,
        "source_health_ok": True,
    }
    data.update(overrides)
    return data


def test_health_is_observe_only():
    response = client().get("/v1/astra/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["side_effects"] == "none"
    assert body["execution_authority"] == "none"
    assert body["commercial_mutation"] is False
    assert body["payment_execution"] is False
    assert body["outreach_execution"] is False
    assert body["allocation_execution"] is False


def test_board_preview_returns_plan_only_allocation_recommendation():
    response = client().post(
        "/v1/astra/board/preview",
        json={"snapshot": snapshot()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["side_effects"] == "none"
    assert body["execution_authority"] == "none"
    board = body["board"]
    assert board["side_effects"] == "none"
    assert board["primary"]["recommended_job_type"] == (
        "plan_controlled_allocation"
    )
    assert board["primary"]["side_effect_approval_required"] is True


def test_reply_backlog_outranks_allocation():
    response = client().post(
        "/v1/astra/board/preview",
        json={"snapshot": snapshot(replies_waiting=2)},
    )
    assert response.status_code == 200
    primary = response.json()["board"]["primary"]
    assert primary["recommended_job_type"] == "triage_buyer_replies"


def test_negative_margin_review_can_outrank_operations():
    response = client().post(
        "/v1/astra/board/preview",
        json={
            "snapshot": snapshot(failed_jobs=1),
            "negative_margin_orders": 1,
            "calibration_ready": True,
            "gross_margin_rate": -0.1,
        },
    )
    assert response.status_code == 200
    primary = response.json()["board"]["primary"]
    assert primary["recommended_job_type"] == "review_negative_margin"


def test_non_observe_preview_is_rejected():
    response = client().post(
        "/v1/astra/board/preview",
        json={"snapshot": snapshot(execution_mode="live")},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "astra preview supports OBSERVE only"
