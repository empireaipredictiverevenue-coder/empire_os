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
