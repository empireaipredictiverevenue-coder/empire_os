from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.founder_objectives_api import (
    create_founder_objectives_router,
)


def client():
    app = FastAPI()
    app.include_router(create_founder_objectives_router())
    return TestClient(app)


def test_catalog_defaults_to_current_authoritative_objectives():
    response = client().get("/v1/founder-objectives/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "current"
    assert payload["execution_allowed"] is False
    assert payload["objectives"][0]["key"] == "F1"
    assert all(
        kr["target_confirmed"] is True
        for obj in payload["objectives"]
        for kr in obj["key_results"]
    )


def test_legacy_catalog_is_reference_only_and_unconfirmed():
    response = client().get(
        "/v1/founder-objectives/catalog?scope=legacy"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "legacy"
    assert payload["objectives"][0]["key"] == "O1"
    assert all(
        kr["target_confirmed"] is False
        for obj in payload["objectives"]
        for kr in obj["key_results"]
    )


def test_preview_scores_canonical_evidence_without_side_effects():
    response = client().post(
        "/v1/founder-objectives/preview",
        json={
            "cycle": "2026-Q3",
            "evidence": {
                "commercial_buyer_conversations": {
                    "value": 1,
                    "observed_at": "2026-09-20T23:40:00Z",
                    "evidence_refs": ["canonical:buyer_conversation"],
                    "source": "commercial_loop",
                    "state": "observed",
                }
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "OBSERVE"
    assert payload["execution_allowed"] is False
    assert (
        payload["objectives"][0]["key_results"][0]["progress"]
        == 1.0
    )
