from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from empire_os.advertising_api import create_advertising_router
from empire_os.advertising_transport import (
    AdvertisingTransportError,
    PostgresAdvertisingObservationRpc,
    RpcAdvertisingObservationRepository,
)


class FakeRepository:
    def __init__(self):
        self.rows = {}

    def append(self, item):
        key = (item.canonical_campaign_id, item.provider_observation_id)
        if key in self.rows:
            return {
                "status": "existing",
                "observation_id": self.rows[key],
            }
        observation_id = f"obs-{len(self.rows) + 1}"
        self.rows[key] = observation_id
        return {
            "status": "recorded",
            "observation_id": observation_id,
        }


def client(repo=None):
    app = FastAPI()
    app.include_router(create_advertising_router(
        observation_repository=repo
    ))
    return TestClient(app)


def body():
    return {
        "canonical_campaign_id": "campaign-uuid-1",
        "provider_observation_id": "google-obs-1",
        "row": {
            "platform": "google",
            "campaign_id": "external-campaign-1",
            "creative_id": "creative-1",
            "spend_cents": 10000,
            "attributed_revenue_cents": None,
            "attributed_gross_profit_cents": None,
            "impressions": 1000,
            "clicks": 50,
            "conversions": None,
            "observed_at": "2026-09-19T20:55:00+00:00",
            "source": "google_ads_read_adapter",
        },
        "evidence": {"account_id": "account-1"},
    }


def test_unbound_ingest_fails_closed():
    response = client().post(
        "/v1/advertising/observations/ingest",
        json=body(),
    )
    assert response.status_code == 503


def test_observation_ingest_is_non_executing():
    response = client(FakeRepository()).post(
        "/v1/advertising/observations/ingest",
        json=body(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "recorded"
    assert payload["execution_authority"] == "none"
    assert payload["campaign_creation"] is False
    assert payload["budget_mutation"] is False
    assert payload["pause_mutation"] is False
    assert payload["retarget_execution"] is False


def test_observation_ingest_is_idempotent():
    repo = FakeRepository()
    c = client(repo)
    first = c.post("/v1/advertising/observations/ingest", json=body())
    second = c.post("/v1/advertising/observations/ingest", json=body())
    assert first.status_code == 200
    assert second.json()["status"] == "existing"
    assert len(repo.rows) == 1


def test_rpc_repository_preserves_unknown_attribution_as_none():
    calls = []

    def rpc(name, params):
        calls.append((name, params))
        return {"status": "recorded", "observation_id": "obs-1"}

    repo = RpcAdvertisingObservationRepository(rpc)
    app = FastAPI()
    app.include_router(create_advertising_router(
        observation_repository=repo
    ))
    response = TestClient(app).post(
        "/v1/advertising/observations/ingest",
        json=body(),
    )
    assert response.status_code == 200
    params = calls[0][1]
    assert params["p_attributed_revenue_cents"] is None
    assert params["p_attributed_gross_profit_cents"] is None
    assert params["p_evidence"]["platform"] == "google"


def test_transport_rejects_budget_or_campaign_rpc_before_connect():
    rpc = PostgresAdvertisingObservationRpc(
        "postgresql://example",
        connect_factory=lambda dsn: (_ for _ in ()).throw(
            AssertionError("must not connect")
        ),
    )
    with pytest.raises(
        AdvertisingTransportError,
        match="cannot execute",
    ):
        rpc("update_ad_campaign_budget", {})
