"""Read-only BSC escrow mainnet holder, delay and backing gauntlet."""
from __future__ import annotations

from dataclasses import replace

import pytest

from empire_os.bsc_escrow_verifier import BscEscrowConfig
from empire_os.escrow_mainnet_role_readiness import (
    DECISION_DELAY_SELECTOR, ESCROW_BACKING_SELECTOR, HAS_ROLE_SELECTOR,
    KEYS, ROLES, EscrowRoleConfig, role_config_snapshot,
    verify_escrow_runtime_roles_and_backing,
)
from empire_os.self_serve_payment_readiness import CheckoutPaymentPreflightHold


CONTRACT = "0x" + "c"*40
ADMIN = "0x" + "1"*40
REQUESTER = "0x" + "2"*40
ARBITER = "0x" + "3"*40
PAUSER = "0x" + "4"*40
ROLE_VALUES = {"admin": ADMIN, "requester": REQUESTER,
               "arbiter": ARBITER, "pauser": PAUSER}
ROLES_CONFIG = EscrowRoleConfig(**ROLE_VALUES, decision_delay_seconds=7200)
DEPLOYMENT = BscEscrowConfig(
    rpc_url="http://127.0.0.1:8545", escrow_contract=CONTRACT,
    beneficiary="0x" + "a"*40,
    runtime_sha256="f"*64, min_confirmations=12,
)


def role_env():
    return {**{name:ROLE_VALUES[role] for role,name in KEYS.items()},
            "BSC_ESCROW_DECISION_DELAY_SECONDS":"7200"}


def word(value:int)->str:
    return "0x"+f"{value:064x}"


def fake_rpc(*, chain="0x38", missing_role=None, extra_role_result=None,
             seconds=7200,balance=1_000_000,liability=999_000,
             malformed=False,timeout=False):
    seen=[]
    expected={HAS_ROLE_SELECTOR+role_id[2:]+"0"*24+ROLE_VALUES[name][2:]:name
              for name,role_id in ROLES}
    def rpc(method,params):
        seen.append((method,params))
        if timeout:raise TimeoutError("PRIVATE_NODE_UNREACHABLE")
        if method=="eth_chainId":return chain
        assert method=="eth_call"
        item,at=params
        assert at=="latest"
        assert item["to"]==CONTRACT
        data=item["data"]
        if data in expected:
            name=expected[data]
            if malformed and name=="admin":return "0x1"
            if name==missing_role:return word(0)
            if extra_role_result is not None and name=="requester":
                return word(extra_role_result)
            return word(1)
        if data==DECISION_DELAY_SELECTOR:return word(seconds)
        if data==ESCROW_BACKING_SELECTOR:return word(balance)+word(liability)[2:]
        raise AssertionError(data)
    return rpc,seen


def test_role_snapshot_is_not_an_audit_or_authorisation():
    configured=role_config_snapshot(role_env())
    assert configured["configured"] is True
    assert configured["mainnet_role_evidence_verified"] is False
    assert "ADMIN" not in str(configured) and ADMIN not in str(configured)


@pytest.mark.parametrize(("key","replacement"),[
    ("BSC_ESCROW_ADMIN_ADDRESS", "0x"+"0"*40),
    ("BSC_ESCROW_REQUESTER_ADDRESS", ARBITER),
    ("BSC_ESCROW_ARBITER_ADDRESS", "not_an_address"),
    ("BSC_ESCROW_PAUSER_ADDRESS", ARBITER),
    ("BSC_ESCROW_DECISION_DELAY_SECONDS", "600"),
    ("BSC_ESCROW_DECISION_DELAY_SECONDS", "0"),
    ("BSC_ESCROW_DECISION_DELAY_SECONDS", "604801"),
    ("BSC_ESCROW_DECISION_DELAY_SECONDS", "invalid"),
])
def test_role_env_rejects_missing_duplicate_invalid_and_short_delay(key,replacement):
    config=role_env()
    config[key]=replacement
    assert role_config_snapshot(config)["configured"] is False
    with pytest.raises(CheckoutPaymentPreflightHold,match="escrow_roles_config_unverified"):
        EscrowRoleConfig.from_env(config)


def test_explicit_operator_addresses_are_not_inferred_from_wallet_or_contract():
    assert role_config_snapshot({})["configured"] is False
    assert not set(KEYS.values()).intersection({"BSC_TREASURY_ADDRESS","BSC_WALLET_ADDRESS"})


def test_verified_roles_and_backing_call_exact_readonly_contract_methods():
    rpc,seen=fake_rpc()
    proof=verify_escrow_runtime_roles_and_backing(
        deployment=DEPLOYMENT,roles=ROLES_CONFIG,rpc_call=rpc,
    )
    assert proof["status"]=="ESCROW_EXPECTED_ROLE_HOLDERS_AND_BACKING_VERIFIED_READ_ONLY"
    assert proof["expected_role_holders_verified"]==4
    assert proof["all_role_holders_exclusivity_verified"] is False
    assert proof["role_grant_history_independently_audited"] is False
    assert proof["decision_delay_seconds"]==7200
    assert proof["escrow_backing_solvency_pass"] is True
    assert proof["funds_moved"] is False
    assert proof["role_grants_created"]==0
    assert len(seen)==7
    assert [name for name,params in seen] == ["eth_chainId"] + ["eth_call"]*6
    assert all(not name.startswith("eth_send") for name,params in seen)


@pytest.mark.parametrize(("kwargs","reason"),[
    ({"chain":"0x1"},"escrow_role_wrong_network"),
    ({"missing_role":"admin"},"escrow_expected_role_holder_unverified"),
    ({"missing_role":"requester"},"escrow_expected_role_holder_unverified"),
    ({"missing_role":"arbiter"},"escrow_expected_role_holder_unverified"),
    ({"missing_role":"pauser"},"escrow_expected_role_holder_unverified"),
    ({"extra_role_result":2},"escrow_expected_role_holder_unverified"),
    ({"seconds":600},"escrow_onchain_decision_delay_mismatch"),
    ({"seconds":86400},"escrow_onchain_decision_delay_mismatch"),
    ({"liability":1_000_001},"escrow_liabilities_exceed_backing"),
    ({"malformed":True},"escrow_role_chain_read_invalid"),
    ({"timeout":True},"escrow_role_chain_read_unavailable"),
])
def test_mainnet_role_or_solvency_mismatch_never_admitted(kwargs,reason):
    rpc,calls=fake_rpc(**kwargs)
    with pytest.raises(CheckoutPaymentPreflightHold,match=reason):
        verify_escrow_runtime_roles_and_backing(
            deployment=DEPLOYMENT,roles=ROLES_CONFIG,rpc_call=rpc,
        )
    assert all(not method.startswith("eth_send") for method,params in calls)


def test_escrow_liability_equal_balance_is_valid_but_does_not_infer_revenue():
    rpc,seen=fake_rpc(balance=10_000,liability=10_000)
    proof=verify_escrow_runtime_roles_and_backing(
        deployment=DEPLOYMENT,roles=ROLES_CONFIG,rpc_call=rpc,
    )
    assert proof["balance_equals_liability"] is True
    assert proof["actual_revenue"] is False


def test_bad_mainnet_deployment_parameters_denied():
    with pytest.raises(CheckoutPaymentPreflightHold,match="escrow_role_chain_config_unverified"):
        verify_escrow_runtime_roles_and_backing(
            deployment=replace(DEPLOYMENT,min_confirmations=1),
            roles=ROLES_CONFIG, rpc_call=lambda *args:pytest.fail("NETWORK_READ_ON_UNTRUSTED_CONFIG"),
        )
