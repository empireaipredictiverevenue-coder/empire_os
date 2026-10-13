"""Existing checkout orders need actionable, nonpayable browser receipts."""
from pathlib import Path

import pytest

PAGE = Path("apps/empire-public-site/src/app/buy/page.tsx")


def _replay_section():
    source = PAGE.read_text(encoding="utf-8")
    assert source.count('result.payment_request_status === "existing_order_review_required"') == 1
    replay = source.split(
        'result.payment_request_status === "existing_order_review_required"', 1,
    )[1].split(
        'result.payment_request_created && result.payment_request_status === "approved"', 1,
    )[0]
    return source, replay


def test_existing_order_shows_reference_and_original_order_recovery():
    source, replay = _replay_section()
    assert "result.order_id ?" in replay
    assert "Your order is already recorded" in replay
    assert "Order reference: {result.order_id}" in replay
    assert "No new" in replay and "payment request was created by this retry" in replay
    assert "independent review" in replay
    assert "Do not" in replay and "transfer USDT" in replay
    assert "Do not" in replay and "replacement order" in replay
    assert "mailto:reply@mail.empire-ai.co.uk?subject=" in replay
    assert "encodeURIComponent(" in replay
    assert "Empire AI existing checkout order" in replay
    assert "role=\"status\"" in replay
    assert source.index('result.payment_request_status === "pending"') < (
        source.index('result.payment_request_status === "existing_order_review_required"')
    ) < source.index('result.payment_request_status === "approved"')


@pytest.mark.parametrize("secret_field", [
    "result.treasury_address", "result.amount_usdt",
    "result.payment_request_id", "result.payer_wallet",
])
def test_replayed_order_never_exposes_payment_information(secret_field):
    _, replay = _replay_section()
    assert secret_field not in replay


def test_checkout_replay_creates_no_second_financial_request():
    source, replay = _replay_section()
    assert "/v1/checkout/orders" not in replay
    assert "fetch(" not in replay
    assert "copyTreasury" not in replay
    assert "crypto.randomUUID()" not in replay
    assert "Email Empire AI with this order reference" in replay
    assert "No payment instructions are" in replay
    assert "payment_request_created" not in replay
    assert "result.order_id ?" in replay
    assert "result.payment_request_status === \"approved\"" in source
