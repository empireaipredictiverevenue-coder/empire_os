"""pay_link — shared BSC USDT (BEP20) pay-link builder.

Single source of truth for minting collectable payment deeplinks across
Empire OS. Every other module imports `build_pay_url` / `vault_address`
from here so the revenue vault stays consistent with the live bsc_listener.

Canonical deeplink format (Trust Wallet / BSC-compatible wallets):
    bsc:{VAULT}?amount={usd:.2f}&contract={USDT_BEP20}&memo={memo}

Amount convention: callers pass either a USD float or an integer in cents.
We normalise: if value >= 1000 we assume cents and divide by 100.
"""
from __future__ import annotations
import os

VAULT = os.environ.get("BSC_WALLET_ADDRESS", "0x1339b487046B0ad924a10c20b1791608EA8595a8")
USDT_BEP20 = os.environ.get(
    "BSC_USDT_CONTRACT", "0x55d398326f99059fF775485246999027B3197955"
)


def vault_address() -> str:
    """Authoritative revenue vault the bsc_listener watches."""
    return VAULT


def _to_usd(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    if v >= 1000:
        v = v / 100.0  # caller passed cents
    return round(v, 2)


def build_pay_url(*args, memo: str = None, ref_code: str = None, label: str = None) -> str:
    """Build a BSC USDT pay deeplink.

    Accepts flexible positional args (legacy call sites vary):
        build_pay_url(niche, price_usd, ref_code=...)
        build_pay_url(invoice_id, amount_cents, memo=...)
        build_pay_url(quote_id, amount_usdc)
    First positional = memo/label seed (id or niche). Second = amount.
    """
    seed = str(args[0]) if len(args) > 0 else "empire"
    amount = _to_usd(args[1]) if len(args) > 1 else 0.0

    if memo is None:
        memo = seed
    if ref_code:
        memo = f"{memo}:ref:{ref_code}"
    if label is None:
        label = f"Empire%20OS%20{seed}"

    return (
        f"bsc:{VAULT}"
        f"?amount={amount:.2f}"
        f"&contract={USDT_BEP20}"
        f"&label={label}"
        f"&memo={memo}"
    )
