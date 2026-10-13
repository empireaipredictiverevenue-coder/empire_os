"""Offline security tests for direct-BSC buyer payment status capabilities."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import copy
import re
import pytest

from empire_os.direct_bsc_buyer_status import (
    BuyerAccessDenied, fingerprint, issue, status,
)

KEY = bytes(range(32))
OTHER = bytes(reversed(range(32)))
NOW = datetime(2026, 10, 13, 13, tzinfo=timezone.utc)
TREASURY = "0x1339b487046b0ad924a10c20b1791608ea8595a8"
TOKEN_CONTRACT = "0x55d398326f99059ff775485246999027b3197955"
O, B, R = str(uuid4()), str(uuid4()), str(uuid4())
TERMS = "1" * 64


def fixture():
    minted = issue(key=KEY, order_id=O, now=NOW - timedelta(minutes=10),
                   expires_at=NOW + timedelta(hours=3))
    access = dict(minted["persist_only"])
    access["request_id"] = R
    payer = "0x" + "1"*40
    order = {"id": O, "buyer_id": B, "state": "accepted",
             "price_cents": 24900,
             "commercial_payload": {"commercial_terms_sha256": TERMS,
                                    "payer_wallet": payer}}
    payment = {"id": R, "buyer_id": B, "fulfilment_order_id": O,
               "settlement_mode": "direct", "commercial_terms_sha256": TERMS,
               "payer_address": payer,
               "treasury_address": TREASURY, "amount_usdt": "249",
               "status": "pending", "approved_by": None, "approved_at": None,
               "expires_at": NOW + timedelta(hours=2)}
    evidence = {"request_id": R, "fulfilment_order_id": O, "chain_id": 56,
                "token_contract": TOKEN_CONTRACT, "treasury_address": TREASURY,
                "commercial_terms_sha256": TERMS, "confirmations": 12}
    return dict(token=minted["deliver_token_once"], key=KEY, access=access,
                order=order, payment=payment, evidence=None, treasury=TREASURY, now=NOW), evidence


def test_issued_random_bearer_never_persisted_as_plaintext():
    result, _ = fixture()
    token = result["token"]
    assert re.fullmatch(r"ecs1_[A-Za-z0-9_-]{43}", token)
    assert token not in str(result["access"])
    assert fingerprint(token, KEY) == result["access"]["token_fingerprint"]
    second, _ = fixture()
    assert token != second["token"]


def test_missing_payment_request_does_not_issue_wallet():
    v, _ = fixture()
    v["access"]["request_id"] = None
    v["payment"] = None
    result = status(**v)
    assert result == {"status": "awaiting_payment_request", "payment_instructions_ready": False}


def test_pending_approval_never_discloses_treasury():
    v, _ = fixture()
    result = status(**v)
    assert result["status"] == "awaiting_human_approval"
    assert result["payment_instructions_ready"] is False
    assert "treasury_address" not in result
    assert "amount_usdt" not in result


def test_approved_direct_payment_instructions_only_after_human_evidence():
    v, _ = fixture()
    v["payment"]["status"] = "approved"
    v["payment"]["approved_by"] = "independent-operator"
    v["payment"]["approved_at"] = NOW - timedelta(minutes=2)
    result = status(**v)
    assert result == {"status": "approved_payment_instructions",
                      "payment_instructions_ready": True,
                      "amount_usdt": "249", "treasury_address": TREASURY,
                      "network": "BSC", "asset": "USDT", "chain_id": 56}


@pytest.mark.parametrize("modifier", (
    lambda v: v.update(token="invalid"),
    lambda v: v.update(token=str(uuid4())),
    lambda v: v.update(token=v["token"][:-1] + "*"),
    lambda v: v.update(key=OTHER),
    lambda v: v["access"].update(token_fingerprint="f"*64),
    lambda v: v["access"].update(revoked_at=NOW),
    lambda v: v["access"].update(expires_at=NOW),
    lambda v: v["access"].update(issued_at=NOW+timedelta(minutes=1)),
    lambda v: v["access"].update(order_id=str(uuid4())),
    lambda v: v["access"].update(request_id=str(uuid4())),
    lambda v: v["order"].update(id=str(uuid4())),
    lambda v: v["order"].update(buyer_id=str(uuid4())),
    lambda v: v["order"].update(state="cancelled"),
    lambda v: v["payment"].update(fulfilment_order_id=str(uuid4())),
    lambda v: v["payment"].update(buyer_id=str(uuid4())),
    lambda v: v["payment"].update(settlement_mode="escrow"),
    lambda v: v["payment"].update(treasury_address="0x" + "2"*40),
    lambda v: v["payment"].update(commercial_terms_sha256="2"*64),
    lambda v: v["payment"].update(payer_address="0x" + "6"*40),
    lambda v: v["order"].update(price_cents=19900),
    lambda v: v["order"]["commercial_payload"].update(payer_wallet="0x" + "7"*40),
    lambda v: v["payment"].update(amount_usdt="249.01"),
    lambda v: v.update(treasury="0x" + "3"*40),
    lambda v: v["payment"].update(status="unexpected"),
))
def test_cross_buyer_or_bad_capability_denied(modifier):
    v, _ = fixture()
    modifier(v)
    with pytest.raises(BuyerAccessDenied, match="payment_status_unavailable"):
        status(**v)


@pytest.mark.parametrize("amount", ("NaN", "Infinity", "0", "-1", "1.0000000000000000001", 0.2, True))
def test_invalid_amount_never_reaches_customer(amount):
    v, _ = fixture()
    v["payment"].update(status="approved", approved_by="human",
                        approved_at=NOW-timedelta(minutes=1), amount_usdt=amount)
    with pytest.raises(BuyerAccessDenied):
        status(**v)


def test_approved_without_human_evidence_denied():
    v, _ = fixture()
    v["payment"]["status"] = "approved"
    with pytest.raises(BuyerAccessDenied):
        status(**v)


@pytest.mark.parametrize("state", ("cancelled", "expired", "pending"))
def test_no_payment_instructions_for_nonapproved_states(state):
    v, _ = fixture()
    v["payment"]["status"] = state
    projection = status(**v)
    assert projection["payment_instructions_ready"] is False
    assert "treasury_address" not in projection


def test_expired_approval_hides_instructions():
    v, _ = fixture()
    v["payment"].update(status="approved", approved_by="human",
                        approved_at=NOW-timedelta(minutes=5),
                        expires_at=NOW-timedelta(seconds=1))
    assert status(**v)["payment_instructions_ready"] is False


def test_verified_evidence_requires_same_request_and_12_confirmations():
    v, evidence = fixture()
    v["payment"].update(status="approved", approved_by="human",
                        approved_at=NOW-timedelta(minutes=2))
    v["evidence"] = evidence
    result = status(**v)
    assert result == {"status": "payment_evidence_recorded", "payment_instructions_ready": False}
    v["evidence"] = {**evidence, "confirmations": 11}
    with pytest.raises(BuyerAccessDenied):
        status(**v)
    v["evidence"] = {**evidence, "request_id": str(uuid4())}
    with pytest.raises(BuyerAccessDenied):
        status(**v)


def test_issue_requires_bounded_expiry_strong_root_only_pepper_and_uuid():
    with pytest.raises(BuyerAccessDenied):
        issue(key=b"short", order_id=O, now=NOW, expires_at=NOW+timedelta(hours=2))
    with pytest.raises(BuyerAccessDenied):
        issue(key=KEY, order_id=O, now=NOW, expires_at=NOW+timedelta(days=3))
    with pytest.raises(BuyerAccessDenied):
        issue(key=KEY, order_id="guessable-order", now=NOW, expires_at=NOW+timedelta(hours=1))


def test_recorded_evidence_without_human_approval_denied():
    v, evidence = fixture()
    v["payment"]["status"] = "approved"
    v["evidence"] = evidence
    with pytest.raises(BuyerAccessDenied):
        status(**v)


@pytest.mark.parametrize("changed", (
    {"chain_id": 97},
    {"token_contract": "0x" + "4"*40},
    {"treasury_address": "0x" + "5"*40},
    {"commercial_terms_sha256": "2"*64},
    {"fulfilment_order_id": str(uuid4())},
    {"confirmations": True},
))
def test_recorded_evidence_must_match_canonical_receipt(changed):
    v, evidence = fixture()
    v["payment"].update(status="approved", approved_by="human",
                        approved_at=NOW - timedelta(minutes=2))
    v["evidence"] = {**evidence, **changed}
    with pytest.raises(BuyerAccessDenied):
        status(**v)


def test_capability_never_embeds_order_or_buyer_identity():
    v, _ = fixture()
    assert O not in v["token"] and B not in v["token"] and R not in v["token"]
    assert v["access"]["token_fingerprint"] != v["token"]
    assert all(ch not in v["token"] for ch in (".", "/", "+", "="))
