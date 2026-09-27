from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.performance import (
    lighthouse_parser_status,
    parse_lighthouse_report,
)
from empire_os.search_intelligence.search_console import (
    DisabledSearchConsoleAdapter,
    SearchConsoleStatus,
)


REPORT = {
    "lighthouseVersion": "13.0.0",
    "fetchTime": "2026-09-20T23:10:00.000Z",
    "finalDisplayedUrl": "https://example.test/",
    "categories": {
        "performance": {"score": 0.82},
        "accessibility": {"score": 0.96},
        "best-practices": {"score": 0.91},
        "seo": {"score": 0.88},
    },
    "audits": {
        "largest-contentful-paint": {
            "title": "Largest Contentful Paint",
            "numericValue": 3200,
            "numericUnit": "millisecond",
            "displayValue": "3.2 s",
            "score": 0.55,
        },
        "first-contentful-paint": {
            "title": "First Contentful Paint",
            "numericValue": 1500,
            "numericUnit": "millisecond",
            "displayValue": "1.5 s",
            "score": 0.93,
        },
        "cumulative-layout-shift": {
            "title": "Cumulative Layout Shift",
            "numericValue": 0.08,
            "numericUnit": "unitless",
            "displayValue": "0.08",
            "score": 0.95,
        },
        "total-blocking-time": {
            "title": "Total Blocking Time",
            "numericValue": 680,
            "numericUnit": "millisecond",
            "displayValue": "680 ms",
            "score": 0.22,
        },
        "speed-index": {
            "title": "Speed Index",
            "numericValue": 3900,
            "numericUnit": "millisecond",
            "displayValue": "3.9 s",
            "score": 0.7,
        },
        "render-blocking-resources": {
            "title": "Eliminate render-blocking resources",
            "score": 0.4,
            "displayValue": "Potential savings of 420 ms",
            "details": {
                "type": "opportunity",
                "overallSavingsMs": 420,
            },
        },
        "uses-text-compression": {
            "title": "Enable text compression",
            "score": 0.2,
            "details": {
                "type": "opportunity",
                "overallSavingsMs": 900,
            },
        },
    },
}


def test_parser_separates_lab_metrics_from_field_data():
    result = parse_lighthouse_report(REPORT)

    assert result["measurement_kind"] == "lab"
    assert result["field_core_web_vitals_available"] is False
    assert result["field_data_invented"] is False
    assert result["category_scores"]["performance"] == 82
    assert result["category_scores"]["seo"] == 88

    metrics = {row["key"]: row for row in result["lab_metrics"]}
    assert metrics["largest-contentful-paint"]["rating"] == (
        "needs_improvement"
    )
    assert metrics["cumulative-layout-shift"]["rating"] == "good"
    assert metrics["total-blocking-time"]["rating"] == "poor"


def test_parser_orders_opportunities_by_estimated_savings():
    result = parse_lighthouse_report(REPORT)

    assert result["opportunities"][0]["key"] == "uses-text-compression"
    assert result["opportunities"][0]["estimated_savings_ms"] == 900


def test_parser_fails_closed_without_audits():
    try:
        parse_lighthouse_report({"categories": {}})
    except ValueError as exc:
        assert "audits missing" in str(exc)
    else:
        raise AssertionError("missing audits must fail closed")


def test_status_does_not_claim_runner_is_active():
    status = lighthouse_parser_status()

    assert status["parser_available"] is True
    assert status["runner_available"] is False
    assert status["browser_execution"] is False


def test_performance_api_parses_observed_report():
    app = FastAPI()
    app.include_router(
        create_search_router(
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

    status = client.get("/v1/search/performance/status")
    assert status.status_code == 200
    assert status.json()["runner_available"] is False

    response = client.post(
        "/v1/search/performance/lighthouse/parse",
        json={"report": REPORT},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["measurement_kind"] == "lab"
    assert payload["category_scores"]["accessibility"] == 96
    assert payload["execution_allowed"] is False
