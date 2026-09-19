from fastapi.testclient import TestClient

from empire_os.hub import app


client = TestClient(app)


def test_legacy_crm_lead_update_is_retired():
    response = client.post(
        "/v1/crm/leads/1",
        json={"status": "qualified"},
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_crm_lead_update_retired_use_revenue_crm_governed_state_flow"
    )


def test_legacy_crm_status_update_is_retired():
    response = client.post(
        "/v1/crm/leads/1/status",
        json={"status": "qualified"},
    )
    assert response.status_code == 410


def test_legacy_crm_enrichment_writes_are_retired():
    assert client.post("/v1/crm/leads/1/enrich").status_code == 410
    assert client.post("/v1/crm/leads/batch-enrich").status_code == 410


def test_legacy_lane_import_is_retired():
    response = client.post("/v1/crm/import-lane-leads")
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_crm_lane_import_retired_use_canonical_prospect_intake"
    )


def test_legacy_icp_mutation_routes_are_retired():
    batch = client.post("/v1/crm/icp/batch")
    refresh = client.post("/v1/crm/icp/score/1")
    assert batch.status_code == 410
    assert refresh.status_code == 410
