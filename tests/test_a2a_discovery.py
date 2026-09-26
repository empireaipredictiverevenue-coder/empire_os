from fastapi.testclient import TestClient

from empire_os.a2a_discovery import (
    COMMERCE_CAPABILITIES,
    commerce_discovery_manifest,
)
from empire_os.public_gateway import app


def test_commerce_discovery_is_descriptive_not_executable():
    manifest = commerce_discovery_manifest(
        public_base_url="https://empire-ai.co.uk",
        public_capability_names=["market.search"],
    )
    assert manifest["public_discovery"]["authentication_required"] is False
    assert manifest["commercial_discovery"]["authentication_required"] is True
    assert manifest["commercial_discovery"]["authentication_status"] == "not_activated"
    assert manifest["privileged_actions_exposed"] is False
    assert manifest["payments_exposed"] is False
    assert manifest["allocations_exposed"] is False
    assert all(
        capability["execution_exposed"] is False
        for capability in manifest["commercial_discovery"]["capabilities"]
    )


def test_commerce_capabilities_require_auth_and_approval():
    assert COMMERCE_CAPABILITIES
    for capability in COMMERCE_CAPABILITIES:
        assert capability.authentication_required is True
        assert capability.human_approval_required is True
        assert capability.execution_exposed is False
def test_public_discovery_route_exposes_no_commercial_execution():
    response = TestClient(app).get("/a2a/v1/discovery")
    assert response.status_code == 200
    body = response.json()
    assert body["privileged_actions_exposed"] is False
    assert body["payments_exposed"] is False
    assert body["allocations_exposed"] is False
    assert body["commercial_discovery"]["authentication_status"] == "not_activated"


def test_a2a_message_surface_remains_discovery_only():
    response = TestClient(app).post(
        "/a2a/v1/message:send",
        json={
            "message": {
                "messageId": "m1",
                "parts": [{"text": "show capabilities"}],
            }
        },
    )
    assert response.status_code == 200
    data = response.json()["message"]["parts"][0]["data"]
    assert data["mode"] == "public_read_discovery"
    assert response.json()["message"]["metadata"]["privilegedActionsExposed"] is False
