from fastapi.testclient import TestClient

from empire_os.hub import app


client = TestClient(app)


def test_internal_agent_topology_reads_are_retired():
    assert client.get("/v1/agents").status_code == 410
    assert client.get("/v1/agents/status").status_code == 410


def test_prompt_product_bypass_reads_are_retired():
    assert client.get("/v1/prompts/list").status_code == 410
    assert client.get(
        "/v1/prompts/get",
        params={"slug": "example"},
    ).status_code == 410


def test_raw_debug_history_reads_are_retired():
    assert client.get("/v1/damage/scan/recent").status_code == 410
    assert client.get("/v1/resend/webhook/recent").status_code == 410
    assert client.get("/v1/seo/recent").status_code == 410
    assert client.get("/v1/swarms/events").status_code == 410


def test_swarm_soul_prompt_read_is_retired():
    response = client.get("/v1/swarm/prompt/commander")
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_swarm_prompt_retired_use_governed_agent_catalog"
    )


def test_single_legacy_lead_read_is_retired():
    response = client.get("/v1/leads/123")
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_single_lead_read_retired_use_v1_revenue_crm_prospects"
    )
