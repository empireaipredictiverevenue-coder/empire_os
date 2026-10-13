"""Offline tests for DB-sealed, buyer-bound private payment status reads."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from decimal import Decimal
from copy import deepcopy

import pytest

from empire_os.direct_bsc_buyer_status import BuyerAccessDenied, issue
from empire_os.direct_bsc_buyer_status_private_reader import (
    PrivateBuyerStatusPostgresReader, project_private_buyer_status,
    READER_ROLE, READ_SQL,
)

KEY = bytes(range(32))
NOW = datetime(2026, 10, 13, 18, tzinfo=timezone.utc)
TREASURY = "0x1339b487046b0ad924a10c20b1791608ea8595a8"
ORDER = str(uuid4())
BUYER = str(uuid4())
REQUEST = str(uuid4())
TERMS = "b" * 64
PAYER = "0x" + "1" * 40


def fixture():
    minted = issue(key=KEY, order_id=ORDER,
                   now=NOW-timedelta(minutes=10),
                   expires_at=NOW+timedelta(hours=2))
    access = {
        **minted["persist_only"],
        "request_id": REQUEST,
    }
    access["issued_at"] = access["issued_at"].isoformat()
    access["expires_at"] = access["expires_at"].isoformat()
    order = {
        "id": ORDER, "buyer_id": BUYER,
        "state": "accepted", "price_cents": 24900,
        "commercial_payload": {
            "commercial_terms_sha256": TERMS, "payer_wallet": PAYER,
        },
    }
    payment = {
        "id": REQUEST, "buyer_id": BUYER,
        "fulfilment_order_id": ORDER,
        "settlement_mode": "direct",
        "commercial_terms_sha256": TERMS,
        "payer_address": PAYER, "treasury_address": TREASURY,
        "amount_usdt": "249.00",
        "status": "pending", "approved_by": None,
        "approved_at": None,
        "expires_at": (NOW+timedelta(hours=1)).isoformat(),
    }
    return minted["deliver_token_once"], dict(
        access=access, order=order, payment=payment, evidence=None,
    )


def status_for(token, document, **kw):
    return project_private_buyer_status(
        bearer_token=token, hmac_key=KEY,
        read_by_fingerprint=lambda digest: document,
        approved_treasury=TREASURY, now=NOW, **kw,
    )


def test_bearer_fingerprint_only_reaches_private_reader():
    token, record = fixture()
    captured = []
    def read(digest):
        captured.append(digest)
        return record
    out = project_private_buyer_status(
        bearer_token=token, hmac_key=KEY,
        read_by_fingerprint=read,
        approved_treasury=TREASURY, now=NOW,
    )
    assert out == {"status": "awaiting_human_approval", "payment_instructions_ready": False}
    assert len(captured) == 1
    assert captured[0] == record["access"]["token_fingerprint"]
    assert token not in captured[0] and ORDER not in captured[0]


def test_after_human_approval_exact_trusted_payment_instructions():
    token, record = fixture()
    record["payment"]["status"] = "approved"
    record["payment"]["approved_by"] = "independent-human-operator"
    record["payment"]["approved_at"] = (NOW-timedelta(minutes=3)).isoformat()
    result = status_for(token, record)
    assert result["status"] == "approved_payment_instructions"
    assert result["amount_usdt"] == "249.00"
    assert result["treasury_address"] == TREASURY
    assert result["network"] == "BSC"
    assert "buyer_id" not in result and "token_fingerprint" not in result


@pytest.mark.parametrize("mutation", [
    lambda r: r["access"].update(token_fingerprint="0"*64),
    lambda r: r["access"].update(order_id=str(uuid4())),
    lambda r: r["access"].update(request_id=str(uuid4())),
    lambda r: r["access"].update(revoked_at=NOW.isoformat()),
    lambda r: r["access"].update(expires_at=(NOW-timedelta(seconds=1)).isoformat()),
    lambda r: r["access"].update(issued_at="2026-10-13"),
    lambda r: r["access"].update(expires_at="INVALID_TIME"),
    lambda r: r["order"].update(buyer_id=str(uuid4())),
    lambda r: r["order"].update(price_cents=19900),
    lambda r: r["order"]["commercial_payload"].update(payer_wallet="0x"+"2"*40),
    lambda r: r["payment"].update(amount_usdt="249.01"),
    lambda r: r["payment"].update(buyer_id=str(uuid4())),
    lambda r: r["payment"].update(settlement_mode="escrow"),
    lambda r: r["payment"].update(treasury_address="0x"+"2"*40),
    lambda r: r["payment"].update(fulfilment_order_id=str(uuid4())),
    lambda r: r["payment"].update(status="approved"),
    lambda r: r.update(access=None),
    lambda r: r.update(order=None),
    lambda r: r.update(payment="not-an-object"),
    lambda r: r.update(evidence="not-an-object"),
    lambda r: r.update(debug="should-never-have-this-field"),
])
def test_every_cross_buyer_invalid_date_or_unapproved_record_fails_closed(mutation):
    token, document = fixture()
    mutation(document)
    with pytest.raises(BuyerAccessDenied, match="payment_status_unavailable"):
        status_for(token, document)


@pytest.mark.parametrize("bad", [
    None, {}, [], "no row", {"access":{}, "order":{}, "payment":None, "evidence":None},
])
def test_missing_or_malformed_query_result_fails_closed(bad):
    token, _ = fixture()
    with pytest.raises(BuyerAccessDenied):
        status_for(token, bad)


def test_untrusted_transport_exception_no_original_secret_or_driver_message():
    token, _ = fixture()
    def fail(_digest):
        raise RuntimeError("password=SECRET db:connection info")
    with pytest.raises(BuyerAccessDenied, match="payment_status_unavailable") as error:
        project_private_buyer_status(
            bearer_token=token, hmac_key=KEY,
            read_by_fingerprint=fail,
            approved_treasury=TREASURY, now=NOW,
        )
    assert error.value.__cause__ is None


def test_rejects_wrong_bearer_without_even_calling_private_database():
    _, record = fixture()
    called = []
    with pytest.raises(BuyerAccessDenied):
        project_private_buyer_status(
            bearer_token="guessed-order-uuid",
            hmac_key=KEY,
            read_by_fingerprint=lambda d: called.append(d) or record,
            approved_treasury=TREASURY, now=NOW,
        )
    assert called == []


class FakeCursor:
    def __init__(self, outcome):
        self.outcome = outcome
        self.commands = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.commands.append((sql, params))
    def fetchone(self): return self.outcome


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self._cursor


def test_private_transport_always_starts_read_only_and_assumes_exact_role(monkeypatch):
    monkeypatch.setenv("EMPIREDB_DSN", "postgres://general-app")
    cur = FakeCursor(({"access": {}},))
    rpc = PrivateBuyerStatusPostgresReader(
        "postgres://dedicated-reader", connect_factory=lambda dsn: FakeConnection(cur),
    )
    assert rpc("a"*64) == {"access": {}}
    assert cur.commands == [
        ("SET TRANSACTION READ ONLY", None),
        ("SET LOCAL statement_timeout='2500ms'", None),
        ("SET LOCAL ROLE " + READER_ROLE, None),
        (READ_SQL, ("a"*64,)),
    ]


def test_rejects_general_app_dsn_and_missing_config(monkeypatch):
    monkeypatch.setenv("EMPIREDB_DSN", "postgres://general-app")
    with pytest.raises(BuyerAccessDenied):
        PrivateBuyerStatusPostgresReader("postgres://general-app", connect_factory=lambda s: None)
    with pytest.raises(BuyerAccessDenied):
        PrivateBuyerStatusPostgresReader("", connect_factory=lambda s: None)


@pytest.mark.parametrize("bad", ["", "0"*63, "invalid", "x"*64])
def test_invalid_db_digest_is_rejected_before_sql(bad):
    seen = []
    rpc = PrivateBuyerStatusPostgresReader(
        "postgres://dedicated-reader", connect_factory=lambda s: seen.append(s),
    )
    with pytest.raises(BuyerAccessDenied):
        rpc(bad)
    assert seen == []


def test_private_transport_rejects_none_or_multiple_rows():
    for outcome in (None, (), (1,2)):
        rpc = PrivateBuyerStatusPostgresReader(
            "postgres://dedicated-reader",
            connect_factory=lambda dsn: FakeConnection(FakeCursor(outcome)),
        )
        with pytest.raises(BuyerAccessDenied):
            rpc("a"*64)
