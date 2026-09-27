from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.search_intelligence.api import create_search_router
from empire_os.search_intelligence.reports import (
    build_search_product_report,
)
from empire_os.search_intelligence.search_console import (
    DisabledSearchConsoleAdapter,
    SearchConsoleStatus,
)


def test_report_keeps_missing_sections_unavailable():
    report = build_search_product_report(
        product_key="technical_search_audit",
        site="https://example.test",
        generated_at="2026-09-20T23:20:00Z",
        evidence={
            "indexation_health": {"indexed": 12},
            "metadata_quality": {"issues": 3},
        },
    )

    assert report["observed_sections"] == 2
    assert report["unavailable_sections"] > 0
    assert report["synthetic_metrics"] == 0
    states = {row["key"]: row["state"] for row in report["sections"]}
    assert states["indexation_health"] == "observed"
    assert states["schema_review"] == "unavailable"


def test_report_requires_real_product_and_site():
    try:
        build_search_product_report(
            product_key="not-real",
            site="https://example.test",
            generated_at="2026-09-20T23:20:00Z",
            evidence={},
        )
    except ValueError as exc:
        assert "search product not found" in str(exc)
    else:
        raise AssertionError("unknown product must fail")


def test_report_api_is_observe_only():
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

    response = client.post(
        "/v1/search/products/local_search_grid/report/preview",
        json={
            "site": "https://example.test",
            "generated_at": "2026-09-20T23:20:00Z",
            "evidence": {
                "maps_grid_visibility": {
                    "observed_points": 25,
                    "ranked_points": 21,
                }
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["product"]["key"] == "local_search_grid"
    assert payload["execution_allowed"] is False
    assert payload["publishing_execution"] is False
    assert payload["pricing_observed"] is False
    assert payload["synthetic_metrics"] == 0
