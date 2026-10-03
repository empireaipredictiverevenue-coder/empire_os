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



def test_founder_deliverability_route_exposes_production_readiness_snapshot():
    app = FastAPI()
    app.include_router(
        create_founder_outbound_deliverability_router(
            FakeProvider(),
            repository=None,
            readiness_provider=lambda: {
                "status": "OBSERVE_OPERATIONAL",
                "send_authorized": False,
                "activation": {
                    "live_send": {"status": "BLOCKED"}
                },
            },
        )
    )
    response = TestClient(app).get("/v1/founder-outbound-deliverability")
    assert response.status_code == 200
    readiness = response.json()["production_readiness"]
    assert readiness["status"] == "OBSERVE_OPERATIONAL"
    assert readiness["send_authorized"] is False


def test_readiness_provider_failure_does_not_hide_deliverability_health():
    def fail():
        raise RuntimeError("snapshot unavailable")

    app = FastAPI()
    app.include_router(
        create_founder_outbound_deliverability_router(
            FakeProvider(),
            repository=None,
            readiness_provider=fail,
        )
    )
    response = TestClient(app).get("/v1/founder-outbound-deliverability")
    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_health"] == "GREEN"
    assert payload["production_readiness"]["status"] == "UNAVAILABLE"
    assert payload["production_readiness"]["send_authorized"] is False
    assert payload["production_readiness"]["error_type"] == "RuntimeError"
