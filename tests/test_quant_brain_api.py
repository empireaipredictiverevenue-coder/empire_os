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
