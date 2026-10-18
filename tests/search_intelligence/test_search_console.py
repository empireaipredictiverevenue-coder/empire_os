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


def test_page_only_adapter_uses_exact_page_dimension_and_final_data(tmp_path):
    credential = tmp_path / "gsc.json"
    credential.write_text("{}")
    recorded = []
    def fake_post(url, headers, payload):
        recorded.append((url, headers, payload))
        return {"rows": [{
            "keys": ["https://empire-ai.co.uk/industries/solar"],
            "clicks": 2, "impressions": 18, "ctr": 2/18,
            "position": 6.4,
        }]}
    adapter = GoogleSearchConsoleAdapter(
        "sc-domain:empire-ai.co.uk", credential,
        token_provider=lambda _: "fixture-token", post_json=fake_post,
    )
    d = adapter.page_observations(
        start_date="2026-10-08", end_date="2026-10-17", limit=100,
    )
    assert len(d) == 1
    assert d[0]["keys"] == ["https://empire-ai.co.uk/industries/solar"]
    url, headers, payload = recorded[0]
    assert url.endswith("searchAnalytics/query")
    assert headers["Authorization"] == "Bearer fixture-token"
    assert payload == {
        "startDate": "2026-10-08", "endDate": "2026-10-17",
        "dimensions": ["page"], "rowLimit": 100, "dataState": "final",
    }


@pytest.mark.parametrize("body", [
    {"rows": [{"keys": ["foo", "bar"]}]},
    {"rows": [{"keys": []}]},
    {"rows": [{"keys": [4]}]},
    {"rows": ["unsafe"]},
    {"rows": "unsafe"},
])
def test_page_dimension_adapter_rejects_untrusted_shapes(tmp_path, body):
    credential = tmp_path / "gsc.json"
    credential.write_text("{}")
    adapter = GoogleSearchConsoleAdapter(
        "sc-domain:empire-ai.co.uk", credential,
        token_provider=lambda _: "fixture-token", post_json=lambda *args: body,
    )
    with pytest.raises(SearchConsoleUnavailable):
        adapter.page_observations(start_date="2026-10-08", end_date="2026-10-17")


def test_page_only_api_is_503_when_source_disabled(monkeypatch):
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_ENABLED", "false")
    r = _client().get(
        "/v1/search/search-console/pages?start_date=2026-10-08&end_date=2026-10-17"
    )
    assert r.status_code == 503
    assert r.json()["detail"] == "disabled"


def test_page_only_api_503_when_adapter_not_extended():
    app = FastAPI()
    app.include_router(create_search_router(search_console_adapter=FakeReadySearchConsole()))
    r = TestClient(app).get(
        "/v1/search/search-console/pages?start_date=2026-10-08&end_date=2026-10-17"
    )
    assert r.status_code == 503
    assert r.json()["detail"] == "page_dimension_reader_unavailable"


def test_page_only_api_exposes_bounded_observations_and_no_execution():
    class ReadyPageAdapter(FakeReadySearchConsole):
        def page_observations(self, *, start_date, end_date, limit=1000):
            assert limit == 17
            return [{"keys": ["https://empire-ai.co.uk/industries/roofing"],
                     "clicks": 1, "impressions": 7, "ctr": 1/7,
                     "position": 13.2}]
    app = FastAPI()
    app.include_router(create_search_router(search_console_adapter=ReadyPageAdapter()))
    r = TestClient(app).get(
        "/v1/search/search-console/pages?start_date=2026-10-08&end_date=2026-10-17&limit=17"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dimensions"] == ["page"]
    assert body["data_state"] == "final"
    assert body["count"] == 1
    assert body["window"] == ["2026-10-08", "2026-10-17"]
    assert body["indexation_verified"] is False
    assert body["attributed_buyer_verified"] is False
    assert body["execution_authority"] == "none"


@pytest.mark.parametrize("dates", [
    "start_date=2026-10-17&end_date=2026-10-08",
    "start_date=2026-08-01&end_date=2026-10-17",
])
def test_page_only_api_rejects_reverse_or_unbounded_dates(dates):
    app = FastAPI()
    app.include_router(create_search_router(search_console_adapter=FakeReadySearchConsole()))
    r = TestClient(app).get("/v1/search/search-console/pages?" + dates)
    assert r.status_code == 422


def test_page_only_limit_guard_denies_extra_returned_rows():
    class TooMany(FakeReadySearchConsole):
        def page_observations(self, *, start_date, end_date, limit=1000):
            return [{"keys": ["https://empire-ai.co.uk/industries/solar"]}] * (limit+1)
    app=FastAPI()
    app.include_router(create_search_router(search_console_adapter=TooMany()))
    r=TestClient(app).get(
        "/v1/search/search-console/pages?start_date=2026-10-08&end_date=2026-10-17&limit=1")
    assert r.status_code == 503
    assert r.json()["detail"] == "page_dimension_source_untrusted"
