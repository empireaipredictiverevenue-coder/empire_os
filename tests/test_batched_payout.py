"""Regression tests for retirement of legacy batched payout rail."""
import pytest

from empire_os import batched_payout
from empire_os.payment_rail_policy import RetiredPaymentRailError


def test_legacy_batched_payout_reports_retired():
    state = batched_payout.status()
    assert state["status"] == "RETIRED"
    assert state["asset"] == "USDT"
    assert state["network"] == "BSC"
    assert state["execution_allowed"] is False


def test_legacy_batched_payout_execution_fails_closed():
    with pytest.raises(RetiredPaymentRailError):
        batched_payout.build_batched_payout_tx([])
    with pytest.raises(RetiredPaymentRailError):
        batched_payout.verify_batched_payout_tx("0x" + "0" * 64)
