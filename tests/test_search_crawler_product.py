from fastapi import FastAPI
from fastapi.testclient import TestClient

import empire_os.search_intelligence.api as search_api
from empire_os.search_intelligence.crawler_product import (
    audit_probe_result,
    crawl_search_site,
)
from empire_os.search_intelligence.search_console import (
    DisabledSearchConsoleAdapter,
    SearchConsoleStatus,
)


def sample_probe():
    return {
        "ok": True,
        "requested_url": "https://example.test",
        "final_url": "https://example.test/",
        "canonical_url": "",
        "domain": "example.test",
        "title": "Example Roofing",
        "description": "",
        "business_names": ["Example Roofing"],
        "phones": ["+1 555 111 2222"],
        "addresses": [],
        "schema_types": [],
        "pages_checked": [
            {
                "url": "https://example.test/",
                "canonical_url": "",
                "title": "Example Roofing",
                "schema_records": 0,
            },
            {
                "url": "https://example.test/about",
                "canonical_url": "",
                "title": "Example Roofing",
                "schema_records": 0,
            },
            {
                "url": "https://example.test/services",
                "canonical_url": "https://example.test/services",
                "title": "",
                "schema_records": 0,
            },
        ],
        "evidence_score": 0.4,
        "budget_exhausted": True,
    }


def test_audit_probe_result_surfaces_observed_technical_findings():
    audit = audit_probe_result(sample_probe())

    assert audit["available"] is True
    assert audit["pages_observed"] == 3
    codes = {row["code"] for row in audit["findings"]}
    assert "meta_description_missing" in codes
    assert "site_canonical_missing" in codes
    assert "structured_data_not_observed" in codes
    assert "page_title_missing" in codes
    assert "page_canonical_missing" in codes
    assert "duplicate_page_title" in codes
    assert "crawl_budget_exhausted" in codes
    assert audit["execution_allowed"] is False


def test_crawl_failure_is_fail_closed():
    audit = audit_probe_result({
        "ok": False,
        "requested_url": "https://bad.test",
        "error": "fetch_failed",
    })

    assert audit["available"] is False
    assert audit["reason"] == "fetch_failed"
    assert audit["findings"][0]["severity"] == "critical"


def test_crawl_search_site_bounds_input_and_never_mutates():
    calls = []

    def fake_probe(url, **kwargs):
        calls.append((url, kwargs))
        probe = sample_probe()
        probe["requested_url"] = url
        return probe

    result = crawl_search_site(
        "example.test",
        max_pages=99,
        request_timeout=99,
        time_budget_seconds=999,
        probe=fake_probe,
    )

    assert result["source"] == "empire_web_intelligence_crawler"
    assert result["execution_allowed"] is False
    assert result["publishing_execution"] is False
    assert result["indexation_execution"] is False
    assert calls[0][1]["max_pages"] == 12
    assert calls[0][1]["request_timeout"] == 30.0
    assert calls[0][1]["time_budget_seconds"] == 120.0


def test_api_exposes_native_crawl_preview(monkeypatch):
    monkeypatch.setattr(
        search_api,
        "crawl_search_site",
        lambda url, **kwargs: {
            "schema_version": "empire.search.crawl.v1",
            "source": "empire_web_intelligence_crawler",
            "mode": "OBSERVE",
            "execution_allowed": False,
            "requested_url": url,
            "audit": {"available": True, "finding_count": 0},
        },
    )

    app = FastAPI()
    app.include_router(
        search_api.create_search_router(
            repository=None,
            search_console_adapter=DisabledSearchConsoleAdapter(
                SearchConsoleStatus(
                    enabled=False,
                    configured=False,
                    available=False,
                    reason="not_configured",
                )
            ),
        )
    )
    client = TestClient(app)

    response = client.post(
        "/v1/search/crawl/preview",
        json={"url": "https://example.test", "max_pages": 4},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "empire_web_intelligence_crawler"
    assert payload["execution_allowed"] is False
