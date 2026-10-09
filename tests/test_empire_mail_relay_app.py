from fastapi.testclient import TestClient

from empire_os.empire_mail_relay_app import app


def test_health_is_fail_closed(monkeypatch):
    monkeypatch.setenv(
        "EMPIRE_MAIL_RELAY_MODE",
        "OBSERVE",
    )
    monkeypatch.setenv(
        "EMPIRE_MAIL_RELAY_SEND_AUTHORIZED",
        "false",
    )

    client = TestClient(app)
    result = client.get("/health")

    assert result.status_code == 200

    body = result.json()

    assert body["mode"] == "OBSERVE"
    assert body["send_authorized"] is False
    assert body["mutation_authorized"] is False
    assert body["transport"] == "https_443"


def test_health_separates_live_service_from_unprovisioned_mailbox(monkeypatch, tmp_path):
    monkeypatch.setenv("EMPIRE_MAIL_RELAY_MODE", "OBSERVE")
    monkeypatch.setenv("EMPIRE_MAIL_RELAY_SEND_AUTHORIZED", "false")
    monkeypatch.delenv("EMPIRE_GMAIL_SENDER", raising=False)
    monkeypatch.setenv("EMPIRE_GMAIL_TOKEN_FILE", str(tmp_path / "absent-token.json"))
    body = TestClient(app).get("/health").json()
    assert body["ok"] is True  # Service liveness, NOT mail deliverability.
    assert body["mailbox_configuration_present"] is False
    assert body["oauth_verified"] is False
    assert body["mailbox_ready"] is False
    assert body["readiness_status"] == "BLOCKED_NOT_PROVISIONED"
    assert body["readiness_blockers"] == [
        "sender_not_configured", "oauth_token_missing",
    ]
    assert body["mutation_authorized"] is False


def test_health_ready_not_equal_send_permission(monkeypatch, tmp_path):
    token = tmp_path / "oauth-token.json"
    token.write_text("{}")
    monkeypatch.setenv("EMPIRE_GMAIL_SENDER", "phil@mail.empire-ai.co.uk")
    monkeypatch.setenv("EMPIRE_GMAIL_TOKEN_FILE", str(token))
    monkeypatch.setenv("EMPIRE_MAIL_RELAY_MODE", "OBSERVE")
    monkeypatch.setenv("EMPIRE_MAIL_RELAY_SEND_AUTHORIZED", "false")
    body = TestClient(app).get("/health").json()
    assert body["mailbox_configuration_present"] is True
    assert body["oauth_verified"] is False
    assert body["mailbox_ready"] is False
    assert body["readiness_status"] == "CONFIG_PRESENT_UNVERIFIED"
    assert body["readiness_blockers"] == ["oauth_validation_not_performed"]
    assert body["mutation_authorized"] is False


def test_send_is_blocked_in_observe(monkeypatch):
    monkeypatch.setenv(
        "EMPIRE_MAIL_RELAY_MODE",
        "OBSERVE",
    )
    monkeypatch.setenv(
        "EMPIRE_MAIL_RELAY_SEND_AUTHORIZED",
        "false",
    )

    client = TestClient(app)

    result = client.post(
        "/v1/send",
        json={"claim": {}},
    )

    assert result.status_code == 409
    assert result.json()["detail"] == "relay is OBSERVE only"
