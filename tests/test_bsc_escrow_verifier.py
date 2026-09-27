import hashlib

import pytest

from empire_os.bsc_escrow_verifier import (
    ACTION_TOPICS, BscEscrowConfig, escrow_id_from_uuid, verify_escrow_action,
    verify_escrow_created, creation_record_payload, lifecycle_record_payload,
)
from empire_os.bsc_usdt_verifier import (
    BSC_USDT_CONTRACT, PaymentVerificationError, TRANSFER_TOPIC,
)

ESCROW = "0x1111111111111111111111111111111111111111"
BENEFICIARY = "0x2222222222222222222222222222222222222222"
PAYER = "0x3333333333333333333333333333333333333333"
CALLER = "0x4444444444444444444444444444444444444444"
TX = "0x" + "55" * 32
BLOCK_HASH = "0x" + "66" * 32
RUNTIME = "0x6001600055"
RUNTIME_SHA = hashlib.sha256(bytes.fromhex(RUNTIME[2:])).hexdigest()
REQUEST_UUID = "11111111-2222-3333-4444-555555555555"
ESCROW_ID = escrow_id_from_uuid(REQUEST_UUID)
AMOUNT = 125 * 10**18
TERMS_HASH = "0x" + "77" * 32


def address_topic(address):
    return "0x" + "0" * 24 + address[2:].lower()


def uint_data(value):
    return "0x" + format(value, "064x")

def config(runtime_sha=RUNTIME_SHA):
    return BscEscrowConfig(
        rpc_url="https://example.invalid",
        escrow_contract=ESCROW,
        beneficiary=BENEFICIARY,
        runtime_sha256=runtime_sha,
        min_confirmations=12,
    )


def mock_rpc(action="funded", amount=AMOUNT, include_event=True, include_transfer=True,
             runtime=RUNTIME, latest=120, block=100):
    party = PAYER if action in {"funded", "refunded"} else BENEFICIARY
    transfer_from = PAYER if action == "funded" else ESCROW
    transfer_to = ESCROW if action == "funded" else party
    logs = []
    if include_event:
        logs.append({
            "address": ESCROW,
            "topics": [ACTION_TOPICS[action], ESCROW_ID, address_topic(party)],
            "data": uint_data(amount), "removed": False,
            "transactionHash": TX, "blockHash": BLOCK_HASH,
            "blockNumber": hex(block), "logIndex": "0x0",
        })
    if include_transfer:
        logs.append({
            "address": BSC_USDT_CONTRACT,
            "topics": [TRANSFER_TOPIC, address_topic(transfer_from), address_topic(transfer_to)],
            "data": uint_data(amount), "removed": False,
            "transactionHash": TX, "blockHash": BLOCK_HASH,
            "blockNumber": hex(block), "logIndex": "0x1",
        })
    responses = {
        "eth_chainId": hex(56),
        "eth_getCode": runtime,
        "eth_getTransactionByHash": {
            "hash": TX,
            "from": PAYER if action == "funded" else CALLER,
            "to": ESCROW,
            "blockHash": BLOCK_HASH,
            "blockNumber": hex(block),
        },
        "eth_getTransactionReceipt": {
            "transactionHash": TX,
            "blockHash": BLOCK_HASH,
            "status": "0x1",
            "blockNumber": hex(block),
            "logs": logs,
        },
        "eth_blockNumber": hex(latest),
        "eth_getBlockByNumber": {"number": hex(block), "hash": BLOCK_HASH, "timestamp": hex(1_800_000_000)},
    }
    return lambda method, params: responses[method]


@pytest.mark.parametrize("action", ["funded", "released", "refunded"])
def test_verifies_escrow_lifecycle_actions(action):
    evidence = verify_escrow_action(
        config(), TX, ESCROW_ID, "125", action=action,
        expected_payer=PAYER, rpc_call=mock_rpc(action=action),
    )
    assert evidence.verified is True
    assert evidence.action == action
    assert evidence.amount_raw == AMOUNT
    assert evidence.confirmations == 21

def test_rejects_runtime_code_mismatch():
    with pytest.raises(PaymentVerificationError, match="runtime code fingerprint"):
        verify_escrow_action(
            config("0" * 64), TX, ESCROW_ID, "125", action="funded",
            expected_payer=PAYER, rpc_call=mock_rpc(),
        )


@pytest.mark.parametrize("event,transfer", [(False, True), (True, False)])
def test_rejects_missing_event_or_transfer(event, transfer):
    with pytest.raises(PaymentVerificationError, match="must match exactly once"):
        verify_escrow_action(
            config(), TX, ESCROW_ID, "125", action="funded", expected_payer=PAYER,
            rpc_call=mock_rpc(include_event=event, include_transfer=transfer),
        )


def test_rejects_wrong_amount():
    with pytest.raises(PaymentVerificationError, match="terms mismatch|amount mismatch"):
        verify_escrow_action(
            config(), TX, ESCROW_ID, "125", action="funded", expected_payer=PAYER,
            rpc_call=mock_rpc(amount=AMOUNT - 1),
        )


def test_rejects_insufficient_confirmations():
    with pytest.raises(PaymentVerificationError, match="insufficient escrow confirmations"):
        verify_escrow_action(
            config(), TX, ESCROW_ID, "125", action="released", expected_payer=PAYER,
            rpc_call=mock_rpc(action="released", latest=105),
        )

def created_data(amount, funding_deadline, refund_after):
    return "0x" + "".join(format(v, "064x") for v in [amount, funding_deadline, refund_after])


def mock_created_rpc(amount=AMOUNT, terms_hash=TERMS_HASH,
                     funding_deadline=1_800_000_500, refund_after=1_800_086_400,
                     latest=120, block=100):
    log = {
        "address": ESCROW,
        "topics": [
            "0xa059c713430165273f3068baf286a05928bcf10e7e11b90e8269b11ed451bcdf",
            ESCROW_ID, address_topic(PAYER), terms_hash,
        ],
        "data": created_data(amount, funding_deadline, refund_after),
        "removed": False, "transactionHash": TX, "blockHash": BLOCK_HASH,
        "blockNumber": hex(block), "logIndex": "0x0",
    }
    responses = {
        "eth_chainId": hex(56), "eth_getCode": RUNTIME,
        "eth_getTransactionByHash": {"hash": TX, "from": CALLER, "to": ESCROW,
            "blockHash": BLOCK_HASH, "blockNumber": hex(block)},
        "eth_getTransactionReceipt": {"transactionHash": TX, "blockHash": BLOCK_HASH,
            "status": "0x1", "blockNumber": hex(block), "logs": [log]},
        "eth_blockNumber": hex(latest),
        "eth_getBlockByNumber": {"number": hex(block), "hash": BLOCK_HASH,
            "timestamp": hex(1_800_000_000)},
    }
    return lambda method, params: responses[method]

def test_verifies_escrow_created_terms_and_deadlines():
    evidence = verify_escrow_created(
        config(), TX, ESCROW_ID, "125", PAYER, TERMS_HASH,
        rpc_call=mock_created_rpc(),
    )
    assert evidence.verified is True
    assert evidence.payer_address == PAYER
    assert evidence.amount_raw == AMOUNT
    assert evidence.terms_hash == TERMS_HASH
    assert evidence.funding_deadline == 1_800_000_500
    assert evidence.refund_after == 1_800_086_400


def test_rejects_escrow_created_terms_mismatch():
    with pytest.raises(PaymentVerificationError, match="terms hash mismatch"):
        verify_escrow_created(
            config(), TX, ESCROW_ID, "125", PAYER, "0x" + "88" * 32,
            rpc_call=mock_created_rpc(),
        )

def test_rejects_escrow_created_amount_mismatch():
    with pytest.raises(PaymentVerificationError, match="amount mismatch"):
        verify_escrow_created(
            config(), TX, ESCROW_ID, "125", PAYER, TERMS_HASH,
            rpc_call=mock_created_rpc(amount=AMOUNT - 1),
        )


def test_rejects_invalid_created_deadline_ordering():
    with pytest.raises(PaymentVerificationError, match="invalid on-chain escrow deadlines"):
        verify_escrow_created(
            config(), TX, ESCROW_ID, "125", PAYER, TERMS_HASH,
            rpc_call=mock_created_rpc(funding_deadline=1_799_999_999),
        )


def test_record_payload_helpers_match_database_shape():
    created = verify_escrow_created(
        config(), TX, ESCROW_ID, "125", PAYER, TERMS_HASH,
        rpc_call=mock_created_rpc(),
    )
    creation_payload = creation_record_payload(config(), created)
    assert creation_payload["contract_address"] == ESCROW
    assert creation_payload["beneficiary_address"] == BENEFICIARY
    assert creation_payload["runtime_sha256"] == RUNTIME_SHA
    assert creation_payload["verified_at"].endswith("Z")

    funded = verify_escrow_action(
        config(), TX, ESCROW_ID, "125", action="funded",
        expected_payer=PAYER, rpc_call=mock_rpc(action="funded"),
    )
    lifecycle_payload = lifecycle_record_payload(funded)
    assert lifecycle_payload["action"] == "funded"
    assert lifecycle_payload["escrow_id"] == ESCROW_ID
    assert lifecycle_payload["verified_at"].endswith("Z")
