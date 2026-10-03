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
