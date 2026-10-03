from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.founder_outbound_deliverability_api import (
    create_founder_outbound_deliverability_router,
)


class FakeProvider:
    def metrics(self, *, start: datetime, end: datetime, granularity="daily"):
        return {
            "data": [{
                "domain_name": "mail.example.com",
                "sent": 100,
                "delivered": 100,
                "bounced": 0,
                "complained": 0,
            }]
        }


def test_founder_deliverability_route_is_read_only_snapshot():
    app = FastAPI()
    app.include_router(create_founder_outbound_deliverability_router(FakeProvider()))
    response = TestClient(app).get("/v1/founder-outbound-deliverability")
    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_health"] == "GREEN"
    assert set(payload["windows"]) == {"1d", "7d", "30d"}



class FakeRepository:
    def decisions(self, *, limit):
        assert limit == 1
        return [{
            "id": "decision-1",
            "posture": "READY",
            "observed_at": "2026-10-03T12:00:00+00:00",
        }]

    def observations(self, *, limit):
        assert limit == 500
        return [{
            "id": "observation-1",
            "observed_at": "2026-10-03T12:00:00+00:00",
            "domain": "mail.example.com",
            "metric_name": "bounce_rate",
            "metric_value": 0.01,
            "source": "resend",
        }]


def test_founder_deliverability_route_exposes_canonical_empiredb_history():
    app = FastAPI()
    app.include_router(
        create_founder_outbound_deliverability_router(
            FakeProvider(),
            FakeRepository(),
        )
    )
    response = TestClient(app).get("/v1/founder-outbound-deliverability")
    assert response.status_code == 200
    payload = response.json()
    canonical = payload["canonical_evidence_store"]
    assert canonical["configured"] is True
    assert canonical["latest_decision"]["posture"] == "READY"
    assert (
        canonical["replay"]["assets"]["mail.example.com"]["metrics"]["bounce_rate"]
        == 0.01
    )
