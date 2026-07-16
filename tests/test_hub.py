"""
Tests for the Empire OS Hub FastAPI server.
"""

import pytest
from starlette.testclient import TestClient

from empire_os.hub import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHubHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "online"
        assert data["engine"] == "empire-os-v3"


class TestLeadPipeline:
    def test_incoming_lead(self, client):
        resp = client.post(
            "/v1/pipeline/incoming",
            json={
                "niche": "roofing",
                "details": "Commercial warehouse storm damage hail leak multi-unit repair",
                "phone": "555-123-4567",
                "zip_code": "33101",
                "name": "ABC Roofing",
                "source": "test",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("accepted", "rejected")

    def test_incoming_lead_missing_data(self, client):
        resp = client.post(
            "/v1/pipeline/incoming",
            json={"niche": "roofing"},  # no phone, no details
        )
        assert resp.status_code == 400


class TestFunnel:
    def test_funnel_counts(self, client):
        resp = client.get("/v1/funnel/counts")
        assert resp.status_code == 200
        data = resp.json()
        assert "discovered" in data

    def test_funnel_prospect_not_found(self, client):
        resp = client.get("/v1/funnel/prospect/no_such")
        assert resp.status_code == 404
        data = resp.json()
        assert "not found" in data["detail"].lower()

    def test_funnel_states(self, client):
        resp = client.get("/v1/funnel/states")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "prospects" in data


class TestTraffic:
    def test_traffic_status(self, client):
        resp = client.get("/v1/traffic/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "by_state" in data
        assert "total" in data


class TestCEO:
    def test_ceo_brief(self, client):
        resp = client.get("/v1/ceo/brief")
        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data
        assert "headline" in data
        assert "funnel" in data
        assert "decisions" in data


class TestMarketing:
    def test_marketing_draft(self, client):
        resp = client.get("/v1/marketing/draft/hvac")
        assert resp.status_code == 200
        data = resp.json()
        assert data["niche"] == "hvac"

    def test_marketing_tick(self, client):
        resp = client.post("/v1/marketing/tick")
        assert resp.status_code == 200
        data = resp.json()
        assert "scanned" in data


class TestAgiSales:
    def test_sales_state(self, client):
        resp = client.get("/v1/agi/sales/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent"] == "agi-sales"

    def test_sales_deals(self, client):
        resp = client.get("/v1/agi/sales/deals")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "deals" in data


class TestAgiCloser:
    def test_closer_state(self, client):
        resp = client.get("/v1/agi/closer/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent"] == "agi-closer"

    def test_closer_endpoint_exists(self, client):
        """Just verify the endpoint is wired without triggering LLM."""
        resp = client.get("/v1/agi/closer/state")
        assert resp.status_code == 200


class TestDecisions:
    def test_decisions_list(self, client):
        resp = client.get("/v1/decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data
        assert "decisions" in data
        assert isinstance(data["decisions"], list)

    def test_decision_approve_404(self, client):
        """Approving a non-existent prospect returns 404."""
        resp = client.post("/v1/decisions/no_such_id/approve")
        assert resp.status_code == 404

    def test_decision_deny_404(self, client):
        """Denying a non-existent prospect returns 404."""
        resp = client.post("/v1/decisions/no_such_id/deny")
        assert resp.status_code == 404


class TestDashboard:
    def test_dashboard_page(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Empire OS v3" in resp.text

    def test_dashboard_data(self, client):
        resp = client.get("/v1/dashboard/data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["engine"] == "Empire OS"
        assert "funnel" in data
        assert "funnel_total" in data


class TestTelegramRoutes:
    def test_telegram_brief_no_token(self, client):
        resp = client.post("/v1/telegram/brief", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False  # no token configured

    def test_telegram_alert_no_token(self, client):
        resp = client.post("/v1/telegram/alert", json={}, params={"message": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False


class TestWaterfallRoutes:
    def test_leads_enrich(self, client):
        resp = client.post(
            "/v1/leads/enrich",
            json={"company": "Acme Roofing", "phone": "555-1234"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # All providers are unconfigured by default, so should fail validation
        assert "success" in data
        assert "providers_tried" in data
        assert "cost_cents" in data

    def test_waterfall_metrics(self, client):
        resp = client.get("/v1/waterfall/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_runs" in data
        assert "by_provider" in data
