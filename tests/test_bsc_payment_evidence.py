from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import empire_os.bsc_payment_evidence as adapter
from empire_os.bsc_usdt_verifier import BscUsdtConfig, BSC_USDT_CONTRACT, PaymentVerificationError

REQUEST, BUYER, ORDER = [str(__import__("uuid").UUID(int=n)) for n in (1, 2, 3)]
PAYER, TREASURY = "0x" + "33" * 20, "0x" + "22" * 20
TX = "0x" + "44" * 32
NOW = datetime(2026, 9, 17, tzinfo=timezone.utc)


class ReadOnlyDB:
    def __init__(self):
        self.rows = {
            "bsc_payment_requests": [{
                "id": REQUEST, "buyer_id": BUYER, "fulfilment_order_id": ORDER,
                "status": "approved", "approved_by": "human-review",
                "approved_at": "2026-09-16T00:00:00+00:00",
                "expires_at": "2026-09-18T00:00:00+00:00",
                "commercial_terms_sha256": "a" * 64,
                "amount_usdt": "100", "min_block_number": 99,
                "payer_address": PAYER, "treasury_address": TREASURY,
            }],
            "buyers": [{"id": BUYER}],
            "fulfilment_orders": [{
                "id": ORDER, "buyer_id": BUYER, "state": "accepted",
                "commercial_payload": {"commercial_terms_sha256": "a" * 64},
            }],
            "bsc_payment_evidence": [],
        }
    def select(self, table, filters, limit, columns="*"):
        return [deepcopy(r) for r in self.rows[table]
                if all(r.get(k) == v for k, v in filters.items())][:limit]


@pytest.fixture
def setup(monkeypatch):
    db = ReadOnlyDB()
    proof = {"amount_raw": 100 * 10**18, "block_number": 100,
             "token_decimals": 18, "verified": True}
    calls = []
    def verify(config, tx, amount, **kwargs):
        calls.append((tx, amount, kwargs["expected_payer"]))
        return SimpleNamespace(**proof, to_dict=lambda: dict(proof))
    monkeypatch.setattr(adapter, "verify_payment", verify)
    return db, calls, proof


def run(db):
    return adapter.preview_payment(
        REQUEST, TX, db=db, now=NOW,
        config=BscUsdtConfig("https://example.invalid", TREASURY, BSC_USDT_CONTRACT),
    )


def test_observe_never_records_or_recognizes_revenue(setup):
    db, calls, _ = setup
    result = run(db)
    assert result["mode"] == "OBSERVE"
    assert result["recorded"] is False and result["actual_revenue"] is False
    assert result["evidence"]["amount_raw"] == str(100 * 10**18)
    assert calls[0][2] == PAYER


@pytest.mark.parametrize("field,value", [
    ("status", "pending"), ("approved_by", ""), ("approved_at", None),
    ("expires_at", "2026-09-16T00:00:00+00:00"),
    ("commercial_terms_sha256", "bad"), ("amount_usdt", "NaN"),
    ("amount_usdt", 100.0),
    ("min_block_number", 0), ("payer_address", None),
    ("treasury_address", PAYER),
])
def test_rejects_invalid_request_before_chain_call(setup, field, value):
    db, calls, _ = setup
    db.rows["bsc_payment_requests"][0][field] = value
    with pytest.raises(PaymentVerificationError):
        run(db)
    assert calls == []


@pytest.mark.parametrize("table", ["buyers", "fulfilment_orders", "bsc_payment_requests"])
def test_missing_canonical_rows_fail_closed(setup, table):
    db, calls, _ = setup
    db.rows[table] = []
    with pytest.raises(PaymentVerificationError):
        run(db)
    assert not calls


@pytest.mark.parametrize("field,value", [
    ("buyer_id", REQUEST), ("state", "cancelled"), ("commercial_payload", {}),
])
def test_order_binding(setup, field, value):
    db, calls, _ = setup
    db.rows["fulfilment_orders"][0][field] = value
    with pytest.raises(PaymentVerificationError):
        run(db)
    assert not calls


@pytest.mark.parametrize("row", [
    {"transaction_hash": TX, "request_id": ORDER},
    {"transaction_hash": "0x" + "55" * 32, "request_id": REQUEST},
])
def test_preexisting_reservation_rejected(setup, row):
    db, calls, _ = setup
    db.rows["bsc_payment_evidence"] = [row]
    with pytest.raises(PaymentVerificationError, match="already recorded"):
        run(db)
    assert not calls


def test_historical_payment_is_rejected(setup):
    db, _, proof = setup
    proof["block_number"] = 98
    with pytest.raises(PaymentVerificationError, match="predates"):
        run(db)


def test_database_failure_propagates_without_fallback(setup):
    db, calls, _ = setup
    def failed(*args, **kwargs):
        raise RuntimeError("database unavailable")
    db.select = failed
    with pytest.raises(RuntimeError, match="unavailable"):
        run(db)
    assert not calls


def test_preview_with_real_verifier_and_offline_rpc():
    from test_bsc_usdt_verifier import mock_rpc
    result = adapter.preview_payment(
        REQUEST, TX, db=ReadOnlyDB(), now=NOW, rpc_call=mock_rpc(),
        config=BscUsdtConfig("https://example.invalid", TREASURY, BSC_USDT_CONTRACT),
    )
    assert result["evidence"]["verified"] is True
    assert result["evidence"]["amount_raw"] == str(125 * 10**18)
    assert result["recorded"] is False


def test_weak_confirmation_configuration_is_rejected(setup):
    db, calls, _ = setup
    with pytest.raises(PaymentVerificationError, match="12 confirmations"):
        adapter.preview_payment(
            REQUEST, TX, db=db, now=NOW,
            config=BscUsdtConfig("unused", TREASURY, BSC_USDT_CONTRACT,
                                min_confirmations=1),
        )
    assert not calls
