"""Retired legacy direct-charge adapter.

Direct SQLite/processor charging is not canonical. Commercial payment starts
from a governed fulfilment order and uses USDT on BSC.
"""
from __future__ import annotations

from empire_os.payment_rail_policy import RetiredPaymentRailError


def charge(*_args, **_kwargs):
    raise RetiredPaymentRailError(
        "legacy direct charge retired; use fulfilment order -> "
        "payment_governance -> BSC/USDT verification"
    )


def settle_ppc_invoice(*_args, **_kwargs):
    raise RetiredPaymentRailError(
        "legacy PPC invoice settlement retired; use canonical Revenue Truth"
    )
