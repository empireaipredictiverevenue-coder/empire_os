"""Retired legacy crypto-charge adapter.

Canonical crypto settlement is USDT on BSC through payment_governance and the
independent BSC USDT verifier. This module cannot create or reconcile payments.
"""
from __future__ import annotations

from empire_os.payment_rail_policy import RetiredPaymentRailError


def charge_crypto(*_args, **_kwargs):
    raise RetiredPaymentRailError(
        "legacy crypto charge retired; use governed BSC/USDT payment request"
    )


def reconcile_open_invoices(*_args, **_kwargs):
    raise RetiredPaymentRailError(
        "legacy invoice reconciliation retired; use verified BSC payment evidence"
    )
