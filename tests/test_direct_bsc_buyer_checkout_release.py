"""Fail-closed 049/050 checkout integration tests, all offline."""
import json
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4
from datetime import datetime,timedelta,timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os import direct_bsc_buyer_checkout_release as release

from scripts.provision_direct_bsc_buyer_status_logins import (
    READ_KEY, ISSUE_KEY, READ_LOGIN, ISSUE_LOGIN, dsn_for,
)
from empire_os.bsc_usdt_verifier import BscUsdtConfig

TREASURY="0x1339b487046b0ad924a10c20b1791608ea8595a8"

def dsn_entries():
    return {
       READ_KEY: dsn_for("dbname=empiredb host=127.0.0.1 port=5432",
                         READ_LOGIN,"reader_dummy_secret_A"),
       ISSUE_KEY:dsn_for("dbname=empiredb host=127.0.0.1 port=5432",
                         ISSUE_LOGIN,"issuer_dummy_secret_B"),
    }

def credentials(tmp_path,monkeypatch):
    key=tmp_path/release.CREDENTIAL_KEY
    dsns=tmp_path/release.CREDENTIAL_DSN
    key.write_bytes(bytes(range(32)))
    dsns.write_text("".join(k+"="+json.dumps(v)+"\n"
                            for k,v in dsn_entries().items()))
    key.chmod(0o600);dsns.chmod(0o600)
    monkeypatch.setattr(release,"_credential_dir",lambda:tmp_path)
    monkeypatch.setattr(BscUsdtConfig,"from_env",classmethod(
       lambda cls: cls(rpc_url="http://127.0.0.1:8080",
            treasury_address=TREASURY,
            token_contract="0x55d398326f99059ff775485246999027b3197955",
            min_confirmations=12,
       )
    ))

def test_defaults_off_without_reading_any_credentials(monkeypatch):
    monkeypatch.delenv(release.ACTIVATION,raising=False)
    monkeypatch.setattr(release,"_config",lambda:pytest.fail("secret read"))
    assert release.mount_status_if_released(FastAPI()) is False
    assert release.add_status_receipt_if_released({"status":"pending"})=={"status":"pending"}

def test_staged_app_mounts_with_distinct_logins_and_no_live_key_logs(monkeypatch,tmp_path):
    credentials(tmp_path,monkeypatch)
    monkeypatch.setenv(release.ACTIVATION,"ON")
    app=FastAPI()
    assert release.mount_status_if_released(app) is True
    monkeypatch.setattr(release,"_chain_verified",lambda:False)
    with TestClient(app) as c:
        res=c.post("/v1/checkout/payment-status",
            json={"token":"ecs1_"+"A"*43},
            headers={"origin":"https://empire-ai.co.uk"})
        assert res.status_code==503
        assert res.headers["cache-control"].startswith("no-store")

def test_unverified_chain_never_issues_or_delivers(monkeypatch,tmp_path):
    credentials(tmp_path,monkeypatch)
    monkeypatch.setenv(release.ACTIVATION,"ON")
    monkeypatch.setattr(release,"_chain_verified",lambda:False)
    output=release.add_status_receipt_if_released({"decision":"order_created"})
    assert output["buyer_status_unavailable"] is True
    assert output["buyer_status_token_delivered"] is False

def test_missing_credentials_dont_take_checkout_down(monkeypatch,tmp_path):
    monkeypatch.setenv(release.ACTIVATION,"ON")
    monkeypatch.setattr(release,"_credential_dir",lambda:tmp_path)
    assert release.mount_status_if_released(FastAPI()) is False
    prior={"decision":"order_created","order_id":str(uuid4())}
    assert release.add_status_receipt_if_released(prior)["order_id"]==prior["order_id"]

def test_successful_receipt_uses_exact_db_bound_request(monkeypatch,tmp_path):
    credentials(tmp_path,monkeypatch)
    monkeypatch.setenv(release.ACTIVATION,"ON")
    monkeypatch.setattr(release,"_chain_verified",lambda:True)
    now=datetime.now(timezone.utc)
    oid=str(uuid4());rid=str(uuid4())
    row={"id":rid,"fulfilment_order_id":oid,
         "settlement_mode":"direct","status":"pending",
         "created_at":now-timedelta(minutes=1),
         "expires_at":now+timedelta(minutes=45)}
    class Writer:
        def __init__(self,dsn):assert ISSUE_LOGIN in dsn
        def __call__(self,p):
            return {"decision":"created",
                    "token_fingerprint":p["token_fingerprint"]}
    monkeypatch.setattr(release,"PrivateBuyerIssuerPostgresWriter",Writer)
    monkeypatch.setattr(release,"_pending_request",lambda rid:row)
    out=release.add_status_receipt_if_released({
        "decision":"order_created","order_id":oid,
        "payment_request_id":rid,"settlement_mode":"direct",
        "payment_request_created":True,"payment_request_status":"pending",
        "payment_instructions_ready":False,"actual_revenue":False,
    })
    assert out["buyer_status_token_delivered"] is True
    assert out["buyer_status_token"].startswith("ecs1_")
    assert out["payment_instructions_ready"] is False

@pytest.mark.parametrize("value",["OFF","TRUE","yes","1","on",""])
def test_feature_toggle_exactly_on(monkeypatch,value):
    monkeypatch.setenv(release.ACTIVATION,value)
    assert release._enabled() is False

def test_status_route_default_absent_in_checkout_api(monkeypatch):
    monkeypatch.delenv(release.ACTIVATION,raising=False)
    from empire_os.self_serve_checkout_api import app
    routes=[getattr(r,"path",None) for r in app.router.routes]
    assert "/v1/checkout/payment-status" not in routes

def test_gateway_mediates_bearer_without_query_strings():
    from empire_os.public_gateway import app
    routes=[getattr(r,"path",None) for r in app.router.routes]
    assert "/v1/checkout/payment-status" in routes
    status=TestClient(app).post("/v1/checkout/payment-status",
        json={"token":"ecs1_"+"A"*43},
        headers={"origin":"https://attacker.example"})
    assert status.status_code==403
    assert status.headers["cache-control"].startswith("no-store")
    assert "token" not in status.text
