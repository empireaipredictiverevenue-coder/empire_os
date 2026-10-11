"""Prove checkout -> existing EmpireBscUsdtEscrow is fail-closed and not payable early."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import empire_os.self_serve_checkout as checkout
import empire_os.self_serve_checkout_api as api
from empire_os.bsc_escrow_verifier import BscEscrowConfig
from empire_os.bsc_usdt_verifier import BSC_USDT_CONTRACT, DECIMALS_SELECTOR
from empire_os.self_serve_escrow_bridge import (
    BENEFICIARY_SELECTOR, PAUSED_SELECTOR, TOKEN_SELECTOR,
    escrow_config_snapshot, escrow_mainnet_activation_flag,
    settlement_mode, verify_escrow_checkout_contract,
)
from empire_os.self_serve_payment_readiness import CheckoutPaymentPreflightHold

NOW = datetime(2026, 10, 12, 0, 5, tzinfo=timezone.utc)
CONTRACT = "0x" + "c" * 40
BENEFICIARY = "0x" + "a" * 40
PAYER = "0x" + "b" * 40
CODE = bytes.fromhex("600160005560006000fd")
CODE_HASH = sha256(CODE).hexdigest()
BLOCK_HASH = "0x" + "d" * 64
CFG = BscEscrowConfig(
    rpc_url="http://127.0.0.1:8545",
    escrow_contract=CONTRACT, beneficiary=BENEFICIARY,
    runtime_sha256=CODE_HASH, min_confirmations=12,
)


def config_env():
    return {
        "BSC_RPC_URL": CFG.rpc_url,
        "BSC_ESCROW_CONTRACT": CONTRACT,
        "BSC_ESCROW_BENEFICIARY": BENEFICIARY,
        "BSC_ESCROW_RUNTIME_SHA256": CODE_HASH,
        "BSC_USDT_TOKEN_CONTRACT": BSC_USDT_CONTRACT,
        "BSC_MIN_CONFIRMATIONS": "12",
    }


def abi_address(address):
    return "0x" + "0"*24 + address[2:].lower()


def read_rpc(*, chain="0x38", decimals=18, code=None,
             beneficiary=BENEFICIARY, token=BSC_USDT_CONTRACT, paused=0,
             block_time=NOW, bad_address_padding=False, fail=False):
    seen = []
    def rpc(method, params):
        seen.append((method, params))
        if fail:
            raise TimeoutError("simulated unavailable RPC")
        if method == "eth_chainId": return chain
        if method == "eth_blockNumber": return "0x1a0"
        if method == "eth_getBlockByNumber":
            return {
                "number":"0x1a0", "hash":BLOCK_HASH,
                "timestamp":hex(int(block_time.timestamp())),
            }
        if method == "eth_getCode":
            assert params == [CONTRACT, "latest"]
            return "0x" + (CODE.hex() if code is None else code)
        if method == "eth_call":
            call,at=params
            assert at == "latest"
            selector=call["data"]
            if selector == DECIMALS_SELECTOR:
                assert call["to"]==BSC_USDT_CONTRACT
                return hex(decimals)
            assert call["to"]==CONTRACT
            if selector == BENEFICIARY_SELECTOR:
                value=abi_address(beneficiary)
                return "0x" + "f"*24 + value[26:] if bad_address_padding else value
            if selector == TOKEN_SELECTOR: return abi_address(token)
            if selector == PAUSED_SELECTOR: return hex(paused)
        raise AssertionError((method,params))
    return rpc,seen


def checkout_body():
    return {
        "product_code":"competitor_search_gap",
        "business_name":"Test Company",
        "email":"test@example.invalid",
        "target_domain":"example.invalid",
        "payer_wallet":PAYER,
        "terms_accepted":True,
        "idempotency_key":"escrow-test-key-20261012",
    }


def test_runtime_defaults_to_existing_direct_mode_but_cannot_auto_choose_unknown():
    assert settlement_mode({})=="direct"
    assert settlement_mode({"EMPIRE_SELF_SERVE_SETTLEMENT_MODE":"escrow"})=="escrow"
    with pytest.raises(CheckoutPaymentPreflightHold,match="unsupported"):
        settlement_mode({"EMPIRE_SELF_SERVE_SETTLEMENT_MODE":"automatic"})


def test_escrow_mainnet_deployment_approval_is_independent_and_default_off():
    assert escrow_mainnet_activation_flag({}) is False
    assert escrow_mainnet_activation_flag({"EMPIRE_SELF_SERVE_ESCROW_MAINNET_APPROVED":"OFF"}) is False
    assert escrow_mainnet_activation_flag({"EMPIRE_SELF_SERVE_ESCROW_MAINNET_APPROVED":"ON"}) is True


def test_empty_escrow_config_never_claims_production_contract():
    state=escrow_config_snapshot(environ={})
    assert state["configured"] is False
    assert state["status"]=="ESCROW_MAINNET_CONFIG_MISSING"
    assert "contract" not in state and "beneficiary" not in state


@pytest.mark.parametrize(("field","value"), [
    ("BSC_ESCROW_CONTRACT","0x"+"0"*40),
    ("BSC_ESCROW_BENEFICIARY","0x"+"0"*40),
    ("BSC_ESCROW_BENEFICIARY",CONTRACT),
    ("BSC_ESCROW_CONTRACT","untrusted"),
    ("BSC_ESCROW_RUNTIME_SHA256","deadbeef"),
    ("BSC_ESCROW_RUNTIME_SHA256","z"*64),
    ("BSC_MIN_CONFIRMATIONS","11"),
    ("BSC_MIN_CONFIRMATIONS","0"),
    ("BSC_MIN_CONFIRMATIONS","invalid"),
    ("BSC_USDT_TOKEN_CONTRACT","0x"+"e"*40),
])
def test_invalid_escrow_configuration_held(field,value):
    e=config_env()
    e[field]=value
    state=escrow_config_snapshot(environ=e)
    assert state["configured"] is False
    assert state["status"]=="ESCROW_MAINNET_CONFIG_INVALID"


def test_structural_escrow_config_not_evidence_of_mainnet_deployment():
    state=escrow_config_snapshot(environ=config_env())
    assert state["configured"] is True
    assert state["mainnet_activation_verified"] is False


def test_readonly_escrow_proof_reads_chain_code_beneficiary_token_and_pause():
    rpc,seen=read_rpc()
    evidence=verify_escrow_checkout_contract(config=CFG,rpc_call=rpc,now=NOW)
    assert evidence["status"]=="ESCROW_MAINNET_RUNTIME_VERIFIED_READ_ONLY"
    assert evidence["escrow_runtime_verified"] is True
    assert evidence["chain_id"]==56
    assert evidence["token_decimals"]==18
    assert evidence["escrow_created"] is False
    assert evidence["payment_instructions_ready"] is False
    assert evidence["buyer_order_created"] is False
    assert evidence["actual_revenue"] is False
    assert [name for name,_ in seen]==[
        "eth_chainId","eth_blockNumber","eth_getBlockByNumber",
        "eth_call","eth_getCode","eth_call","eth_call","eth_call",
    ]
    assert all(not method.startswith("eth_send") for method,_ in seen)


@pytest.mark.parametrize(("kwargs","hold"), [
    ({"chain":"0x1"},"escrow_mainnet_read_unavailable"),
    ({"decimals":6},"escrow_usdt_token_mismatch"),
    ({"code":"60016000"},"escrow_runtime_code_mismatch"),
    ({"code":""},"escrow_mainnet_read_unavailable"),
    ({"beneficiary":"0x"+"1"*40},"escrow_beneficiary_mismatch"),
    ({"token":"0x"+"2"*40},"escrow_usdt_token_mismatch"),
    ({"paused":1},"escrow_contract_paused"),
    ({"bad_address_padding":True},"escrow_mainnet_read_unavailable"),
    ({"block_time":NOW-timedelta(hours=2)},"escrow_block_stale"),
    ({"block_time":NOW+timedelta(seconds=75)},"escrow_block_stale"),
    ({"fail":True},"escrow_mainnet_read_unavailable"),
])
def test_escrow_mainnet_evidence_fail_closed(kwargs,hold):
    rpc,seen=read_rpc(**kwargs)
    with pytest.raises(CheckoutPaymentPreflightHold,match=hold):
        verify_escrow_checkout_contract(config=CFG,rpc_call=rpc,now=NOW)
    assert all(not method.startswith("eth_send") for method,_ in seen)


def test_escrow_enabling_orders_needs_three_flags_plus_config(monkeypatch):
    monkeypatch.setenv("EMPIRE_SELF_SERVE_SETTLEMENT_MODE","escrow")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED","ON")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED","ON")
    for k in config_env():monkeypatch.delenv(k,raising=False)
    assert api._orders_authorized() is False
    for k,v in config_env().items():monkeypatch.setenv(k,v)
    assert api._orders_authorized() is False
    status=TestClient(api.app).get("/health").json()
    assert status["checkout_settlement_mode"]=="escrow"
    assert status["bsc_payment_configuration_status"]=="ESCROW_MAINNET_ACTIVATION_HELD"
    monkeypatch.setenv("EMPIRE_SELF_SERVE_ESCROW_MAINNET_APPROVED","ON")
    assert api._orders_authorized() is True
    # Only structurally eligible; chain bytecode is still read before DB.


def test_escrow_missing_approval_prevents_any_buyer_order_write(monkeypatch):
    monkeypatch.setenv("EMPIRE_SELF_SERVE_SETTLEMENT_MODE","escrow")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED","ON")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED","ON")
    monkeypatch.delenv("EMPIRE_SELF_SERVE_ESCROW_MAINNET_APPROVED",raising=False)
    for k,v in config_env().items():monkeypatch.setenv(k,v)
    monkeypatch.setattr(api,"prepare_checkout_order",lambda **kw:pytest.fail("BUYER_WRITTEN"))
    result=TestClient(api.app).post("/v1/orders",json=checkout_body())
    assert result.status_code==503
    assert result.json()["detail"]=="binding_orders_not_authorized"


def test_escrow_invalid_chain_or_bytecode_proof_prevents_buyer_mutation(monkeypatch):
    monkeypatch.setenv("EMPIRE_SELF_SERVE_SETTLEMENT_MODE","escrow")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED","ON")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED","ON")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_ESCROW_MAINNET_APPROVED","ON")
    for k,v in config_env().items():monkeypatch.setenv(k,v)
    monkeypatch.setattr(api,"verify_escrow_checkout_contract",lambda:(
        _ for _ in ()).throw(CheckoutPaymentPreflightHold("escrow_runtime_code_mismatch")))
    monkeypatch.setattr(api,"prepare_checkout_order",lambda **kw:pytest.fail("ORDER_WRITE_AFTER_CODE_MISMATCH"))
    denied=TestClient(api.app).post("/v1/orders",json=checkout_body())
    assert denied.status_code==503
    assert denied.json()["detail"]=="bsc_payment_preflight_unavailable"
    assert "mismatch" not in str(denied.json())


def test_escrow_api_dispatch_verifies_chain_before_creating_any_order(monkeypatch):
    monkeypatch.setenv("EMPIRE_SELF_SERVE_SETTLEMENT_MODE","escrow")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED","ON")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED","ON")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_ESCROW_MAINNET_APPROVED","ON")
    for k,v in config_env().items():monkeypatch.setenv(k,v)
    seen=[]
    monkeypatch.setattr(api,"verify_escrow_checkout_contract",
                        lambda:seen.append("ESCROW_CHAIN_CODE_AND_IDENTITIES_PASS"))
    monkeypatch.setattr(api,"verify_escrow_operator_memberships",
        lambda:seen.append("INDEPENDENT_OPERATOR_ROLES_PRESENT"))
    monkeypatch.setattr(api,"prepare_checkout_order",lambda **kw:(
        seen.append("PREPARE_ORDER_WITH_"+kw["settlement_mode"]),
        {"order_id":"test-only","settlement_mode":"escrow"})[1])
    monkeypatch.setattr(api,"create_payment_request_for_order",lambda order,standing_authority,settlement_mode:(
        seen.append("PROPOSE_EXISTING_ESCROW_RPC_"+settlement_mode),
        {"payment_request_created":False,"actual_revenue":False,"settlement_mode":settlement_mode})[1])
    response=TestClient(api.app).post("/v1/orders",json=checkout_body())
    assert response.status_code==200
    assert response.json()["actual_revenue"] is False
    assert seen==[
        "ESCROW_CHAIN_CODE_AND_IDENTITIES_PASS",
        "INDEPENDENT_OPERATOR_ROLES_PRESENT",
        "PREPARE_ORDER_WITH_escrow",
        "PROPOSE_EXISTING_ESCROW_RPC_escrow",
    ]


def test_escrow_proposal_reuses_canonical_rpc_and_never_gives_payable_address(monkeypatch):
    calls=[]
    monkeypatch.setattr(checkout,"get_block_anchor",lambda cfg,rpc_call=None:{
        "block_number":320
    })
    def existing_governance(plan,*,operator_authorized,db):
        assert operator_authorized is True
        calls.append(plan)
        return {
            "decision":"proposed",
            "request_id":"22222222-2222-2222-2222-222222222222",
            "status":"pending",
            "settlement_mode":"escrow",
            "actual_revenue":False,
        }
    monkeypatch.setattr(checkout,"submit_payment_proposal",existing_governance)
    order={
        "order_id":"11111111-1111-1111-1111-111111111111",
        "payer_wallet":PAYER,
        "settlement_mode":"escrow",
        "product":{"amount_cents":19900},
        "actual_revenue":False,
    }
    response=checkout.create_payment_request_for_order(
        order,standing_authority=True,config=CFG,now=NOW,settlement_mode="escrow",
    )
    assert len(calls)==1
    proposal=calls[0]
    assert proposal["rpc"]=="propose_bsc_escrow_request"
    assert proposal["settlement_mode"]=="escrow"
    assert proposal["write_authorized"] is False
    assert proposal["params"]["p_beneficiary_address"]==BENEFICIARY
    assert proposal["params"]["p_amount_usdt"]=="199"
    assert proposal["params"]["p_payer_address"]==PAYER
    assert proposal["params"]["p_min_block_number"]==320
    assert proposal["params"]["p_idempotency_key"].startswith("checkout-escrow:")
    assert response["payment_request_created"] is True
    assert response["payment_request_status"]=="pending"
    assert response["settlement_mode"]=="escrow"
    assert response["payment_instructions_ready"] is False
    assert response["escrow_creation_verified"] is False
    assert response["treasury_address"] is None
    assert response["amount_usdt"] is None
    assert response["actual_revenue"] is False


def test_approved_escrow_request_still_has_no_funding_instructions(monkeypatch):
    monkeypatch.setattr(checkout,"get_block_anchor",lambda cfg,rpc_call=None:{"block_number":320})
    monkeypatch.setattr(checkout,"submit_payment_proposal",lambda plan,operator_authorized,db:{
        "decision":"existing_request",
        "request_id":"22222222-2222-2222-2222-222222222222",
        "status":"approved",
        "settlement_mode":"escrow",
        "actual_revenue":False,
    })
    response=checkout.create_payment_request_for_order(
        {"order_id":"11111111-1111-1111-1111-111111111111",
         "payer_wallet":PAYER,"settlement_mode":"escrow",
         "product":{"amount_cents":29900}},
        standing_authority=True,config=CFG,now=NOW,settlement_mode="escrow",
    )
    assert response["payment_request_status"]=="approved"
    assert response["next_payment_step"]=="INDEPENDENT_ESCROW_CREATION_PROOF_REQUIRED"
    assert response["payment_instructions_ready"] is False
    assert response["treasury_address"] is None
    assert response["amount_usdt"] is None


def test_escrow_rpc_must_return_escrow_mode_not_direct(monkeypatch):
    monkeypatch.setattr(checkout,"get_block_anchor",lambda cfg,rpc_call=None:{"block_number":320})
    monkeypatch.setattr(checkout,"submit_payment_proposal",lambda plan,operator_authorized,db:{
        "decision":"existing_request",
        "request_id":"22222222-2222-2222-2222-222222222222",
        "status":"approved",
        "settlement_mode":"direct",
        "actual_revenue":False,
    })
    with pytest.raises(checkout.CheckoutError,match="settlement mode not confirmed"):
        checkout.create_payment_request_for_order(
            {"order_id":"11111111-1111-1111-1111-111111111111",
             "payer_wallet":PAYER,"settlement_mode":"escrow",
             "product":{"amount_cents":19900}},
            standing_authority=True,config=CFG,now=NOW,settlement_mode="escrow",
        )


def test_order_mode_mismatch_fails_before_payment_rpc(monkeypatch):
    monkeypatch.setattr(checkout,"submit_payment_proposal",lambda *a,**kw:pytest.fail("UNTRUSTED_ESCROW_PROPOSED"))
    with pytest.raises(checkout.CheckoutError,match="order settlement mode mismatch"):
        checkout.create_payment_request_for_order(
            {"order_id":"11111111-1111-1111-1111-111111111111",
             "settlement_mode":"direct","payer_wallet":PAYER,"product":{"amount_cents":19900}},
            standing_authority=True,config=CFG,now=NOW,settlement_mode="escrow",
        )



def test_readonly_activation_monitor_uses_existing_escrow_mode_and_holds_without_mainnet_gate(monkeypatch):
    from scripts import inspect_self_serve_payment_activation as observer
    env = config_env()
    env["EMPIRE_SELF_SERVE_SETTLEMENT_MODE"] = "escrow"
    monkeypatch.setattr(observer,"load_runtime_env",lambda path:env)
    monkeypatch.setattr(observer,"verify_escrow_checkout_contract",
        lambda:pytest.fail("MAINNET_ESCROW_VERIFIER_CALLED_WITHOUT_APPROVAL"))
    result = observer.inspection(probe_chain=True)
    assert result["schema_version"].endswith(".v2")
    assert result["checkout_settlement_mode"]=="escrow"
    assert result["status"]=="BSC_PAYMENT_ACTIVATION_HELD"
    assert result["reason"]=="ESCROW_MAINNET_ACTIVATION_HELD"
    assert result["escrow_contract_runtime_verified"] is False
    assert result["dedicated_escrow_verifier_automatically_authorized"] is False
    assert result["enable_payment_flags"] is False
    assert result["orders_created"]==0
    assert result["funds_transferred"] is False


def test_readonly_monitor_recognizes_mock_verified_escrow_but_never_authorizes_payment(monkeypatch):
    from scripts import inspect_self_serve_payment_activation as observer
    env=config_env()
    env["EMPIRE_SELF_SERVE_SETTLEMENT_MODE"]="escrow"
    env["EMPIRE_SELF_SERVE_ESCROW_MAINNET_APPROVED"]="ON"
    monkeypatch.setattr(observer,"load_runtime_env",lambda path:env)
    seen=[]
    monkeypatch.setattr(observer,"verify_escrow_operator_memberships",lambda:(
        seen.append("OPERATOR_ROLE_READONLY_PROOF"),{
            "status":"ESCROW_OPERATOR_MEMBERSHIPS_PRESENT_READ_ONLY",
        })[1])
    monkeypatch.setattr(observer,"verify_escrow_checkout_contract",lambda:(
        seen.append("READ_ONLY_CHAIN_PROOF"),{
            "status":"ESCROW_MAINNET_RUNTIME_VERIFIED_READ_ONLY",
            "escrow_runtime_verified":True,
            "block_age_seconds":0.2,
        })[1])
    result=observer.inspection(probe_chain=True)
    assert seen==["READ_ONLY_CHAIN_PROOF","OPERATOR_ROLE_READONLY_PROOF"]
    assert result["status"]=="BSC_PREFLIGHT_PASS"
    assert result["escrow_operator_memberships_verified"] is True
    assert result["escrow_contract_runtime_verified"] is True
    assert result["checkout_settlement_mode"]=="escrow"
    assert result["enable_payment_flags"] is False
    assert result["allow_binding_orders"] is False
    assert result["dedicated_payment_approver_automatically_authorized"] is False
    assert result["buyer_records_written"]==0
    assert result["payment_requests_created"]==0


def test_invalid_mode_holds_observer_without_any_network_reads(monkeypatch):
    from scripts import inspect_self_serve_payment_activation as observer
    monkeypatch.setattr(observer,"load_runtime_env",
        lambda path:{"EMPIRE_SELF_SERVE_SETTLEMENT_MODE":"unknown"})
    monkeypatch.setattr(observer,"verify_checkout_bsc_chain",lambda:pytest.fail("RPC_CALLED"))
    monkeypatch.setattr(observer,"verify_escrow_checkout_contract",lambda:pytest.fail("ESCROW_RPC_CALLED"))
    result=observer.inspection(probe_chain=True)
    assert result["status"]=="BSC_PAYMENT_ACTIVATION_HELD"
    assert result["reason"]=="UNSUPPORTED_CHECKOUT_SETTLEMENT_MODE"
    assert result["authority"]=="none"



def test_escrow_operator_readonly_roles_require_separate_provisioned_login_memberships():
    from empire_os.self_serve_escrow_bridge import verify_escrow_operator_memberships
    valid=[
        ("empire_escrow_verifier",False,False,1),
        ("empire_payment_approver",False,False,1),
    ]
    result=verify_escrow_operator_memberships(reader=lambda:list(valid))
    assert result["status"]=="ESCROW_OPERATOR_MEMBERSHIPS_PRESENT_READ_ONLY"
    assert result["dedicated_credentials_exposed"] is False
    assert result["payment_approval_performed"] is False
    assert result["orders_created"]==0
    for rows in (
        [],
        [("empire_escrow_verifier",False,False,0),valid[1]],
        [valid[0],("empire_payment_approver",False,False,0)],
        [valid[0],("empire_payment_approver",True,False,1)],
        [valid[0],("empire_payment_approver",False,True,1)],
        list(reversed(valid)),
        [valid[0]],
    ):
        with pytest.raises(CheckoutPaymentPreflightHold,match="operator_roles_unprovisioned"):
            verify_escrow_operator_memberships(reader=lambda r=rows:r)


def test_escrow_operator_role_catalog_unavailable_fails_closed():
    from empire_os.self_serve_escrow_bridge import verify_escrow_operator_memberships
    def offline():
        raise RuntimeError("DB disconnected with secrets")
    with pytest.raises(CheckoutPaymentPreflightHold,match="role_catalog_unavailable") as info:
        verify_escrow_operator_memberships(reader=offline)
    assert "secrets" not in str(info.value)


def test_unprovisioned_escrow_operator_roles_block_checkout_before_any_order_write(monkeypatch):
    monkeypatch.setenv("EMPIRE_SELF_SERVE_SETTLEMENT_MODE","escrow")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED","ON")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED","ON")
    monkeypatch.setenv("EMPIRE_SELF_SERVE_ESCROW_MAINNET_APPROVED","ON")
    for k,v in config_env().items():monkeypatch.setenv(k,v)
    calls=[]
    monkeypatch.setattr(api,"verify_escrow_checkout_contract",lambda:calls.append("CONTRACT_VERIFIED"))
    monkeypatch.setattr(api,"verify_escrow_operator_memberships",lambda:(
        _ for _ in ()).throw(CheckoutPaymentPreflightHold("escrow_operator_roles_unprovisioned")))
    monkeypatch.setattr(api,"prepare_checkout_order",lambda **kw:pytest.fail("ESCROW_ACCEPTED_ORDER_WITHOUT_OPERATOR"))
    result=TestClient(api.app).post("/v1/orders",json=checkout_body())
    assert result.status_code==503
    assert result.json()["detail"]=="bsc_payment_preflight_unavailable"
    assert calls==["CONTRACT_VERIFIED"]
