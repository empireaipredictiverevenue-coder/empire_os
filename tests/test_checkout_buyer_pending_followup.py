"""Guard the minimum buyer hand-off on the public checkout page."""
from pathlib import Path


def test_pending_bsc_payment_has_buyer_followup_without_wallet_disclosure():
    source=Path("apps/empire-public-site/src/app/buy/page.tsx").read_text()
    pending=source.split('result.payment_request_status === "pending" ? (',1)[1].split(
        'result.payment_request_status === "approved"',1
    )[0]
    assert "Email Empire AI about this order" in pending
    assert "mailto:reply@mail.empire-ai.co.uk" in pending
    assert "encodeURIComponent(" in pending
    assert "result.order_id" in pending
    assert "Do not transfer USDT before then" in pending
    assert "result.treasury_address" not in pending
    assert "result.amount_usdt" not in pending
