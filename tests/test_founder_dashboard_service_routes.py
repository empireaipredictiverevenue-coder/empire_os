from empire_os.founder_dashboard_service import app


def test_live_founder_service_mounts_coding_team_status_route():
    paths = {
        getattr(route, "path", None)
        for route in app.routes
    }
    assert (
        "/v1/founder-execution-plane/coding-team/status"
        in paths
    )
