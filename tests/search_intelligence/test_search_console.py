from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.search_console import (
    configured_search_console_adapter,
    search_console_status_from_env,
)


def _client():
    app = FastAPI()
    app.include_router(create_search_router())
    return TestClient(app)


def test_search_console_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EMPIRE_SEARCH_CONSOLE_ENABLED", raising=False)
    monkeypatch.delenv("EMPIRE_SEARCH_CONSOLE_SITE_URL", raising=False)
    monkeypatch.delenv(
        "EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE",
        raising=False,
    )
    status = search_console_status_from_env()
    assert status.enabled is False
    assert status.configured is False
    assert status.available is False
    assert status.reason == "disabled"
    assert configured_search_console_adapter().observations(
        start_date="2026-09-01",
        end_date="2026-09-19",
    ) == ()


def test_enabled_gate_requires_site_and_credential_binding(monkeypatch):
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_ENABLED", "true")
    monkeypatch.delenv("EMPIRE_SEARCH_CONSOLE_SITE_URL", raising=False)
    monkeypatch.delenv(
        "EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE",
        raising=False,
    )
    status = search_console_status_from_env()
    assert status.enabled is True
    assert status.configured is False
    assert status.reason == "missing_required_binding"


def test_existing_credential_binding_stays_unavailable_until_approved(
    monkeypatch,
    tmp_path,
):
    credential = tmp_path / "gsc.json"
    credential.write_text("do-not-read-this-content")
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_ENABLED", "true")
    monkeypatch.setenv(
        "EMPIRE_SEARCH_CONSOLE_SITE_URL",
        "https://empire-ai.co.uk/",
    )
    monkeypatch.setenv(
        "EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE",
        str(credential),
    )

    status = search_console_status_from_env()
    assert status.configured is True
    assert status.available is False
    assert status.reason == "adapter_activation_not_approved"
    assert "do-not-read" not in str(status.as_dict())


def test_api_exposes_fail_closed_search_console_status(monkeypatch):
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_ENABLED", "false")
    response = _client().get("/v1/search/search-console/status")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["available"] is False
    assert body["reason"] == "disabled"
