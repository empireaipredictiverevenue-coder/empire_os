"""No customer auth or Google OAuth when private dark staging boots."""
from fastapi.testclient import TestClient

from empire_os.inbound_calendar_connection_service import app


def test_dark_calendar_service_has_no_public_auth_or_provider_operations():
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    data = health.json()
    assert data["status"] == "dark-staging"
    assert data["google_calendar_connected"] is False
    assert data["oauth_callbacks_enabled"] is False
    assert data["openmanus_worker_verified"] is False
    assert data["commercial_actions_authorized"] is False
    assert health.headers["Cache-Control"] == "no-store"
    assert health.headers["Referrer-Policy"] == "no-referrer"

    prefix = "/v1/inbound-recovery/calendar-connect"
    assert client.get(prefix + "/status").status_code == 404
    assert client.get(prefix + "/callback").status_code == 404
    assert client.post(prefix + "/start", json={
        "calendar_id": "fixture@example.invalid",
        "customer_approved_read_only": True,
    }).status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404
