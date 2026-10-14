"""Read-only live canary and complete IN-MEMORY buyer status flow."""
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from pathlib import Path

import pytest

from scripts import probe_direct_bsc_first_buyer_readonly as smoke
from scripts import deploy_direct_bsc_buyer_status_release as release
from empire_os import direct_bsc_buyer_checkout_release as checkout
from empire_os.direct_bsc_buyer_receipt_bridge import with_new_buyer_status_receipt
from empire_os.direct_bsc_buyer_status import fingerprint
from empire_os.direct_bsc_buyer_status_private_reader import project_private_buyer_status

TREASURY="0x1339b487046b0ad924a10c20b1791608ea8595a8"
KEY=bytes(range(32))


def fixtures():
    return {
        "catalog":{
            "binding_order_creation_authorized":True,
            "payment_proposal_authorized":True,
            "checkout_settlement_mode":"direct",
            "actual_revenue":False,
            "products":[{}, {}, {}, {}],
        },
        "health":{
            "status":"online","payment_execution":False,
            "revenue_recognition":False,
            "binding_order_creation_authorized":True,
            "payment_proposal_authorized":True,
        },
        "buy":b"<!doctype html><html><body>Verified buyer checkout</body></html>",
        "chain":{
            "chain_verified":True,"chain_id":56,
            "token_decimals":18,"status":"FRESH_BSC_MAINNET_USDT_ANCHOR",
            "block_age_seconds":3.0,
        },
    }


def run(monkeypatch,overrides=None):
    data=fixtures()
    for name,value in (overrides or {}).items():
        data[name]=value
    events=[]
    monkeypatch.setattr(release,"_published_checkout_verified",
                        lambda:events.append("assets"))
    def fetch(url,*,page=False):
        events.append("GET_"+url.rsplit("/",1)[-1])
        return data["buy"] if page else (data["catalog"] if url==smoke.CATALOG else data["health"])
    def denied(url):
        events.append("POST_RESERVED_TOKEN_"+url.split("/")[2])
        return True
    output=smoke.inspect(fetch=fetch,unknown_denied=denied,
                         chain=lambda **_:data["chain"])
    return output,events


def test_readonly_live_canary_full_contract(monkeypatch):
    result,events=run(monkeypatch)
    assert result["status"]=="CHECKOUT_BUYER_READONLY_CANARY_VERIFIED"
    assert result["real_orders_submitted"]==0
    assert result["status_tokens_issued"]==0
    assert result["revenue_recognition"] is False
    assert result["private_unknown_token_denied"] is True
    assert len([e for e in events if e.startswith("POST")])==2
    assert "assets" in events


@pytest.mark.parametrize("drift",[
    {"catalog":{"binding_order_creation_authorized":False}},
    {"health":{"payment_execution":True}},
    {"chain":{"chain_id":97}},
    {"buy":b"not html"},
])
def test_untrusted_missing_data_held(monkeypatch,drift):
    sample=fixtures()
    name=list(drift)[0]
    original=sample.get(name)
    value=drift[name]
    if type(value) is dict:
        updated={**original,**value}
    else:
        updated=value
    result,events=run(monkeypatch,{name:updated})
    assert result["status"]=="CHECKOUT_BUYER_READONLY_CANARY_HELD"
    assert result["real_orders_submitted"]==0
    assert result["payment_execution"] is False
    assert "error" not in result


def test_lookup_normalizes_canonical_timestamp_strings(monkeypatch):
    order=str(uuid4());request=str(uuid4())
    now=datetime.now(timezone.utc)
    calls=[]
    def fake(verb,path):
        calls.append((verb,path))
        return [{
            "id":request,"fulfilment_order_id":order,
            "settlement_mode":"direct","status":"pending",
            "created_at":now.isoformat(),
            "expires_at":(now+timedelta(hours=1)).isoformat(),
        }]
    from empire_os import sb
    monkeypatch.setattr(sb,"request_json",fake)
    result=checkout._pending_request(request)
    assert result["id"]==request
    assert result["created_at"]==now
    assert result["expires_at"]==now+timedelta(hours=1)
    assert len(calls)==1 and calls[0][0]=="GET"
    assert "&limit=1" in calls[0][1]


def test_complete_order_receipt_to_readonly_status_in_memory_only():
    now=datetime.now(timezone.utc)
    oid,rid,buyer=str(uuid4()),str(uuid4()),str(uuid4())
    payer="0x"+"1"*40
    terms="c"*64
    created=now-timedelta(minutes=1)
    expires=now+timedelta(minutes=40)
    evidence={
        "id":rid,"fulfilment_order_id":oid,
        "settlement_mode":"direct","status":"pending",
        "created_at":created,"expires_at":expires,
    }
    commits=[]
    def store(payload):
        commits.append(dict(payload))
        return {
            "decision":"created",
            "token_fingerprint":payload["token_fingerprint"],
        }
    body=with_new_buyer_status_receipt(
        {
            "decision":"order_created","order_id":oid,
            "payment_request_id":rid,
            "settlement_mode":"direct","payment_request_created":True,
            "payment_request_status":"pending",
            "payment_instructions_ready":False,"actual_revenue":False,
        },
        enabled=True,
        hmac_key=KEY,
        request_lookup=lambda given:evidence if given==rid else None,
        persist_fingerprint=store,now=now,
    )
    assert body["buyer_status_token_delivered"] is True
    assert len(commits)==1
    bearer=body["buyer_status_token"]
    assert fingerprint(bearer,KEY)==commits[0]["token_fingerprint"]
    record={
        "access":{
            "token_fingerprint":commits[0]["token_fingerprint"],
            "order_id":oid,"request_id":rid,
            "issued_at":now.isoformat(),
            "expires_at":commits[0]["expires_at"].isoformat(),
            "revoked_at":None,
        },
        "order":{
            "id":oid,"buyer_id":buyer,"state":"accepted",
            "price_cents":24900,
            "commercial_payload":{
                "commercial_terms_sha256":terms,"payer_wallet":payer,
            },
        },
        "payment":{
            "id":rid,"buyer_id":buyer,"fulfilment_order_id":oid,
            "settlement_mode":"direct",
            "commercial_terms_sha256":terms,
            "payer_address":payer,"treasury_address":TREASURY,
            "amount_usdt":"249.00","status":"pending",
            "approved_by":None,"approved_at":None,
            "expires_at":expires.isoformat(),
        },
        "evidence":None,
    }
    projection=project_private_buyer_status(
        bearer_token=bearer,hmac_key=KEY,
        read_by_fingerprint=lambda digest: record if digest==fingerprint(bearer,KEY) else None,
        approved_treasury=TREASURY,now=now,
    )
    assert projection=={
        "status":"awaiting_human_approval",
        "payment_instructions_ready":False,
    }
    assert bearer not in str(commits)
    assert "amount_usdt" not in projection
    assert "buyer_id" not in projection


def test_module_has_no_live_order_write_or_mail():
    source=Path(smoke.__file__).read_text()
    for blocked in ('"/v1/checkout/orders"',"'POST' /v1/checkout/orders",
                    "install_key(", "send_mail(", "create_order(",
                    "submit_payment_proposal(", "UPDATE public."):
        assert blocked not in source
    assert "POST" in source and "UNKNOWN" in source
