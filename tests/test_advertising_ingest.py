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
            existing = self.rows[key]
            if existing["payload_sha256"] != item.payload_sha256:
                return {
                    "status": "conflict",
                    "reason": "provider_observation_payload_mismatch",
                    "observation_id": existing["observation_id"],
                }
            if (
                existing["canonical_creative_id"]
                != item.canonical_creative_id
            ):
                return {
                    "status": "conflict",
                    "reason": "provider_observation_creative_mismatch",
                    "observation_id": existing["observation_id"],
                }
            return {
                "status": "existing",
                "observation_id": existing["observation_id"],
            }
        observation_id = f"obs-{len(self.rows) + 1}"
        self.rows[key] = {
            "observation_id": observation_id,
            "payload_sha256": item.payload_sha256,
            "canonical_creative_id": item.canonical_creative_id,
        }
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


def body(
    *,
    provider_observation_id="google-obs-1",
    spend_cents=10000,
    canonical_creative_id=None,
):
    return {
        "canonical_campaign_id": "campaign-uuid-1",
        "provider_observation_id": provider_observation_id,
        "canonical_creative_id": canonical_creative_id,
        "row": {
            "platform": "google",
            "campaign_id": "external-campaign-1",
            "creative_id": "creative-external-1",
            "spend_cents": spend_cents,
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


def test_exact_observation_replay_is_idempotent():
    repo = FakeRepository()
    c = client(repo)
    first = c.post("/v1/advertising/observations/ingest", json=body())
    second = c.post("/v1/advertising/observations/ingest", json=body())
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "existing"
    assert len(repo.rows) == 1


def test_changed_metrics_with_same_provider_id_conflict():
    repo = FakeRepository()
    c = client(repo)
    first = c.post(
        "/v1/advertising/observations/ingest",
        json=body(spend_cents=10000),
    )
    second = c.post(
        "/v1/advertising/observations/ingest",
        json=body(spend_cents=12000),
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == (
        "provider_observation_payload_mismatch"
    )
    assert len(repo.rows) == 1


def test_canonical_creative_change_on_replay_conflicts():
    repo = FakeRepository()
    c = client(repo)
    first = c.post(
        "/v1/advertising/observations/ingest",
        json=body(canonical_creative_id="creative-uuid-1"),
    )
    second = c.post(
        "/v1/advertising/observations/ingest",
        json=body(canonical_creative_id="creative-uuid-2"),
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == (
        "provider_observation_creative_mismatch"
    )


def test_rpc_repository_preserves_unknown_attribution_and_provenance():
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
        json=body(canonical_creative_id="creative-uuid-1"),
    )
    assert response.status_code == 200
    params = calls[0][1]
    assert params["p_attributed_revenue_cents"] is None
    assert params["p_attributed_gross_profit_cents"] is None
    assert params["p_creative_id"] == "creative-uuid-1"
    assert params["p_evidence"]["platform"] == "google"
    assert params["p_evidence"]["external_creative_id"] == (
        "creative-external-1"
    )
    assert len(params["p_evidence"]["payload_sha256"]) == 64


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
