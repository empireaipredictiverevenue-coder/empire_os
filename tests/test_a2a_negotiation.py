from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.a2a_commerce_api import create_a2a_commerce_router
from empire_os.a2a_negotiation import preview_negotiation_transition


def test_pending_requires_human_approval():
    result = preview_negotiation_transition(
        current_state="pending_approval",
        requested_state="reviewed",
        human_approval_present=False,
    )
    assert result.transition_valid is False
    assert result.reason == "human_approval_required"
    assert result.execution_authority == "none"


def test_reviewed_can_be_approved_for_manual_execution_only():
    result = preview_negotiation_transition(
        current_state="reviewed",
        requested_state="approved_for_manual_execution",
        human_approval_present=True,
    )
    assert result.transition_valid is True
    assert result.reason == "approved_for_manual_execution_only"
    assert result.payment_authority is False
    assert result.allocation_authority is False
    assert result.task_execution is False


def test_terminal_state_cannot_transition():
    result = preview_negotiation_transition(
        current_state="approved_for_manual_execution",
        requested_state="reviewed",
        human_approval_present=True,
    )
    assert result.transition_valid is False
    assert result.reason == "transition_not_allowed"


def test_preview_api_never_executes():
    app = FastAPI()
    app.include_router(create_a2a_commerce_router())
    client = TestClient(app)
    response = client.post(
        "/v1/a2a-commerce/negotiation/transition/preview",
        json={
            "current_state": "reviewed",
            "requested_state": "counter_proposed",
            "human_approval_present": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_authority"] == "none"
    assert body["payment_authority"] is False
    assert body["allocation_authority"] is False
    assert body["task_execution"] is False
    assert body["transition"]["transition_valid"] is True
