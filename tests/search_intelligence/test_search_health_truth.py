"""Read-only Search Console state must agree across existing API endpoints."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.health import search_health
from empire_os.search_intelligence.search_console import SearchConsoleStatus


def _client(adapter=None):
    app = FastAPI()
    app.include_router(create_search_router(search_console_adapter=adapter))
    return TestClient(app)


def test_missing_environment_is_explicitly_disabled(monkeypatch):
    for key in (
        "EMPIRE_SEARCH_CONSOLE_ENABLED",
        "EMPIRE_SEARCH_CONSOLE_ACTIVATION_APPROVED",
        "EMPIRE_SEARCH_CONSOLE_SITE_URL",
        "EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE",
    ):
        monkeypatch.delenv(key, raising=False)
    state = search_health()
    assert state["execution_mode"] == "OBSERVE"
    assert state["mutations_enabled"] is False
    assert state["search_console"] == {
        "enabled": False, "configured": False, "available": False,
        "reason": "disabled", "site_url": None, "status": "disabled",
    }


def test_summary_and_health_follow_live_configured_adapter(monkeypatch, tmp_path):
    # A dummy on-disk credential is enough for the LOCAL status gate. No
    # credential content is read or sent to Google in this test.
    cred = tmp_path / "private.json"
    cred.write_text('{"marker":"never-display"}')
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_ENABLED", "true")
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_ACTIVATION_APPROVED", "true")
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_SITE_URL", "sc-domain:empire-ai.co.uk")
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE", str(cred))
    client = _client()
    expected = client.get("/v1/search/search-console/status").json()
    assert expected == {
        "enabled": True, "configured": True, "available": True,
        "reason": "ready", "site_url": "sc-domain:empire-ai.co.uk",
    }
    for name in ("/v1/search/health", "/v1/search/summary"):
        response = client.get(name)
        assert response.status_code == 200
        data = response.json()
        assert data["search_console"] == {**expected, "status": "ready"}
        assert data["mutations_enabled"] is False
        assert "never-display" not in response.text
        assert str(cred) not in response.text


def test_unapproved_activation_remains_unavailable(monkeypatch, tmp_path):
    cred = tmp_path / "private.json"
    cred.write_text("{}")
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_ENABLED", "true")
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_ACTIVATION_APPROVED", "false")
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_SITE_URL", "sc-domain:empire-ai.co.uk")
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE", str(cred))
    client = _client()
    assert client.get("/v1/search/search-console/status").json()["available"] is False
    health = client.get("/v1/search/health").json()["search_console"]
    assert health["enabled"] is True
    assert health["configured"] is True
    assert health["available"] is False
    assert health["status"] == "adapter_activation_not_approved"


def test_injected_adapter_is_single_source_of_truth_even_if_env_differs(monkeypatch):
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_ENABLED", "false")
    class Injected:
        def status(self):
            return SearchConsoleStatus(
                enabled=True, configured=True, available=True,
                reason="ready", site_url="sc-domain:injected-example.test",
            )
    client = _client(Injected())
    exact = client.get("/v1/search/search-console/status").json()
    for route in ("/v1/search/health", "/v1/search/summary"):
        data = client.get(route).json()
        assert data["search_console"] == {**exact, "status": exact["reason"]}
