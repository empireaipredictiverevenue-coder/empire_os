from fastapi.testclient import TestClient

from empire_os.hub import app


client = TestClient(app)


def test_legacy_revenue_execution_routes_are_retired():
    assert client.post("/v1/revenue/snapshot/2026-09-19").status_code == 410
    assert client.post("/v1/revenue/brief").status_code == 410


def test_legacy_delegate_scan_is_retired():
    response = client.post("/v1/delegate/scan")
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_delegate_scan_retired_use_governed_source_mesh"
    )


def test_legacy_agi_scout_tick_is_retired():
    response = client.post("/v1/agi/scout/tick")
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_agi_scout_tick_retired_use_governed_source_mesh"
    )


def test_legacy_swarm_event_writer_is_retired():
    response = client.post(
        "/v1/swarms/events",
        json={"event_type": "MarketOpportunityFound", "niche_id": "roofing"},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_swarm_event_writer_retired_use_governed_execution_bus"
    )


def test_video_render_and_agent_dispatch_remain_retired():
    assert client.post("/v1/video/brief", json={}).status_code == 410
    assert client.post("/v1/agents/storm/dispatch", json={}).status_code == 410
