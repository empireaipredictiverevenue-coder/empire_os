"""Stop-first same-bar resolution and adverse gap stress (paper only)."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from copy import deepcopy
import pytest

from empire_os.predictive_crypto_stop_loss_simulator import paper_exit_stress
from empire_os.predictive_crypto_signal_research import CryptoSignalHold
from tests.test_predictive_crypto_signal_research import query

FUTURE=(datetime(2026,8,1,tzinfo=timezone.utc)+timedelta(hours=40)).isoformat()


def candle(entry,stop,target,variant="stop"):
    if variant=="both":
        return dict(closed_at=FUTURE,open=entry,high=target*1.01,
                    low=stop*.99,close=entry)
    if variant=="stop":
        return dict(closed_at=FUTURE,open=entry,high=entry*1.01,
                    low=stop*.99,close=stop)
    if variant=="target":
        return dict(closed_at=FUTURE,open=entry,high=target*1.01,
                    low=entry*.99,close=target)
    if variant=="gap":
        return dict(closed_at=FUTURE,open=stop*.82,high=stop*.86,
                    low=stop*.75,close=stop*.8)
    if variant=="open":
        return dict(closed_at=FUTURE,open=entry*1.07,high=entry*1.08,
                    low=entry*1.06,close=entry*1.07)


def simulate(variant,**options):
    r=query()
    return paper_exit_stress(
        r,candle(r["paper_entry"],r["paper_stop_loss"],r["paper_take_profit"],variant),
        quote_fee_bps_round_trip=20,stop_slippage_bps=35,**options,
    )


def test_both_target_and_stop_hit_forces_stop_not_perfect_win():
    x=simulate("both")
    assert x["status"]=="PAPER_STOP_HIT"
    assert x["both_stop_and_take_profit_hit_conservatively_prioritized_stop"] is True
    assert x["hypothetical_net_pnl_quote"]<0
    assert x["exchange_order_submitted"] is False
    assert x["stop_execution_price_guaranteed"] is False


def test_stop_risk_budget_with_slippage_never_promises_guarantee():
    x=simulate("stop")
    assert x["status"]=="PAPER_STOP_HIT"
    assert x["planned_risk_exceeded"] is False
    assert x["stop_may_be_worse_than_modeled_slippage"] is True


def test_gap_through_stop_can_exceed_budget_on_assumed_open_position():
    x=simulate("gap",paper_position_assumed_open=True)
    assert x["status"]=="PAPER_STOP_HIT"
    assert x["hypothetical_net_pnl_quote"]<0
    assert x["planned_risk_exceeded"] is True
    assert x["already_open_position_is_simulated_only"] is True
    assert x["entry_filled_or_submitted_to_exchange"] is False


def test_next_open_gap_before_entry_cancels_without_trade():
    x=simulate("gap")
    assert x["status"]=="PAPER_ENTRY_CANCELLED_GAP_OR_CHASE"
    assert x["hypothetical_net_pnl_quote"] is None
    x=simulate("open")
    assert x["status"]=="PAPER_ENTRY_CANCELLED_GAP_OR_CHASE"


def test_take_profit_pnl_net_of_round_trip_costs():
    x=simulate("target")
    assert x["status"]=="PAPER_TAKE_PROFIT_HIT"
    assert x["hypothetical_net_pnl_quote"]>0
    assert x["validated_live_profit_or_trade_receipt"] is False


def test_invalid_future_candle_fails_closed_and_forged_signal_refused():
    r=query()
    row=candle(r["paper_entry"],r["paper_stop_loss"],r["paper_take_profit"])
    row["high"]=row["low"]/2
    with pytest.raises(CryptoSignalHold):
        paper_exit_stress(r,row,quote_fee_bps_round_trip=20,stop_slippage_bps=35)
    forged=deepcopy(r)
    forged["real_trade_execution_authorized"]=True
    with pytest.raises(CryptoSignalHold):
        paper_exit_stress(forged,candle(r["paper_entry"],r["paper_stop_loss"],r["paper_take_profit"]),
                          quote_fee_bps_round_trip=20,stop_slippage_bps=35)
