"""Five-URL Google inspection endpoint uses existing loopback API/GSC owner."""
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.search_console import GoogleSearchConsoleAdapter
from empire_os.search_intelligence.owned_url_inspection import URLS, ROOFING_GUIDE_URLS, INSPECTION_ENDPOINT


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



def test_original_api_new_roofing_inspection_exact_two_guides_and_cached(tmp_path):
    calls=[]
    key=tmp_path/"google-test-credential.json"
    key.write_text("{}")
    def sender(endpoint,headers,payload):
        calls.append((endpoint,headers,payload))
        return {"inspectionResult":{"indexStatusResult":{
            "verdict":"NEUTRAL",
            "coverageState":"URL is unknown to Google",
            "googleCanonical":payload["inspectionUrl"],
            "userCanonical":payload["inspectionUrl"],
            "inspectionResultLink":"hidden-provider-token"
        }}}
    adapter=GoogleSearchConsoleAdapter(
        "sc-domain:empire-ai.co.uk",key,
        token_provider=lambda _: "mock-roofing-token",
        post_json=sender,
    )
    app=FastAPI()
    app.include_router(create_search_router(search_console_adapter=adapter))
    route="/v1/search/search-console/indexed-version/roofing-guides"
    r=TestClient(app).get(route)
    assert r.status_code==200
    assert r.headers["cache-control"]=="no-store"
    assert r.headers["x-content-type-options"]=="nosniff"
    d=r.json()
    assert d["count"]==2
    assert d["status"]=="ROOFING_GUIDES_INDEXED_VERSION_INSPECTION_RECORDED"
    assert [x["url"] for x in d["items"]]==list(ROOFING_GUIDE_URLS)
    assert [x[2]["inspectionUrl"] for x in calls]==list(ROOFING_GUIDE_URLS)
    assert all(x[0]==INSPECTION_ENDPOINT for x in calls)
    assert d["google_live_test_performed"] is False
    assert d["google_indexing_request_sent"] is False
    assert "mock-roofing-token" not in r.text
    assert "hidden-provider-token" not in r.text
    again=TestClient(app).get(route)
    assert again.status_code==200 and again.json()==d
    assert len(calls)==2
    # Original five-page endpoint still has independent scope and cache.
    original=TestClient(app).get("/v1/search/search-console/indexed-version/fixed")
    assert original.status_code==200
    assert original.json()["count"]==5
    assert [x[2]["inspectionUrl"] for x in calls[2:]]==list(URLS)


def test_roofing_inspection_api_disabled_source_fails_closed_and_cached(monkeypatch):
    monkeypatch.setenv("EMPIRE_SEARCH_CONSOLE_ENABLED","false")
    app=FastAPI()
    app.include_router(create_search_router())
    url="/v1/search/search-console/indexed-version/roofing-guides"
    first=TestClient(app).get(url)
    second=TestClient(app).get(url)
    assert first.status_code==503 and second.status_code==503
    assert first.json()["detail"]=="gsc_roofing_guides_indexed_version_unavailable"
    assert second.json()["detail"]==first.json()["detail"]
    assert first.headers["cache-control"]=="no-store"


def test_roofing_inspection_api_refuses_wrong_google_property(tmp_path):
    key=tmp_path/"google-test.json"
    key.write_text("{}")
    captured=[]
    adapter=GoogleSearchConsoleAdapter(
        "sc-domain:other.example",key,
        token_provider=lambda _: captured.append("token") or "BAD",
        post_json=lambda *args:captured.append("call") or {},
    )
    app=FastAPI()
    app.include_router(create_search_router(search_console_adapter=adapter))
    r=TestClient(app).get("/v1/search/search-console/indexed-version/roofing-guides")
    assert r.status_code==503
    assert not captured
