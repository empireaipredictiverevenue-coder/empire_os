from decimal import Decimal

import pytest

from empire_os.bsc_usdt_verifier import (
    BSC_USDT_CONTRACT,
    BscUsdtConfig,
    PaymentVerificationError,
    TRANSFER_TOPIC,
    verify_payment,
)

TOKEN = BSC_USDT_CONTRACT
WRONG_TOKEN = "0x1111111111111111111111111111111111111111"
TREASURY = "0x2222222222222222222222222222222222222222"
PAYER = "0x3333333333333333333333333333333333333333"
OTHER = "0x5555555555555555555555555555555555555555"
TX = "0x" + "44" * 32
OTHER_TX = "0x" + "66" * 32
BLOCK_HASH = "0x" + "77" * 32


def topic(address: str) -> str:
    return "0x" + "0" * 24 + address[2:].lower()


def mock_rpc(
    *,
    chain=56,
    amount_raw=125 * 10**18,
    recipient=TREASURY,
    sender=PAYER,
    token=TOKEN,
    latest=120,
    block=100,
    status=1,
    tx_hash=TX,
    receipt_hash=TX,
    logs_valid=True,
):
    logs = [{
        "address": token,
        "topics": [TRANSFER_TOPIC, topic(sender), topic(recipient)],
        "data": "0x" + format(amount_raw, "064x"),
        "removed": False,
        "transactionHash": TX,
        "blockHash": BLOCK_HASH,
        "blockNumber": hex(block),
        "logIndex": "0x0",
    }]
    responses = {
        "eth_chainId": hex(chain),
        "eth_getTransactionByHash": {
            "hash": tx_hash, "from": sender,
            "blockHash": BLOCK_HASH, "blockNumber": hex(block),
        },
        "eth_getTransactionReceipt": {
            "transactionHash": receipt_hash,
            "blockHash": BLOCK_HASH,
            "status": hex(status),
            "blockNumber": hex(block),
            "logs": logs if logs_valid else None,
        },
        "eth_call": hex(18),
        "eth_blockNumber": hex(latest),
        "eth_getBlockByNumber": {"number": hex(block), "hash": BLOCK_HASH},
    }
    return lambda method, params: responses[method]


def config() -> BscUsdtConfig:
    return BscUsdtConfig(
        rpc_url="https://example.invalid",
        treasury_address=TREASURY,
        token_contract=TOKEN,
        min_confirmations=12,
    )


def assert_rejected(message: str, **rpc_options):
    with pytest.raises(PaymentVerificationError, match=message):
        verify_payment(config(), TX, "100", rpc_call=mock_rpc(**rpc_options))


def test_verifies_matching_transfer():
    evidence = verify_payment(
        config(), TX, Decimal("100"), expected_payer=PAYER, rpc_call=mock_rpc()
    )
    assert evidence.verified is True
    assert evidence.chain_id == 56
    assert evidence.treasury_address == TREASURY
    assert evidence.token_contract == TOKEN
    assert evidence.sender_address == PAYER
    assert evidence.amount_token == "125"
    assert evidence.confirmations == 21


@pytest.mark.parametrize(
    ("message", "rpc_options"),
    [
        ("wrong chain id", {"chain": 1}),
        ("transaction failed", {"status": 0}),
        ("RPC transaction hash mismatch", {"tx_hash": OTHER_TX}),
        ("RPC transaction hash mismatch", {"receipt_hash": OTHER_TX}),
        ("no qualifying", {"recipient": OTHER}),
        ("no qualifying", {"token": WRONG_TOKEN}),
        ("no qualifying", {"amount_raw": 99 * 10**18}),
        ("insufficient confirmations", {"latest": 110}),
        ("receipt logs", {"logs_valid": False}),
    ],
)
def test_rejects_untrusted_or_insufficient_chain_evidence(message, rpc_options):
    assert_rejected(message, **rpc_options)


def test_rejects_wrong_payer():
    with pytest.raises(PaymentVerificationError, match="sender does not match"):
        verify_payment(config(), TX, "100", expected_payer=OTHER, rpc_call=mock_rpc())


@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "Infinity"])
def test_rejects_non_positive_or_non_finite_amount(amount):
    with pytest.raises(PaymentVerificationError, match="finite and positive"):
        verify_payment(config(), TX, amount, rpc_call=mock_rpc())


def test_rejects_amount_beyond_token_precision():
    rpc = mock_rpc()
    responses = {"eth_call": "0x6"}

    def six_decimal_rpc(method, params):
        return responses[method] if method in responses else rpc(method, params)

    with pytest.raises(PaymentVerificationError, match="exceeds token precision"):
        verify_payment(config(), TX, "1.0000001", rpc_call=six_decimal_rpc)


def test_rejects_malformed_transaction_hash():
    with pytest.raises(PaymentVerificationError, match="invalid transaction hash"):
        verify_payment(config(), "0xnot-a-hash", "100", rpc_call=mock_rpc())


def test_env_config_defaults_to_canonical_usdt(monkeypatch):
    monkeypatch.setenv("BSC_RPC_URL", "https://rpc.example.invalid")
    monkeypatch.setenv("BSC_TREASURY_ADDRESS", TREASURY)
    monkeypatch.delenv("BSC_USDT_TOKEN_CONTRACT", raising=False)
    assert BscUsdtConfig.from_env().token_contract == BSC_USDT_CONTRACT


def test_env_config_rejects_non_usdt_contract(monkeypatch):
    monkeypatch.setenv("BSC_RPC_URL", "https://rpc.example.invalid")
    monkeypatch.setenv("BSC_TREASURY_ADDRESS", TREASURY)
    monkeypatch.setenv("BSC_USDT_TOKEN_CONTRACT", WRONG_TOKEN)
    with pytest.raises(PaymentVerificationError, match="canonical BSC USDT"):
        BscUsdtConfig.from_env()


def test_direct_config_cannot_override_chain_or_token():
    bad_chain = BscUsdtConfig("unused", TREASURY, TOKEN, chain_id=1)
    with pytest.raises(PaymentVerificationError, match="not BSC mainnet"):
        verify_payment(bad_chain, TX, "100", rpc_call=mock_rpc())

    bad_token = BscUsdtConfig("unused", TREASURY, WRONG_TOKEN)
    with pytest.raises(PaymentVerificationError, match="canonical BSC USDT"):
        verify_payment(bad_token, TX, "100", rpc_call=mock_rpc())


@pytest.mark.parametrize("field,value", [
    ("removed", True),
    ("removed", None),
    ("blockHash", OTHER_TX),
    ("transactionHash", OTHER_TX),
    ("blockNumber", "0x65"),
    ("data", "0x1"),
    ("topics", [TRANSFER_TOPIC, topic(PAYER), topic(TREASURY), TX]),
])
def test_rejects_invalid_transfer_log(field, value):
    base = mock_rpc()
    def rpc(method, params):
        result = base(method, params)
        if method == "eth_getTransactionReceipt":
            result["logs"][0][field] = value
        return result
    with pytest.raises(PaymentVerificationError):
        verify_payment(config(), TX, "100", rpc_call=rpc)


@pytest.mark.parametrize("canonical", [
    None,
    {"number": "0x64", "hash": OTHER_TX},
    {"number": "0x65", "hash": BLOCK_HASH},
])
def test_rejects_orphaned_or_missing_block(canonical):
    base = mock_rpc()
    def rpc(method, params):
        if method == "eth_getBlockByNumber":
            return canonical
        return base(method, params)
    with pytest.raises(PaymentVerificationError, match="canonical"):
        verify_payment(config(), TX, "100", rpc_call=rpc)


def test_amount_checks_do_not_round_large_values():
    expected = "123456789012345678901234567890.000000000000000001"
    raw = 123456789012345678901234567890000000000000000001
    with pytest.raises(PaymentVerificationError, match="no qualifying"):
        verify_payment(config(), TX, expected, rpc_call=mock_rpc(amount_raw=raw-1))
    evidence = verify_payment(config(), TX, expected, rpc_call=mock_rpc(amount_raw=raw))
    assert evidence.amount_token == expected
    assert evidence.block_hash == BLOCK_HASH
    assert evidence.log_index == 0


@pytest.mark.parametrize("bad_hash", [
    "0x+" + "1" * 63, "0x" + "1_" * 32, "0x " + "1" * 63,
])
def test_rejects_non_hex_characters(bad_hash):
    with pytest.raises(PaymentVerificationError, match="invalid transaction hash"):
        verify_payment(config(), bad_hash, "100", rpc_call=mock_rpc())


def test_rejects_nonzero_topic_padding():
    base = mock_rpc()
    def rpc(method, params):
        result = base(method, params)
        if method == "eth_getTransactionReceipt":
            result["logs"][0]["topics"][2] = "0x" + "1" * 24 + TREASURY[2:]
        return result
    with pytest.raises(PaymentVerificationError, match="padding"):
        verify_payment(config(), TX, "100", rpc_call=rpc)
