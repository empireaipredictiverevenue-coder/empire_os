from fastapi.testclient import TestClient

from empire_os.hub import app


client = TestClient(app)


def test_legacy_lead_and_stats_reads_are_retired():
    assert client.get("/v1/leads").status_code == 410
    assert client.get("/v1/stats/leads").status_code == 410
    assert client.get("/v1/stats/revenue").status_code == 410


def test_legacy_homeowner_and_carrier_reads_are_retired():
    assert client.get("/v1/homeowner/jobs").status_code == 410
    assert client.get("/v1/homeowner/jobs/1").status_code == 410
    assert client.get("/v1/homeowner/pipeline/stats").status_code == 410
    assert client.get("/v1/homeowner/pipeline/timeline/1").status_code == 410
    assert client.get("/v1/carrier-applications").status_code == 410
    assert client.get("/v1/carrier-applications/1").status_code == 410


def test_legacy_lane_and_ppc_reads_are_retired():
    assert client.get("/v1/lanes").status_code == 410
    assert client.get("/v1/ppc/buyer_pms").status_code == 410
    assert client.get("/v1/ppc/charges").status_code == 410


def test_legacy_crm_read_model_is_retired():
    paths = [
        "/v1/crm/leads",
        "/v1/crm/leads/1",
        "/v1/crm/pipeline",
        "/v1/crm/enrichment-stats",
        "/v1/crm/qualification-summary",
        "/v1/crm/icp/analytics",
        "/v1/crm/icp/score/1",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 410, (path, response.text)


def test_replacement_hints_are_explicit():
    assert client.get("/v1/leads").json()["detail"] == (
        "legacy_lead_list_retired_use_v1_revenue_crm_prospects"
    )
    assert client.get("/v1/lanes").json()["detail"] == (
        "legacy_lane_list_retired_use_v1_revenue_exchange_markets"
    )
    assert client.get("/v1/ppc/charges").json()["detail"] == (
        "legacy_ppc_charge_read_retired_use_v1_advertising_observations"
    )
