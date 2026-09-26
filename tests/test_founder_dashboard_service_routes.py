from empire_os.founder_dashboard_service import (
    app,
    build_founder_dashboard_service,
)


CODING_TEAM_PATH = (
    "/v1/founder-execution-plane/coding-team/status"
)


def _paths(service):
    return {
        getattr(route, "path", None)
        for route in service.routes
    }


def test_live_founder_service_mounts_coding_team_status_route():
    assert CODING_TEAM_PATH in _paths(app)


def test_fresh_founder_service_factory_mounts_coding_team_status_route():
    fresh = build_founder_dashboard_service()
    assert CODING_TEAM_PATH in _paths(fresh)
    assert "/v1/founder-execution-plane/status" in _paths(fresh)
    assert "/health" in _paths(fresh)
