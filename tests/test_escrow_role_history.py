"""No-write complete AccessControl history replay for reviewed Empire escrow deploys."""
from __future__ import annotations

from dataclasses import replace
import copy
import pytest

from empire_os.bsc_escrow_verifier import BscEscrowConfig
from empire_os.escrow_mainnet_role_readiness import EscrowRoleConfig, ROLES
from empire_os.escrow_role_history import (
    EscrowDeploymentProvenance, ACCESS_CONTROL_TOPICS, ROLE_GRANTED,
    ROLE_REVOKED, ROLE_ADMIN_CHANGED, ADMIN_TRANSFER_SCHEDULED,
    LOG_CHUNK_BLOCKS, MAX_HISTORY_BLOCKS,
    verify_escrow_access_control_history,
)
from empire_os.self_serve_payment_readiness import CheckoutPaymentPreflightHold

CONTRACT="0x"+"c"*40
TX_HASH="0x"+"e"*64
ADMIN="0x"+"1"*40
REQUESTER="0x"+"2"*40
ARBITER="0x"+"3"*40
PAUSER="0x"+"4"*40
HOLDERS={"admin":ADMIN,"requester":REQUESTER,"arbiter":ARBITER,"pauser":PAUSER}
DEPLOYMENT=BscEscrowConfig(
    rpc_url="http://127.0.0.1:8545", escrow_contract=CONTRACT,
    beneficiary="0x"+"a"*40,runtime_sha256="f"*64,min_confirmations=12,
)
ROLE_CONFIG=EscrowRoleConfig(**HOLDERS,decision_delay_seconds=7200)
PROVENANCE=EscrowDeploymentProvenance(deployment_transaction_hash=TX_HASH,deployment_block=100)
HEAD=2120
CONFIRMED=HEAD-12+1


def block_hash(number):
    return "0x"+f"{number:064x}"

def address_topic(a):
    return "0x"+"0"*24+a[2:]

def create_log(name,role_id,number=100,index=0,account=None,event=ROLE_GRANTED):
    return {
        "address":CONTRACT,
        "removed":False,
        "blockNumber":hex(number),
        "transactionIndex":"0x0",
        "logIndex":hex(index),
        "transactionHash":TX_HASH if number==100 else "0x"+"1"*64,
        "blockHash":block_hash(number),
        "topics":[event,role_id,address_topic(account or HOLDERS[name]),address_topic(ADMIN)],
        "data":"0x",
    }

def initial_logs():
    return [create_log(name,role,index=i) for i,(name,role) in enumerate(ROLES)]


def mock_chain(*, appended=None, receipt_patch=None, mutation=None,
               tip=HEAD,chain="0x38",unstable=False,log_error=None):
    events=initial_logs()+list(appended or [])
    events.sort(key=lambda x:(int(x["blockNumber"],16),int(x["transactionIndex"],16),int(x["logIndex"],16)))
    receipt={
        "transactionHash":TX_HASH,
        "status":"0x1",
        "contractAddress":CONTRACT,
        "to":None,
        "blockNumber":"0x64",
        "blockHash":block_hash(100),
    }
    if receipt_patch:receipt.update(receipt_patch)
    calls=[]
    anchors=[0]
    def rpc(method, params):
        calls.append((method, copy.deepcopy(params)))
        if method=="eth_chainId":return chain
        if method=="eth_blockNumber":return hex(tip)
        if method=="eth_getBlockByNumber":
            number=int(params[0],16)
            if number==CONFIRMED:anchors[0]+=1
            return {
                "number":params[0],
                "hash":("0x"+"f"*64 if unstable and number==CONFIRMED and anchors[0]>1
                        else block_hash(number)),
                "timestamp":"0x665b9e00",
            }
        if method=="eth_getTransactionReceipt":
            assert params==[TX_HASH]
            return copy.deepcopy(receipt)
        if method=="eth_getLogs":
            assert len(params)==1
            query=params[0]
            assert query["address"]==CONTRACT
            assert query["topics"]==[ACCESS_CONTROL_TOPICS]
            start=int(query["fromBlock"],16)
            end=int(query["toBlock"],16)
            assert 0<=end-start<LOG_CHUNK_BLOCKS
            if log_error=="offline":
                raise TimeoutError("node unavailable")
            found=[copy.deepcopy(e) for e in events
                   if start<=int(e["blockNumber"],16)<=end]
            if mutation and start <= mutation[0] <= end:
                mutation[1](found)
            return found
        raise AssertionError(("Unexpected chain method",method))
    return rpc,calls


def test_full_confirmed_log_replay_proves_exact_four_roles_no_writes():
    rpc,calls=mock_chain()
    result=verify_escrow_access_control_history(
        deployment=DEPLOYMENT,roles=ROLE_CONFIG,
        provenance=PROVENANCE,rpc_call=rpc,
    )
    assert result["status"]=="ESCROW_CONFIRMED_ROLE_GRANT_HISTORY_EXCLUSIVE_AT_HEIGHT"
    assert result["confirmed_through_block"]==CONFIRMED
    assert result["confirmation_depth"]==12
    assert result["role_grants_replayed"]==4
    assert result["contiguous_blocks_scanned"]==CONFIRMED-100+1
    assert result["role_grant_exclusivity_verified_for_confirmed_window"] is True
    assert result["future_role_changes_covered"] is False
    assert result["independent_external_security_audit"] is False
    assert result["transactions_sent"]==0
    assert result["funds_moved"] is False
    assert result["actual_revenue"] is False
    queried=[(int(params[0]["fromBlock"],16),int(params[0]["toBlock"],16))
             for method,params in calls if method=="eth_getLogs"]
    assert queried==[(100,1099),(1100,2099),(2100,CONFIRMED)]
    assert queried[0][0]==100 and queried[-1][1]==CONFIRMED
    assert all(queried[i+1][0]==queried[i][1]+1 for i in range(len(queried)-1))
    assert all(not method.startswith("eth_send") and method!="eth_sendRawTransaction"
               for method,params in calls)


@pytest.mark.parametrize(("bad","reason"),[
    ({"BSC_ESCROW_DEPLOY_BLOCK":"0"},"escrow_deployment_provenance_missing"),
    ({"BSC_ESCROW_DEPLOY_BLOCK":"-5"},"escrow_deployment_provenance_missing"),
    ({"BSC_ESCROW_DEPLOY_BLOCK":"100","BSC_ESCROW_DEPLOY_TX_HASH":"garbage"},"escrow_deployment_provenance_missing"),
])
def test_provenance_never_infers_deployed_contract_from_historical_wallet(bad,reason):
    env={"BSC_ESCROW_DEPLOY_BLOCK":"100","BSC_ESCROW_DEPLOY_TX_HASH":TX_HASH}
    env.update(bad)
    with pytest.raises(CheckoutPaymentPreflightHold,match=reason):
        EscrowDeploymentProvenance.from_env(env)


def test_approved_deployment_receipt_binds_actual_contract_block_and_success():
    for modification in (
        {"status":"0x0"},
        {"transactionHash":"0x"+"9"*64},
        {"contractAddress":"0x"+"9"*40},
        {"to":"0x"+"4"*40},
        {"blockNumber":"0x65"},
        {"blockHash":"0x"+"0"*64},
    ):
        rpc,calls=mock_chain(receipt_patch=modification)
        with pytest.raises(CheckoutPaymentPreflightHold,match="(receipt_mismatch|receipt_noncanonical)"):
            verify_escrow_access_control_history(
                deployment=DEPLOYMENT,roles=ROLE_CONFIG,
                provenance=PROVENANCE,rpc_call=rpc,
            )
        assert not any(m=="eth_getLogs" for m,p in calls)


def test_unbounded_log_range_and_unconfirmed_deployment_fail_without_log_calls():
    for tip in (110,100+MAX_HISTORY_BLOCKS+12):
        rpc,calls=mock_chain(tip=tip)
        with pytest.raises(CheckoutPaymentPreflightHold,match="range_unbounded"):
            verify_escrow_access_control_history(
                deployment=DEPLOYMENT,roles=ROLE_CONFIG,
                provenance=PROVENANCE,rpc_call=rpc,
            )
        assert not any(method=="eth_getLogs" for method,params in calls)


def test_wrong_bsc_chain_holds_before_any_role_log_request():
    rpc,calls=mock_chain(chain="0x1")
    with pytest.raises(CheckoutPaymentPreflightHold,match="wrong_chain"):
        verify_escrow_access_control_history(
            deployment=DEPLOYMENT,roles=ROLE_CONFIG,
            provenance=PROVENANCE,rpc_call=rpc,
        )
    assert [m for m,p in calls]==["eth_chainId"]


@pytest.mark.parametrize(("event","reason"),[
    (ROLE_GRANTED,"escrow_role_history_extra_grant"),
    (ROLE_REVOKED,"escrow_role_history_unreviewed_change"),
    (ROLE_ADMIN_CHANGED,"escrow_role_history_unreviewed_change"),
    (ADMIN_TRANSFER_SCHEDULED,"escrow_role_history_unreviewed_change"),
])
def test_extra_grants_revocations_admin_changes_or_pending_transfer_hold(event,reason):
    entry=create_log("requester",ROLES[1][1],number=1150,index=0,account="0x"+"f"*40,event=event)
    if event==ROLE_ADMIN_CHANGED:
        entry["topics"]=[event,ROLES[1][1],ROLES[0][1],ROLES[0][1]]
    elif event==ADMIN_TRANSFER_SCHEDULED:
        entry["topics"]=[event,address_topic("0x"+"f"*40)]
        entry["data"]="0x"+"0"*64
    rpc,calls=mock_chain(appended=[entry])
    with pytest.raises(CheckoutPaymentPreflightHold,match=reason):
        verify_escrow_access_control_history(
            deployment=DEPLOYMENT,roles=ROLE_CONFIG,
            provenance=PROVENANCE,rpc_call=rpc,
        )


def test_malformed_removed_foreign_out_of_order_duplicate_and_out_of_bounds_events_fail_closed():
    samples=[
        (lambda logs:logs[0].__setitem__("removed",True),"malformed"),
        (lambda logs:logs[0].__setitem__("address","0x"+"9"*40),"malformed"),
        (lambda logs:logs[0]["topics"].__setitem__(2,"0x"+"1"*64),"malformed"),
        (lambda logs:logs[0].__setitem__("data","0x12"),"malformed"),
        (lambda logs:logs.append(copy.deepcopy(logs[0])),"order_or_duplicate"),
        (lambda logs:logs.reverse(),"order_or_duplicate"),
        (lambda logs:logs[0].__setitem__("blockNumber","0xfff"),"malformed"),
    ]
    for mutator,reason in samples:
        rpc,calls=mock_chain(mutation=(100,mutator))
        with pytest.raises(CheckoutPaymentPreflightHold,match=reason):
            verify_escrow_access_control_history(
                deployment=DEPLOYMENT,roles=ROLE_CONFIG,
                provenance=PROVENANCE,rpc_call=rpc,
            )


def test_rpc_unavailable_and_changed_canonical_anchor_fail_closed():
    rpc,calls=mock_chain(log_error="offline")
    with pytest.raises(CheckoutPaymentPreflightHold,match="rpc_unavailable"):
        verify_escrow_access_control_history(
            deployment=DEPLOYMENT,roles=ROLE_CONFIG,
            provenance=PROVENANCE,rpc_call=rpc,
        )
    rpc,calls=mock_chain(unstable=True)
    with pytest.raises(CheckoutPaymentPreflightHold,match="anchor_changed"):
        verify_escrow_access_control_history(
            deployment=DEPLOYMENT,roles=ROLE_CONFIG,
            provenance=PROVENANCE,rpc_call=rpc,
        )



def test_readonly_operator_inspector_defaults_to_no_network(monkeypatch):
    from scripts import inspect_escrow_role_history as inspector
    monkeypatch.setattr(inspector, "verify_escrow_checkout_contract",
                        lambda **kwargs: pytest.fail("UNEXPECTED_NETWORK_CALL"))
    monkeypatch.setattr(inspector, "verify_escrow_access_control_history",
                        lambda **kwargs: pytest.fail("UNEXPECTED_ROLE_SCAN"))
    out=inspector.inspection(env={})
    assert out["status"]=="ESCROW_ROLE_HISTORY_HELD"
    assert out["reason"]=="ESCROW_MAINNET_CONFIG_MISSING"
    assert out["deployment_provenance_configured"] is False
    assert out["onchain_transactions_sent"]==0
    assert out["database_mutations"]==0


def test_readonly_inspector_never_infers_approval_from_config_only(monkeypatch):
    from scripts import inspect_escrow_role_history as inspector
    env={
        "BSC_RPC_URL":DEPLOYMENT.rpc_url,
        "BSC_ESCROW_CONTRACT":CONTRACT,
        "BSC_ESCROW_BENEFICIARY":DEPLOYMENT.beneficiary,
        "BSC_ESCROW_RUNTIME_SHA256":DEPLOYMENT.runtime_sha256,
        "BSC_MIN_CONFIRMATIONS":"12",
        "BSC_ESCROW_ADMIN_ADDRESS":ADMIN,
        "BSC_ESCROW_REQUESTER_ADDRESS":REQUESTER,
        "BSC_ESCROW_ARBITER_ADDRESS":ARBITER,
        "BSC_ESCROW_PAUSER_ADDRESS":PAUSER,
        "BSC_ESCROW_DECISION_DELAY_SECONDS":"7200",
        "BSC_ESCROW_DEPLOY_TX_HASH":TX_HASH,
        "BSC_ESCROW_DEPLOY_BLOCK":"100",
    }
    monkeypatch.setattr(inspector, "verify_escrow_access_control_history",
                        lambda **kwargs:pytest.fail("NETWORK_PROBE_NOT_EXPLICITLY_APPROVED"))
    preliminary=inspector.inspection(env=env)
    assert preliminary["contract_configured"] is True
    assert preliminary["role_owner_addresses_configured"] is True
    assert preliminary["deployment_provenance_configured"] is True
    assert preliminary["status"]=="ESCROW_ROLE_HISTORY_HELD"
    assert preliminary["role_grant_exclusivity_at_confirmed_height_verified"] is False


def test_readonly_inspector_reports_independent_audit_and_payment_still_held(monkeypatch):
    from scripts import inspect_escrow_role_history as inspector
    env={
        "BSC_RPC_URL":DEPLOYMENT.rpc_url,
        "BSC_ESCROW_CONTRACT":CONTRACT,
        "BSC_ESCROW_BENEFICIARY":DEPLOYMENT.beneficiary,
        "BSC_ESCROW_RUNTIME_SHA256":DEPLOYMENT.runtime_sha256,
        "BSC_MIN_CONFIRMATIONS":"12",
        "BSC_ESCROW_ADMIN_ADDRESS":ADMIN,
        "BSC_ESCROW_REQUESTER_ADDRESS":REQUESTER,
        "BSC_ESCROW_ARBITER_ADDRESS":ARBITER,
        "BSC_ESCROW_PAUSER_ADDRESS":PAUSER,
        "BSC_ESCROW_DECISION_DELAY_SECONDS":"7200",
        "BSC_ESCROW_DEPLOY_TX_HASH":TX_HASH,
        "BSC_ESCROW_DEPLOY_BLOCK":"100",
    }
    calls=[]
    monkeypatch.setattr(inspector, "verify_escrow_checkout_contract",
                        lambda config:(
                            calls.append("VERIFIED_CONTRACT_CODE_TOKEN_BENEFICIARY"),
                            {"escrow_runtime_verified":True},
                        )[1])
    monkeypatch.setattr(inspector, "verify_escrow_runtime_roles_and_backing",
                        lambda deployment,roles:(
                            calls.append("VERIFIED_FOUR_ROLE_HOLDERS_AND_BACKING"),
                            {"expected_role_holders_verified":4,"escrow_backing_solvency_pass":True},
                        )[1])
    monkeypatch.setattr(inspector, "verify_escrow_access_control_history",
                        lambda deployment,roles,provenance:(
                            calls.append("REPLAYED_ALL_CONFIRMED_ROLE_EVENTS"),
                            {
                                "role_grant_exclusivity_verified_for_confirmed_window":True,
                                "contiguous_blocks_scanned":2010,
                                "role_grants_replayed":4,
                                "confirmed_through_block":2109,
                            },
                        )[1])
    result=inspector.inspection(verify_history=True,env=env)
    assert calls==[
        "VERIFIED_CONTRACT_CODE_TOKEN_BENEFICIARY",
        "VERIFIED_FOUR_ROLE_HOLDERS_AND_BACKING",
        "REPLAYED_ALL_CONFIRMED_ROLE_EVENTS",
    ]
    assert result["status"]=="ESCROW_ROLE_HISTORY_ONCHAIN_READ_PROOF_COMPLETE"
    assert result["role_history_blocks_scanned"]==2010
    assert result["role_grant_exclusivity_at_confirmed_height_verified"] is True
    assert result["role_grant_exclusivity_independently_audited"] is False
    assert result["external_smart_contract_security_audit_verified"] is False
    assert result["payment_activation_performed"] is False
    assert result["onchain_transactions_sent"]==0
    assert result["execution_authority"]=="none"



def test_incomplete_constructor_events_never_pass_as_clean_history():
    def omit_pauser(logs):
        logs.pop()
    rpc,calls=mock_chain(mutation=(100,omit_pauser))
    with pytest.raises(CheckoutPaymentPreflightHold,match="role_history_incomplete"):
        verify_escrow_access_control_history(
            deployment=DEPLOYMENT,roles=ROLE_CONFIG,
            provenance=PROVENANCE,rpc_call=rpc,
        )


def test_constructor_grant_must_originate_from_deployment_transaction():
    def forged_grant(logs):
        logs[1]["transactionHash"]="0x"+"2"*64
    rpc,calls=mock_chain(mutation=(100,forged_grant))
    with pytest.raises(CheckoutPaymentPreflightHold,match="not_constructor_grant"):
        verify_escrow_access_control_history(
            deployment=DEPLOYMENT,roles=ROLE_CONFIG,
            provenance=PROVENANCE,rpc_call=rpc,
        )


def test_unexpected_role_id_on_constructor_is_not_clean_policy():
    def rogue_role(logs):
        logs[2]["topics"][1]="0x"+"f"*64
    rpc,calls=mock_chain(mutation=(100,rogue_role))
    with pytest.raises(CheckoutPaymentPreflightHold,match="extra_grant"):
        verify_escrow_access_control_history(
            deployment=DEPLOYMENT,roles=ROLE_CONFIG,
            provenance=PROVENANCE,rpc_call=rpc,
        )


def test_admin_delay_schedule_and_cancel_historical_events_both_hold():
    from empire_os.escrow_role_history import (
        ADMIN_DELAY_CHANGE_SCHEDULED, ADMIN_DELAY_CHANGE_CANCELLED,
    )
    first=create_log("admin",ROLES[0][1],number=1150,index=0)
    first["topics"]=[ADMIN_DELAY_CHANGE_SCHEDULED]
    first["data"]="0x"+"0"*63+"1"+"0"*63+"2"
    second=create_log("admin",ROLES[0][1],number=1151,index=0)
    second["topics"]=[ADMIN_DELAY_CHANGE_CANCELLED]
    second["data"]="0x"
    for event in (first,second):
        rpc,calls=mock_chain(appended=[event])
        with pytest.raises(CheckoutPaymentPreflightHold,match="unreviewed_change"):
            verify_escrow_access_control_history(
                deployment=DEPLOYMENT,roles=ROLE_CONFIG,
                provenance=PROVENANCE,rpc_call=rpc,
            )


def test_replayed_log_count_must_be_bounded():
    from empire_os.escrow_role_history import MAX_LOGS_PER_CHUNK
    def flood(logs):
        logs.extend([copy.deepcopy(logs[0])] * (MAX_LOGS_PER_CHUNK+1))
    rpc,calls=mock_chain(mutation=(100,flood))
    with pytest.raises(CheckoutPaymentPreflightHold,match="log_coverage_unverified"):
        verify_escrow_access_control_history(
            deployment=DEPLOYMENT,roles=ROLE_CONFIG,
            provenance=PROVENANCE,rpc_call=rpc,
        )


def test_even_complete_history_is_not_independent_audit_or_payment_activation():
    rpc,calls=mock_chain()
    report=verify_escrow_access_control_history(
        deployment=DEPLOYMENT,roles=ROLE_CONFIG,
        provenance=PROVENANCE,rpc_call=rpc,
    )
    assert report["independent_external_security_audit"] is False
    assert report["future_role_changes_covered"] is False
    assert report["permissions_changed"] is False
    assert report["funds_moved"] is False
    assert report["transactions_sent"]==0
