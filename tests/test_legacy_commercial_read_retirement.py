from fastapi.testclient import TestClient

from empire_os.hub import app


client = TestClient(app)


def test_legacy_outreach_and_sample_reads_are_retired():
    assert client.get(
        "/v1/leads/sample",
        params={"niche": "roofing", "metro": "London"},
    ).status_code == 410
    assert client.get("/v1/outreach/prospect/prospect-1").status_code == 410


def test_legacy_commercial_pricing_reads_are_retired():
    assert client.get("/v1/buyers/seat-tiers").status_code == 410
    assert client.get("/v1/prompts/tiers").status_code == 410


def test_legacy_tenant_and_payout_reads_are_retired():
    assert client.get("/v1/tenants/tenant-1").status_code == 410
    assert client.get("/v1/payouts/status").status_code == 410
    assert client.get("/v1/payouts/sign-tx").status_code == 410
    assert client.get("/v1/payouts/tx-base64").status_code == 410


def test_legacy_lane_reads_are_retired():
    assert client.get("/v1/lanes/lane-1").status_code == 410
    assert client.get("/v1/lanes/leads/pending").status_code == 410
    assert client.get("/v1/lanes/leads/by-source").status_code == 410
    assert client.get("/v1/lanes/score/prospect-1").status_code == 410


def test_legacy_ppc_and_crm_analytics_reads_are_retired():
    assert client.get("/v1/ppc/invoices").status_code == 410
    assert client.get("/v1/crm/analytics").status_code == 410
    assert client.get("/v1/crm/revenue-analytics").status_code == 410


def test_legacy_swarm_ledger_is_retired():
    response = client.get("/v1/swarm/ledger")
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "legacy_swarm_ledger_retired_use_canonical_observability"
    )
