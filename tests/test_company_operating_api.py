from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.company_operating_api import create_company_operating_router


def client():
    app = FastAPI()
    app.include_router(create_company_operating_router())
    return TestClient(app)


def test_health_is_observe_only():
    body = client().get("/v1/company-ops/health").json()
    assert body["execution_authority"] == "none"
    assert body["marketing_execution"] is False
    assert body["rd_production_deployment"] is False


def test_rd_review_api_does_not_launch_product():
    body = client().post(
        "/v1/company-ops/rd/candidate/review",
        json={"data": {
            "research_id": "r1",
            "stage": "prototype",
            "hypothesis": "Prototype can improve search ranking quality.",
            "evidence_refs": ["e:1"],
        }},
    ).json()
    assert body["product_launch"] is False
    assert body["production_deployment"] is False


def test_marketing_review_api_keeps_spend_disabled():
    body = client().post(
        "/v1/company-ops/marketing/brief/review",
        json={"data": {
            "campaign_id": "c1",
            "objective": "Demand",
            "audience": "buyers",
            "product": "Predictive Revenue",
            "offer": "demo",
            "success_metric": "qualified opportunities",
            "evidence_refs": ["e:1"],
            "attribution_plan": {"model": "event"},
        }},
    ).json()
    assert body["review_ready"] is True
    assert body["outbound_enabled"] is False
    assert body["paid_spend_enabled"] is False
