from fastapi import FastAPI
from fastapi.testclient import TestClient
from empire_os.quant_brain_api import create_quant_brain_router

def client():
    app=FastAPI(); app.include_router(create_quant_brain_router()); return TestClient(app)

def test_health_is_non_executing():
    b=client().get("/v1/quant-brain/health").json()
    assert b["execution_authority"]=="none"
    assert b["prediction_is_actual"] is False
    assert b["capital_execution"] is False

def test_economics_preview():
    r=client().post("/v1/quant-brain/economics/preview",json={"data":{
        "probability_success":.5,"conditional_revenue_cents":100000,
        "fixed_cost_cents":10000,"success_cost_cents":20000}})
    assert r.status_code==200
    assert r.json()["expected_gross_profit_cents"]==30000
    assert r.json()["actual_revenue"] is False

def test_unverified_bayes_update_fails_closed():
    r=client().post("/v1/quant-brain/bayes/beta/preview",json={"data":{
        "prior_alpha":1,"prior_beta":1,"successes":1,"failures":0,
        "verified_real_outcomes":False}})
    assert r.status_code==422


def test_health_advertises_decision_packet():
    body = client().get("/v1/quant-brain/health").json()
    assert "decision_packet" in body["capabilities"]
    assert "reliability_bins" in body["capabilities"]


def test_decision_packet_preview_fails_closed_when_missing():
    r = client().post(
        "/v1/quant-brain/decision-packet/preview",
        json={
            "data": {
                "candidate_id": "opp:missing",
                "inputs": {"probability_success": 0.4},
            }
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "UNAVAILABLE"
    assert r.json()["execution_authority"] == "none"


def test_decision_packet_preview_available():
    r = client().post(
        "/v1/quant-brain/decision-packet/preview",
        json={
            "data": {
                "candidate_id": "opp:ready",
                "trials": 500,
                "seed": 7,
                "inputs": {
                    "probability_success": 0.5,
                    "conditional_revenue_cents": 100000,
                    "fixed_cost_cents": 10000,
                    "success_cost_cents": 20000,
                    "revenue_low_cents": 90000,
                    "revenue_high_cents": 110000,
                    "success_cost_low_cents": 15000,
                    "success_cost_high_cents": 25000,
                    "uncertainty": 0.25,
                    "time_to_revenue_days": 14,
                    "confidence": 0.75,
                },
            }
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "AVAILABLE"
    assert body["actual_revenue"] is False
    assert body["capital_execution"] is False


def test_calibration_endpoints():
    payload = {"data": {"predictions": [0.8, 0.2], "outcomes": [1, 0]}}
    loss = client().post(
        "/v1/quant-brain/calibration/log-loss/preview",
        json=payload,
    )
    reliability = client().post(
        "/v1/quant-brain/calibration/reliability/preview",
        json={"data": {**payload["data"], "bins": 5}},
    )
    assert loss.status_code == 200
    assert reliability.status_code == 200
    assert loss.json()["execution_authority"] == "none"
    assert reliability.json()["execution_authority"] == "none"
