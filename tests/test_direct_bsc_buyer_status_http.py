"""Private HTTP payment-status handler tests: default OFF, origin and token isolation."""
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.direct_bsc_buyer_status import issue, fingerprint
from empire_os.direct_bsc_buyer_status_http import (
    create_private_buyer_status_router,HEADERS,
)

NOW=datetime(2026,10,13,19,tzinfo=timezone.utc)
KEY=bytes(range(32))
ORDER=str(uuid4())
BUYER=str(uuid4())
REQUEST=str(uuid4())
TREASURY="0x1339b487046b0ad924a10c20b1791608ea8595a8"
minted=issue(key=KEY,order_id=ORDER,now=NOW-timedelta(minutes=6),
             expires_at=NOW+timedelta(hours=1))
TOKEN=minted["deliver_token_once"]
record={
    "access":{
        **minted["persist_only"],
        "request_id":REQUEST,
    },
    "order":{
        "id":ORDER,"buyer_id":BUYER,
        "state":"accepted","price_cents":24900,
        "commercial_payload":{
            "payer_wallet":"0x"+"1"*40,
            "commercial_terms_sha256":"a"*64,
        },
    },
    "payment":{
        "id":REQUEST,"buyer_id":BUYER,
        "fulfilment_order_id":ORDER,"settlement_mode":"direct",
        "commercial_terms_sha256":"a"*64,
        "payer_address":"0x"+"1"*40,
        "treasury_address":TREASURY,
        "amount_usdt":"249.00","status":"pending",
        "approved_by":None,"approved_at":None,
        "expires_at":NOW+timedelta(minutes=40),
    },
    "evidence":None,
}


def client(enabled=False,lookup=None,limiter=None,now=None):
    app=FastAPI()
    app.include_router(create_private_buyer_status_router(
        origin="https://empire-ai.co.uk",
        authorized=lambda:enabled,
        allow_request=limiter or (lambda peer:True),
        hmac_key=KEY,approved_treasury=TREASURY,
        read_by_fingerprint=lookup or (lambda digest:record),
        now=now or (lambda:NOW),
    ))
    return TestClient(app)


def post(c,payload=None,headers=None):
    base={"Origin":"https://empire-ai.co.uk","Content-Type":"application/json"}
    if headers:base.update(headers)
    return c.post("/v1/checkout/payment-status",
                  json={"token":TOKEN} if payload is None else payload,
                  headers=base)


def test_default_off_never_calls_database_or_limiter():
    observed=[]
    c=client(lookup=lambda d:observed.append(d),limiter=lambda p:observed.append(p))
    response=post(c)
    assert response.status_code==503
    assert response.json()=={"error":"buyer_status_unavailable"}
    assert observed==[]
    for key,val in HEADERS.items():
        assert response.headers[key]==val


def test_correct_token_success_only_bounded_status_and_no_pii():
    observed=[]
    c=client(enabled=True,lookup=lambda d:observed.append(d) or record)
    response=post(c)
    assert response.status_code==200
    assert response.json()=={
        "status":"awaiting_human_approval",
        "payment_instructions_ready":False,
    }
    assert observed==[fingerprint(TOKEN,KEY)]
    assert TOKEN not in str(response.json())
    assert ORDER not in str(response.json())
    assert response.headers["cache-control"].startswith("no-store")


@pytest.mark.parametrize("changes,expected",[
    ({"Origin":"https://attacker.example"},403),
    ({"Sec-Fetch-Site":"cross-site"},403),
    ({"Content-Type":"text/plain"},415),
])
def test_origin_and_content_type_rejected_pre_database(changes,expected):
    called=[]
    r=post(client(enabled=True,lookup=lambda d:called.append(d)),
           headers=changes)
    assert r.status_code==expected
    assert called==[]


def test_refuses_unknown_bearer_and_cross_buyer_without_disclosure():
    unknown="ecs1_"+("A"*43)
    responses=[]
    for data in (
        {"token":unknown},
        {"token":TOKEN,"order_id":ORDER},
        {"order_id":ORDER},
        {"token":TOKEN,"debug":True},
    ):
        response=post(client(enabled=True,lookup=lambda d:None),payload=data)
        responses.append(response)
        assert response.status_code==404
        assert response.json()=={"error":"payment_status_unavailable"}
    assert all(r.headers["cache-control"].startswith("no-store") for r in responses)


def test_oversize_body_denied_without_db():
    calls=[]
    c=client(enabled=True,lookup=lambda d:calls.append(d))
    r=post(c,payload={"token":TOKEN+"x"*600})
    assert r.status_code==413
    assert calls==[]


def test_rate_limit_uses_trusted_peer_not_spoofable_headers():
    allowed=[]
    c=client(enabled=True,limiter=lambda peer:allowed.append(peer) or False)
    r=post(c,headers={"X-Forwarded-For":"1.2.3.4"})
    assert r.status_code==429
    assert allowed==["testclient"]


def test_failure_uses_uniform_404_and_does_not_expose_driver_error():
    def explode(_digest):
        raise RuntimeError("password=PRIVATE;buyer=SECRET")
    response=post(client(enabled=True,lookup=explode))
    assert response.status_code==404
    assert response.json()=={"error":"payment_status_unavailable"}
    assert "PRIVATE" not in response.text
    assert "SECRET" not in response.text


def test_duplicate_json_keys_denied():
    c=client(enabled=True)
    r=c.post("/v1/checkout/payment-status",
             content=json.dumps({"token":TOKEN})[:-1]+',"token":"'+TOKEN+'"}',
             headers={"origin":"https://empire-ai.co.uk",
                      "content-type":"application/json"})
    assert r.status_code==404


def test_expiry_and_revocation_fail_closed():
    for expired, revoked in ((True,False),(False,True)):
        payload=json.loads(json.dumps(record,default=str))
        if expired:payload["access"]["expires_at"]=(NOW-timedelta(seconds=1)).isoformat()
        if revoked:payload["access"]["revoked_at"]=NOW.isoformat()
        r=post(client(enabled=True,lookup=lambda digest:payload))
        assert r.status_code==404
        assert r.json()=={"error":"payment_status_unavailable"}
