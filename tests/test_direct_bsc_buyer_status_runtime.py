"""Default-OFF status ASGI integration contract, without production services."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from empire_os.direct_bsc_buyer_status import BuyerAccessDenied,issue,fingerprint
from empire_os.direct_bsc_buyer_status_runtime import (
    create_staged_private_status_app,
)
from scripts.provision_direct_bsc_buyer_status_logins import READ_LOGIN

KEY=bytes(range(32))
DSN=("dbname=empiredb host=127.0.0.1 port=5432 "
     "user="+READ_LOGIN+" password=isolated-fixture-only")
TREASURY="0x1339b487046b0ad924a10c20b1791608ea8595a8"
NOW=datetime.now(timezone.utc)
ORDER=str(uuid4())
REQUEST=str(uuid4())
BUYER=str(uuid4())
token_blob=issue(key=KEY,order_id=ORDER,now=NOW-timedelta(minutes=1),
                 expires_at=NOW+timedelta(minutes=30))
TOKEN=token_blob["deliver_token_once"]
RECORD={
    "access":{**token_blob["persist_only"],"request_id":REQUEST},
    "order":{
        "id":ORDER,"buyer_id":BUYER,"state":"accepted","price_cents":24900,
        "commercial_payload":{
            "commercial_terms_sha256":"b"*64,
            "payer_wallet":"0x"+"1"*40,
        },
    },
    "payment":{
        "id":REQUEST,"buyer_id":BUYER,"fulfilment_order_id":ORDER,
        "settlement_mode":"direct","status":"pending",
        "amount_usdt":"249.00","commercial_terms_sha256":"b"*64,
        "payer_address":"0x"+"1"*40,"treasury_address":TREASURY,
        "approved_at":None,"approved_by":None,
        "expires_at":NOW+timedelta(minutes=35),
    },
    "evidence":None,
}


def create(**overrides):
    params={
        "reader_dsn":DSN,"hmac_key":KEY,"treasury_address":TREASURY,
        "allow_request":lambda peer:True,
        "read_by_fingerprint":lambda digest:RECORD,
    }
    params.update(overrides)
    return create_staged_private_status_app(**params)


def post(app,token=TOKEN):
    return TestClient(app).post(
       "/v1/checkout/payment-status",
       json={"token":token},
       headers={"origin":"https://empire-ai.co.uk",
                "content-type":"application/json"},
    )


def test_default_off_even_with_valid_bearer_never_queries_database():
    calls=[]
    app=create(read_by_fingerprint=lambda d:calls.append(d),
               allow_request=lambda peer:calls.append(peer))
    result=post(app)
    assert result.status_code==503
    assert result.json()=={"error":"buyer_status_unavailable"}
    assert calls==[]
    assert result.headers["cache-control"].startswith("no-store")
    assert "Bearer" not in result.text


@pytest.mark.parametrize("founder,chain",[(False,False),(True,False),(False,True)])
def test_requires_both_approval_and_fresh_chain_proof(founder,chain):
    calls=[]
    app=create(founder_release=lambda:founder,
               verified_chain=lambda:chain,
               read_by_fingerprint=lambda d:calls.append(d))
    assert post(app).status_code==503
    assert calls==[]


def test_approved_injected_status_only_returns_safe_projection():
    calls=[]
    app=create(founder_release=lambda:True,verified_chain=lambda:True,
               read_by_fingerprint=lambda d:calls.append(d) or RECORD)
    response=post(app)
    assert response.status_code==200
    assert response.json()=={"status":"awaiting_human_approval",
                            "payment_instructions_ready":False}
    assert calls==[fingerprint(TOKEN,KEY)]
    assert ORDER not in response.text
    assert TOKEN not in response.text
    assert BUYER not in response.text


def test_wrong_bearer_never_returns_cross_buyer_status():
    app=create(founder_release=lambda:True,verified_chain=lambda:True)
    impostor=issue(key=KEY,order_id=str(uuid4()),now=NOW-timedelta(minutes=1),
                   expires_at=NOW+timedelta(minutes=30))["deliver_token_once"]
    response=post(app,impostor)
    assert response.status_code==404
    assert response.json()=={"error":"payment_status_unavailable"}


@pytest.mark.parametrize("value",[
    "dbname=empiredb host=127.0.0.1 user=empiredb_app password=secret",
    "dbname=empiredb host=192.0.2.1 user="+READ_LOGIN+" password=secret",
    "dbname=empiredb host=127.0.0.1 port=5433 user="+READ_LOGIN+" password=secret",
    "dbname=empiredb host=127.0.0.1 hostaddr=192.0.2.2 user="+READ_LOGIN+" password=secret",
    "dbname=empiredb host=127.0.0.1 user="+READ_LOGIN,
    "",
])
def test_wrong_reader_identity_denied(value):
    with pytest.raises(BuyerAccessDenied):
        create(reader_dsn=value)


@pytest.mark.parametrize("override",[
    {"hmac_key":b"short"},
    {"hmac_key":""},
    {"treasury_address":"0x"+"0"*40},
    {"treasury_address":"0x"+"Z"*40},
    {"allow_request":None},
    {"read_by_fingerprint":"not_callable"},
])
def test_invalid_config_denied_before_mount(override):
    with pytest.raises(BuyerAccessDenied):
        create(**override)


def test_failing_release_callbacks_fail_closed():
    def problem():
        raise RuntimeError("SECRET_PRIVATE_FAILURE")
    for override in ({"founder_release":problem,"verified_chain":lambda:True},
                     {"founder_release":lambda:True,"verified_chain":problem}):
        res=post(create(**override))
        assert res.status_code==503
        assert "SECRET_PRIVATE_FAILURE" not in res.text


def test_no_automatic_public_mount_or_live_deployment():
    root=Path(__file__).resolve().parents[1]
    gateway=(root/"empire_os/public_gateway.py").read_text()
    checkout=(root/"empire_os/self_serve_checkout_api.py").read_text()
    for name in ("create_staged_private_status_app",
                 "create_private_buyer_status_router"):
        assert name not in gateway and name not in checkout
    source=(root/"empire_os/direct_bsc_buyer_status_runtime.py").read_text()
    for banned in ("uvicorn.run", "systemctl restart", "env_file",
                   "os.environ[", "issue_direct_bsc_buyer_status"):
        assert banned not in source
