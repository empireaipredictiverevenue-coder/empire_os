from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.search_console import (
    GoogleSearchConsoleAdapter,
    SearchConsoleUnavailable,
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
    with pytest.raises(SearchConsoleUnavailable, match="disabled"):
        configured_search_console_adapter().observations(
            start_date="2026-09-01",
            end_date="2026-09-19",
        )


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


def test_activation_flag_is_separate_from_configuration(monkeypatch, tmp_path):
    credential = tmp_path / "gsc.json"
    credential.write_text("{}")
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_ENABLED", "true")
    monkeypatch.setenv(
        "EMPIRE_SEARCH_CONSOLE_SITE_URL",
        "https://empire-ai.co.uk/",
    )
    monkeypatch.setenv(
        "EMPIRE_SEARCH_CONSOLE_CREDENTIAL_FILE",
        str(credential),
    )
    monkeypatch.setenv(
        "EMPIRE_SEARCH_CONSOLE_ACTIVATION_APPROVED",
        "true",
    )
    status = search_console_status_from_env()
    assert status.configured is True
    assert status.available is True
    assert status.reason == "ready"


def test_real_adapter_maps_search_analytics_rows_without_network(tmp_path):
    credential = tmp_path / "gsc.json"
    credential.write_text("{}")
    calls = []

    def token_provider(path: Path) -> str:
        assert path == credential
        return "test-token"

    def post_json(url, headers, payload):
        calls.append((url, dict(headers), dict(payload)))
        return {
            "rows": [{
                "keys": ["predictive revenue", "https://empire-ai.co.uk/"],
                "clicks": 3,
                "impressions": 40,
                "ctr": 0.075,
                "position": 4.2,
            }]
        }

    adapter = GoogleSearchConsoleAdapter(
        "https://empire-ai.co.uk/",
        credential,
        token_provider=token_provider,
        post_json=post_json,
    )
    rows = adapter.observations(
        start_date="2026-09-01",
        end_date="2026-09-19",
        limit=50,
    )
    assert rows[0]["clicks"] == 3
    assert rows[0]["position"] == 4.2
    url, headers, payload = calls[0]
    assert "searchAnalytics/query" in url
    assert headers["Authorization"] == "Bearer test-token"
    assert payload["dimensions"] == ["query", "page"]
    assert payload["rowLimit"] == 50


def test_real_adapter_bounds_row_limit(tmp_path):
    credential = tmp_path / "gsc.json"
    credential.write_text("{}")
    observed = {}

    def post_json(url, headers, payload):
        observed.update(payload)
        return {"rows": []}

    adapter = GoogleSearchConsoleAdapter(
        "sc-domain:empire-ai.co.uk",
        credential,
        token_provider=lambda path: "token",
        post_json=post_json,
    )
    assert adapter.observations(
        start_date="2026-09-01",
        end_date="2026-09-19",
        limit=999999,
    ) == ()
    assert observed["rowLimit"] == 25000
class FakeReadySearchConsole:
    def status(self):
        from empire_os.search_intelligence.search_console import SearchConsoleStatus
        return SearchConsoleStatus(
            enabled=True,
            configured=True,
            available=True,
            reason="ready",
            site_url="https://empire-ai.co.uk/",
        )

    def observations(self, *, start_date, end_date, limit=1000):
        return [{
            "keys": ["predictive revenue", "https://empire-ai.co.uk/"],
            "clicks": 5,
            "impressions": 50,
            "position": 3.5,
        }]

    def daily_observations(self, *, start_date, end_date, limit=1000):
        from datetime import date, timedelta
        start = date.fromisoformat(start_date)
        return [
            {
                "keys": [(start + timedelta(days=i)).isoformat()],
                "clicks": 10 + i,
                "impressions": 100 + i * 10,
                "ctr": (10 + i) / (100 + i * 10),
                "position": 4.0,
            }
            for i in range(14)
        ]


def test_search_console_observations_endpoint_fails_closed_by_default():
    response = _client().get(
        "/v1/search/search-console/observations"
        "?start_date=2026-09-01&end_date=2026-09-19"
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "disabled"
def test_search_console_observations_endpoint_returns_real_adapter_rows():
    app = FastAPI()
    app.include_router(create_search_router(
        search_console_adapter=FakeReadySearchConsole(),
    ))
    response = TestClient(app).get(
        "/v1/search/search-console/observations"
        "?start_date=2026-09-01&end_date=2026-09-19&limit=25"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "google_search_console"
    assert body["count"] == 1
    assert body["limit"] == 25
    assert body["items"][0]["clicks"] == 5


def test_search_console_observations_rejects_reverse_date_range():
    app = FastAPI()
    app.include_router(create_search_router(
        search_console_adapter=FakeReadySearchConsole(),
    ))
    response = TestClient(app).get(
        "/v1/search/search-console/observations"
        "?start_date=2026-09-19&end_date=2026-09-01"
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_date_range"


def test_real_adapter_maps_daily_search_analytics_rows(tmp_path):
    credential = tmp_path / "gsc.json"
    credential.write_text("{}")
    calls = []

    def post_json(url, headers, payload):
        calls.append(dict(payload))
        return {
            "rows": [{
                "keys": ["2026-09-01"],
                "clicks": 3,
                "impressions": 40,
                "ctr": 0.075,
                "position": 4.2,
            }]
        }

    adapter = GoogleSearchConsoleAdapter(
        "https://empire-ai.co.uk/",
        credential,
        token_provider=lambda path: "token",
        post_json=post_json,
    )
    rows = adapter.daily_observations(
        start_date="2026-09-01",
        end_date="2026-09-19",
        limit=50,
    )
    assert rows[0]["clicks"] == 3
    assert calls[0]["dimensions"] == ["date"]


def test_search_console_daily_endpoint_returns_date_rows():
    app = FastAPI()
    app.include_router(create_search_router(
        search_console_adapter=FakeReadySearchConsole(),
    ))
    response = TestClient(app).get(
        "/v1/search/search-console/daily"
        "?start_date=2026-09-01&end_date=2026-09-14"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dimensions"] == ["date"]
    assert body["count"] == 14


def test_search_traffic_forecast_endpoint_preserves_shadow_mode():
    app = FastAPI()
    app.include_router(create_search_router(
        search_console_adapter=FakeReadySearchConsole(),
    ))
    response = TestClient(app).get(
        "/v1/search/forecast/traffic"
        "?start_date=2026-09-01&end_date=2026-09-14&horizon_days=7"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "SHADOW_COMPARE"
    assert body["execution_authority"] == "none"
    assert body["observed_rows"] == 14
    assert body["forecast"]["baseline_impressions"]["available"] is True
    assert body["forecast"]["timesfm_horizon_impressions"] is None
