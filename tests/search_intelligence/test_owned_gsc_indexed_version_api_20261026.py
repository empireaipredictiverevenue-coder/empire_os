"""Five-URL Google inspection endpoint uses existing loopback API/GSC owner."""
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.search_console import GoogleSearchConsoleAdapter
from empire_os.search_intelligence.owned_url_inspection import URLS, INSPECTION_ENDPOINT


def test_gsc_owned_inspection_existing_api_bounded_readonly(tmp_path):
    calls=[]
    key=tmp_path / "dummy-key.json"
    key.write_text("{}")

    def sender(endpoint, headers, payload):
        calls.append((endpoint, headers, payload))
        return {"inspectionResult": {"indexStatusResult": {
            "verdict": "PASS", "coverageState": "Submitted and indexed",
            "googleCanonical": payload["inspectionUrl"],
            "lastCrawlTime": "2026-10-15T09:00:00Z",
            "inspectionResultLink": "untrusted-token-will-be-removed",
        }}}

    adapter=GoogleSearchConsoleAdapter(
        "sc-domain:empire-ai.co.uk", key,
        token_provider=lambda _: "mock-token", post_json=sender,
    )
    app=FastAPI()
    app.include_router(create_search_router(search_console_adapter=adapter))
    r=TestClient(app).get("/v1/search/search-console/indexed-version/fixed")
    assert r.status_code==200
    assert r.headers["cache-control"]=="no-store"
    assert r.json()["count"]==5
    assert [call[2]["inspectionUrl"] for call in calls]==list(URLS)
    assert all(call[0]==INSPECTION_ENDPOINT for call in calls)
    assert r.json()["google_indexing_request_sent"] is False
    assert "mock-token" not in r.text
    assert "untrusted-token-will-be-removed" not in r.text
    second=TestClient(app).get("/v1/search/search-console/indexed-version/fixed")
    assert second.status_code == 200
    assert len(calls) == 5
    assert second.json() == r.json()


def test_gsc_indexed_version_rejects_disabled_source(monkeypatch):
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_ENABLED","false")
    app=FastAPI()
    app.include_router(create_search_router())
    r=TestClient(app).get("/v1/search/search-console/indexed-version/fixed")
    assert r.status_code==503
    assert r.json()["detail"]=="gsc_indexed_version_inspection_unavailable"
    assert r.headers["cache-control"]=="no-store"
