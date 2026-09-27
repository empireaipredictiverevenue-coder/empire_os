from collections import Counter

from fastapi.testclient import TestClient

from empire_os.hub import app


client = TestClient(app)


def test_legacy_paid_product_execution_routes_are_retired():
    routes = [
        "/v1/satellite/idle-watch/report",
        "/v1/warehouse/asset/report",
        "/v1/leads/engine/discover",
        "/v1/skillspector/audit",
        "/v1/opencut/studio",
        "/v1/templates/list",
        "/v1/hermes/framework",
        "/v1/lead-lane/access",
        "/v1/satellite/wastage/report",
        "/v1/marketingskills/access",
    ]
    for path in routes:
        response = client.post(path, json={"tenant": "legacy-tenant"})
        assert response.status_code == 410, (path, response.text)


def test_hub_has_no_duplicate_method_path_registrations():
    pairs = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if not path:
            continue
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            pairs.append((method, path))

    counts = Counter(pairs)
    duplicates = {
        pair: count
        for pair, count in counts.items()
        if count > 1
    }
    assert duplicates == {}
