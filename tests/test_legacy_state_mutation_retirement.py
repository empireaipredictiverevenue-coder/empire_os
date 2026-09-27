from fastapi.testclient import TestClient

from empire_os.hub import app


client = TestClient(app)


def test_traffic_mutation_routes_are_retired():
    discover = client.post(
        "/v1/traffic/discover",
        json={
            "prospect_id": "prospect-1",
            "niche": "roofing",
            "metro": "London",
        },
    )
    match = client.post(
        "/v1/traffic/match",
        json={"prospect_id": "prospect-1", "notes": "reviewed"},
    )
    assert discover.status_code == 410
    assert match.status_code == 410


def test_buyer_auto_onboarding_is_retired():
    response = client.post(
        "/v1/buyers/apply",
        json={
            "name": "Acme",
            "niche": "roofing",
            "tier": "silver",
            "email": "buyer@example.com",
        },
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_buyer_apply_retired_use_governed_bsc_buyer_onboarding_flow"
    )


def test_swarm_worker_config_write_is_retired():
    response = client.post(
        "/v1/swarm/worker-config",
        json={
            "worker_id": "outreach-agent",
            "niche": "roofing",
            "metro": "London",
        },
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_swarm_worker_config_retired_use_governed_execution_bus"
    )


def test_homeowner_mutation_routes_are_retired():
    cases = [
        ("post", "/v1/homeowner/jobs", {}),
        ("post", "/v1/homeowner/jobs/1/match", {}),
        ("patch", "/v1/homeowner/jobs/1/status", {}),
        ("post", "/v1/homeowner/jobs/1/status", {}),
        ("patch", "/v1/homeowner/jobs/matches/1/status", {}),
        ("post", "/v1/homeowner/pipeline/transition", {}),
    ]
    for method, path, payload in cases:
        response = getattr(client, method)(path, json=payload)
        assert response.status_code == 410, (method, path, response.text)


def test_carrier_application_mutations_are_retired():
    cases = [
        ("post", "/v1/carrier-applications", {}),
        ("patch", "/v1/carrier-applications/1", {}),
        ("post", "/v1/carrier-applications/1/auto-fill", {}),
    ]
    for method, path, payload in cases:
        response = getattr(client, method)(path, json=payload)
        assert response.status_code == 410, (method, path, response.text)
