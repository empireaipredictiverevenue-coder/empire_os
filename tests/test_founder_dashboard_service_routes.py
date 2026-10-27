from empire_os.founder_dashboard_service import (
    app,
    build_founder_dashboard_service,
)


CODING_TEAM_PATH = (
    "/v1/founder-execution-plane/coding-team/status"
)


def _documented_paths(service):
    """Use FastAPI's public OpenAPI contract, not router internals.

    FastAPI 0.137+ preserves included APIRouters as nested _IncludedRouter
    objects. Top-level app.routes entries therefore do not necessarily expose
    .path even when the included endpoints are correctly registered.
    """
    schema = service.openapi()
    paths = schema.get("paths") or {}
    return set(paths)


def test_live_founder_service_mounts_coding_team_status_route():
    assert CODING_TEAM_PATH in _documented_paths(app)


def test_fresh_founder_service_factory_mounts_coding_team_status_route():
    fresh = build_founder_dashboard_service()
    paths = _documented_paths(fresh)

    assert CODING_TEAM_PATH in paths
    assert "/v1/founder-execution-plane/status" in paths
    assert "/health" in paths


PREDICTIVE_REVENUE_DEMO_PATH = "/v1/predictive-revenue/demo"
PREDICTIVE_REVENUE_DEMO_LIVE_PATH = "/v1/predictive-revenue/demo/live"


def test_live_founder_service_mounts_predictive_revenue_demo_routes():
    paths = _documented_paths(app)
    assert PREDICTIVE_REVENUE_DEMO_PATH in paths
    assert PREDICTIVE_REVENUE_DEMO_LIVE_PATH in paths


def test_fresh_founder_service_mounts_predictive_revenue_demo_routes():
    paths = _documented_paths(build_founder_dashboard_service())
    assert PREDICTIVE_REVENUE_DEMO_PATH in paths
    assert PREDICTIVE_REVENUE_DEMO_LIVE_PATH in paths


def test_company_review_is_mounted_but_unconfigured_access_is_held():
    from fastapi.testclient import TestClient
    client = TestClient(build_founder_dashboard_service())
    path = "/v1/predictive-revenue/company-review"
    response = client.get(path, params={"company_scope": "example", "source_id": "source"})
    assert response.status_code == 503
    assert response.json() == {"detail": "company_review_not_configured"}
    assert response.headers["cache-control"] == "no-store"
    assert client.post(path).status_code == 405
    assert client.get("/health").json()["read_only"] is True


def test_bad_company_router_configuration_fails_service_construction():
    import pytest
    for factory in (False, lambda: None):
        with pytest.raises(ValueError):
            build_founder_dashboard_service(company_review_router_factory=factory)
