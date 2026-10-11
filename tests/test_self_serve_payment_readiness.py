"""Checkout payment preflight: safe fail-close BEFORE any canonical order write."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID
import pytest
from fastapi.testclient import TestClient

import empire_os.self_serve_checkout_api as checkout_api
import empire_os.self_serve_checkout as checkout
from empire_os.bsc_usdt_verifier import BSC_USDT_CONTRACT, BscUsdtConfig
from empire_os.self_serve_payment_readiness import (
    CheckoutPaymentPreflightHold, checkout_bsc_config_snapshot,
    verify_checkout_bsc_chain,
)

NOW = datetime(2026, 10, 11, 23, tzinfo=timezone.utc)
TREASURY = "0x" + "a" * 40
PAYER = "0x" + "b" * 40
BLOCK_HASH = "0x" + "c" * 64
CONFIG = BscUsdtConfig(
    rpc_url="http://127.0.0.1:8545",
    treasury_address=TREASURY,
    token_contract=BSC_USDT_CONTRACT,
)

def mock_rpc(*, chain="0x38", token_decimals=18, block_timestamp=None, fail=False):
    seen=[]
    stamp=int((block_timestamp or NOW).timestamp())
    values = {
        "eth_chainId": chain,
        "eth_blockNumber": "0x140",
        "eth_getBlockByNumber": {
            "number":"0x140", "hash":BLOCK_HASH,"timestamp":hex(stamp),
        },
        "eth_call":hex(token_decimals),
    }
    def rpc(method,params):
        seen.append((method,params))
        if fail:
            raise TimeoutError("private node not responding")
        return values[method]
    return rpc,seen

def checkout_body():
    return {
        "product_code":"competitor_search_gap",
        "business_name":"Example Ltd","email":"client@example.test",
        "target_domain":"example.test","payer_wallet":PAYER,
        "terms_accepted":True,"idempotency_key":"verified-checkout-test-11",
    }

def test_missing_bsc_config_is_redacted_and_held():
    data=checkout_bsc_config_snapshot(env={})
    assert data=={
        "configured":False,
        "status":"BSC_CONFIG_MISSING",
        "chain_verified":False,
        "payment_collection_ready":False,
    }
    assert "rpc_url" not in data and "treasury_address" not in data

@pytest.mark.parametrize("config", [
    {"BSC_RPC_URL":"http://127.0.0.1:8545","BSC_TREASURY_ADDRESS":"0x" + "0"*40},
    {"BSC_RPC_URL":"http://127.0.0.1:8545","BSC_TREASURY_ADDRESS":"notanaddress"},
    {"BSC_RPC_URL":"http://127.0.0.1:8545","BSC_TREASURY_ADDRESS":TREASURY,
     "BSC_USDT_TOKEN_CONTRACT":"0x"+"d"*40},
    {"BSC_RPC_URL":"http://127.0.0.1:8545","BSC_TREASURY_ADDRESS":TREASURY,
     "BSC_MIN_CONFIRMATIONS":"0"},
])
def test_invalid_bsc_config_never_admitted(config):
    state=checkout_bsc_config_snapshot(env=config)
    assert state["configured"] is False
    assert state["status"]=="BSC_CONFIG_INVALID"

def test_structural_config_does_not_claim_network_or_payment_approval():
    result=checkout_bsc_config_snapshot(env={
        "BSC_RPC_URL":CONFIG.rpc_url,
        "BSC_TREASURY_ADDRESS":TREASURY,
        "BSC_USDT_TOKEN_CONTRACT":BSC_USDT_CONTRACT,
    })
    assert result["configured"] is True
    assert result["chain_verified"] is False
    assert result["payment_collection_ready"] is False

def test_readonly_mainnet_token_anchor_requires_three_plus_calls():
    rpc,calls=mock_rpc()
    proof=verify_checkout_bsc_chain(config=CONFIG,rpc_call=rpc,now=NOW)
    assert proof["chain_verified"] is True
    assert proof["status"]=="FRESH_BSC_MAINNET_USDT_ANCHOR"
    assert proof["chain_id"]==56
    assert proof["token_decimals"]==18
    assert proof["block_number"]==320
    assert proof["orders_created"]==0
    assert proof["payment_requests_created"]==0
    assert proof["actual_revenue"] is False
    assert [name for name,params in calls]==[
        "eth_chainId","eth_blockNumber","eth_getBlockByNumber","eth_call"
    ]
    assert all(not name.startswith("eth_send") for name,params in calls)

@pytest.mark.parametrize("kwargs,expected", [
    ({"chain":"0x1"},"bsc_chain_read_unavailable"),
    ({"token_decimals":6},"bsc_token_decimals_unverified"),
    ({"block_timestamp":NOW-timedelta(hours=1)},"bsc_chain_head_stale"),
    ({"block_timestamp":NOW+timedelta(minutes=2)},"bsc_chain_head_stale"),
    ({"fail":True},"bsc_chain_read_unavailable"),
])
def test_network_mismatch_stale_wrong_token_and_timeouts_hold(kwargs,expected):
    rpc,calls=mock_rpc(**kwargs)
    with pytest.raises(CheckoutPaymentPreflightHold,match=expected):
        verify_checkout_bsc_chain(config=CONFIG,rpc_call=rpc,now=NOW)
    assert not any(method.startswith("eth_send") for method,params in calls)

def test_missing_env_before_payment_preflight(monkeypatch):
    monkeypatch.delenv("BSC_RPC_URL",raising=False)
    monkeypatch.delenv("BSC_TREASURY_ADDRESS",raising=False)
    with pytest.raises(CheckoutPaymentPreflightHold,match="bsc_payment_config_unavailable"):
        verify_checkout_bsc_chain()

def test_both_authority_flags_do_not_override_missing_bsc_configuration(monkeypatch):
    monkeypatch.setenv("EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED","ON")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED","ON")
    monkeypatch.delenv("BSC_RPC_URL",raising=False)
    monkeypatch.delenv("BSC_TREASURY_ADDRESS",raising=False)
    monkeypatch.setattr(checkout_api,"prepare_checkout_order",
                        lambda **kwargs:pytest.fail("ORDER_MUTATED_WITHOUT_BSC"))
    client=TestClient(checkout_api.app)
    health=client.get("/health")
    assert health.status_code==200
    assert health.json()["binding_order_creation_authorized"] is False
    assert health.json()["bsc_payment_configuration_status"]=="BSC_CONFIG_MISSING"
    order=client.post("/v1/orders",json=checkout_body())
    assert order.status_code==503
    assert order.json()["detail"]=="binding_orders_not_authorized"

def test_full_configured_flags_but_failed_rpc_hold_before_buyer_or_order(monkeypatch):
    monkeypatch.setenv("EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED","ON")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED","ON")
    monkeypatch.setattr(checkout_api,"_settlement_snapshot",
        lambda:{"configured":True,"mode":"direct","status":"BSC_CONFIGURED_CHAIN_UNVERIFIED"})
    monkeypatch.setattr(checkout_api,"verify_checkout_bsc_chain",
        lambda: (_ for _ in ()).throw(CheckoutPaymentPreflightHold("bsc_chain_head_stale")))
    monkeypatch.setattr(checkout_api,"prepare_checkout_order",
                        lambda **kwargs:pytest.fail("PARTIAL_ACCEPTED_ORDER_WRITTEN"))
    order=TestClient(checkout_api.app).post("/v1/orders",json=checkout_body())
    assert order.status_code==503
    assert order.json()["detail"]=="bsc_payment_preflight_unavailable"
    assert "stale" not in str(order.json())  # safe, stable public error

def test_verified_chain_preflight_runs_before_mock_order(monkeypatch):
    monkeypatch.setenv("EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED","ON")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED","ON")
    monkeypatch.setattr(checkout_api,"_settlement_snapshot",
                        lambda:{"configured":True,"mode":"direct","status":"BSC_CONFIGURED_CHAIN_UNVERIFIED"})
    seq=[]
    monkeypatch.setattr(checkout_api,"verify_checkout_bsc_chain",
                        lambda:seq.append("CHAIN_VERIFIED_BEFORE_DB"))
    monkeypatch.setattr(checkout_api,"prepare_checkout_order",
                        lambda **kwargs:(seq.append("CREATE_ORDER_AFTER_CHAIN"),{"order_id":"mock"})[1])
    monkeypatch.setattr(checkout_api,"create_payment_request_for_order",
                        lambda order,standing_authority,settlement_mode:(seq.append("PROPOSE_AFTER_ORDER"),{
                            "payment_request_created":False,"payment_request_status":"pending",
                            "actual_revenue":False,
                        })[1])
    result=TestClient(checkout_api.app).post("/v1/orders",json=checkout_body())
    assert result.status_code==200
    assert seq==["CHAIN_VERIFIED_BEFORE_DB","CREATE_ORDER_AFTER_CHAIN","PROPOSE_AFTER_ORDER"]

def test_payment_proposal_pending_status_does_not_expose_treasury_or_amount(monkeypatch):
    valid_order={
        "order_id":"33333333-3333-3333-3333-333333333333",
        "payer_wallet":PAYER,
        "product":{"amount_cents":19900},
        "actual_revenue":False,
    }
    anchor={"block_number":320}
    monkeypatch.setattr(checkout,"get_block_anchor",lambda cfg,rpc_call=None:anchor)
    monkeypatch.setattr(checkout,"submit_payment_proposal",lambda plan,operator_authorized,db:{
        "status":"pending","decision":"proposed",
        "request_id":"44444444-4444-4444-4444-444444444444","actual_revenue":False,
    })
    pending=checkout.create_payment_request_for_order(
        valid_order,standing_authority=True,
        config=CONFIG,now=NOW,
    )
    assert pending["payment_request_created"] is True
    assert pending["payment_request_status"]=="pending"
    assert pending["payment_instructions_ready"] is False
    assert pending["treasury_address"] is None
    assert pending["amount_usdt"] is None
    assert pending["actual_revenue"] is False

def test_only_dedicated_approved_payment_status_can_show_treasury(monkeypatch):
    valid_order={
        "order_id":"33333333-3333-3333-3333-333333333333",
        "payer_wallet":PAYER,"product":{"amount_cents":19900},"actual_revenue":False,
    }
    monkeypatch.setattr(checkout,"get_block_anchor",lambda cfg,rpc_call=None:{"block_number":320})
    monkeypatch.setattr(checkout,"submit_payment_proposal",lambda plan,operator_authorized,db:{
        "status":"approved","decision":"existing_request",
        "request_id":"44444444-4444-4444-4444-444444444444","actual_revenue":False,
    })
    result=checkout.create_payment_request_for_order(
        valid_order,standing_authority=True,config=CONFIG,now=NOW,
    )
    assert result["payment_request_status"]=="approved"
    assert result["payment_instructions_ready"] is True
    assert result["amount_usdt"]=="199"
    assert result["treasury_address"]==TREASURY
    assert result["actual_revenue"] is False

def test_unknown_payment_status_and_invalid_request_id_not_claimed(monkeypatch):
    order={"order_id":"33333333-3333-3333-3333-333333333333",
           "payer_wallet":PAYER,"product":{"amount_cents":19900}}
    monkeypatch.setattr(checkout,"get_block_anchor",lambda cfg,rpc_call=None:{"block_number":320})
    for status,id_ in [("cancelled",str(UUID(int=1))),("approved","garbage")]:
        monkeypatch.setattr(checkout,"submit_payment_proposal",lambda plan,operator_authorized,db:{
            "status":status,"request_id":id_,"actual_revenue":False,
        })
        with pytest.raises(checkout.CheckoutError):
            checkout.create_payment_request_for_order(order,standing_authority=True,config=CONFIG,now=NOW)



def test_one_shot_monitor_does_not_create_payments_or_repeat_founder_approval(monkeypatch):
    from scripts import inspect_self_serve_payment_activation as observer
    monkeypatch.setattr(observer,"load_runtime_env",lambda path:{})
    result=observer.inspection()
    assert result["status"]=="BSC_PAYMENT_ACTIVATION_HELD"
    assert result["reason"]=="BSC_CONFIG_MISSING"
    assert len(result["founder_approved_activation_scope"])==4
    assert result["buyer_records_written"]==0
    assert result["orders_created"]==0
    assert result["payment_requests_created"]==0
    assert result["actual_revenue"] is False
    assert result["funds_transferred"] is False
    assert result["allow_binding_orders"] is False
    assert "BSC_TREASURY_ADDRESS" not in str(result)


def test_one_shot_monitor_config_only_does_not_claim_role_or_chain(monkeypatch):
    from scripts import inspect_self_serve_payment_activation as observer
    monkeypatch.setattr(observer,"load_runtime_env",lambda path:{
        "BSC_RPC_URL":"http://127.0.0.1:8545",
        "BSC_TREASURY_ADDRESS":TREASURY,
    })
    result=observer.inspection()
    assert result["status"]=="BSC_PAYMENT_ACTIVATION_HELD"
    assert result["reason"]=="CHAIN_READ_NOT_YET_VERIFIED"
    assert result["bsc_configuration_present"] is True
    assert result["chain_verified"] is False
    assert result["dedicated_payment_approver_automatically_authorized"] is False
