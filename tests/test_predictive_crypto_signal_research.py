"""Private proprietary stop-loss-first crypto paper signal research."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
import math

import pytest
from empire_os.predictive_crypto_signal_research import (
    CryptoSignalHold, review_crypto_trade_signal,
)

START=datetime(2026,8,1,tzinfo=timezone.utc)
PARAMS=dict(instrument="BTC/USDT",interval_minutes=60,equity_quote=10000.,
            spread_bps=10,fee_bps_round_trip=20,
            conservative_stop_slippage_bps=35)


def bars(*,count=38,volume_last=160):
    out=[]
    for i in range(count):
        close=100+i*.30
        opening=close-.14
        t=START+timedelta(hours=i+1)
        out.append({
            "closed_at":t.isoformat(),
            "first_available_at":(t+timedelta(seconds=10)).isoformat(),
            "ingested_at":(t+timedelta(seconds=20)).isoformat(),
            "open":round(opening,6),"high":round(close+.13,6),
            "low":round(opening-.28,6),"close":round(close,6),
            "volume":volume_last if i==count-1 else 100,
            "evidence_sha256":f"{i+1:064x}",
        })
    return out


def query(values=None,*,asof=None,**opts):
    values=bars() if values is None else values
    stamp=asof or (START+timedelta(hours=len(values),minutes=5)).isoformat()
    return review_crypto_trade_signal(values,as_of=stamp,**{**PARAMS,**opts})


def test_eligible_research_candidate_has_stop_before_entry_and_costed_risk():
    result=query()
    assert result["status"]=="PAPER_SIGNAL_CANDIDATE_NOT_VALIDATED"
    assert result["signal_side"]=="LONG_RESEARCH_ONLY"
    assert result["market_regime"]=="TREND_UP"
    assert result["paper_stop_loss"]<result["paper_entry"]<result["paper_take_profit"]
    assert result["paper_cash_risk_budget"]==50.
    assert result["paper_max_planned_loss_including_modeled_slippage_and_fees"]<=50.00001
    assert result["risk_sizing_fraction"]==.005
    assert result["stop_order_may_gap_and_exceed_planned_loss"] is True
    assert result["stop_fill_price_guaranteed"] is False
    assert result["ninety_nine_percent_accuracy_proven"] is False
    assert result["real_trade_execution_authorized"] is False
    assert result["wallet_access_used"] is False
    assert result["exchange_credentials_used"] is False
    assert result["database_writes"] is False
    assert result["execution_authority"]=="none"


def test_sparse_or_stale_history_abstains():
    assert query(bars(count=25))["reason"]=="INSUFFICIENT_HISTORY"
    later=(START+timedelta(days=8)).isoformat()
    assert query(asof=later)["reason"]=="STALE_COMPLETED_CANDLE"


def test_normal_volume_no_breakout_abstains_without_signals():
    candles=bars(volume_last=90)
    result=query(candles)
    assert result["reason"]=="REGIME_OR_ENTRY_CONFIRMATION_MISSING"
    assert result["paper_stop_loss"] is None
    assert result["paper_position_quantity"] is None


def test_market_volatility_or_spread_or_fee_excessive_abstains():
    r=query(spread_bps=35)
    assert r["reason"]=="SPREAD_TOO_WIDE"
    r=query(fee_bps_round_trip=200)
    assert r["reason"]=="ALL_IN_FRICTION_EXCESSIVE"
    assert r["signal_side"]=="NONE"


def test_does_not_use_candle_not_available_at_asof():
    original=query()
    future=bars(count=39)[-1]
    result=query([*bars(),future],asof=(START+timedelta(hours=38,minutes=5)).isoformat())
    assert result["future_or_late_bars_withheld"]==1
    assert result["paper_stop_loss"]==original["paper_stop_loss"]
    assert result["change_detection_digest_only"]==original["change_detection_digest_only"]


def test_late_ingested_closed_candle_withheld_not_backfilled():
    original=query()
    candidate=bars()
    candidate[-1]["ingested_at"]=(START+timedelta(hours=40)).isoformat()
    result=query(candidate)
    assert result["future_or_late_bars_withheld"]==1
    assert result["status"]=="NO_TRADE"
    assert result["reason"]=="STALE_COMPLETED_CANDLE" or result["reason"]=="REGIME_OR_ENTRY_CONFIRMATION_MISSING"


def test_duplicate_and_out_of_order_bars_rejected():
    sample=bars()
    with pytest.raises(CryptoSignalHold):
        query([*sample,sample[-1]])
    with pytest.raises(CryptoSignalHold):
        query(list(reversed(sample)))


@pytest.mark.parametrize("change",[
    lambda x:x.update(open=0),
    lambda x:x.update(high=x["close"]-5),
    lambda x:x.update(low=x["close"]+5),
    lambda x:x.update(volume=-2),
    lambda x:x.update(volume=float("nan")),
    lambda x:x.update(volume=True),
    lambda x:x.update(close=math.inf),
    lambda x:x.update(ingested_at="2026-08-01T03:00:00"),
    lambda x:x.update(evidence_sha256="not a hash"),
    lambda x:x.update(unexpected="x"),
])
def test_invalid_market_data_fails_closed(change):
    candidate=bars()
    change(candidate[4])
    with pytest.raises(CryptoSignalHold):
        query(candidate)


def test_source_and_live_gates_cannot_be_claimed_from_fixture():
    original=bars()
    summary=query(original)
    assert all(summary[k] is False for k in (
        "source_issuer_authenticated","market_data_rights_verified",
        "signal_accuracy_proven","ninety_nine_percent_accuracy_proven",
        "future_profit_guaranteed","real_trade_execution_authorized",
        "exchange_credentials_used","leverage_authorized",
        "paper_trade_entry_order_placed",
    ))
    assert original==bars()


@pytest.mark.parametrize("invalid",["btcusdt","BTC USDT","../","BTC@USD"])
def test_unreviewed_instrument_rejected(invalid):
    with pytest.raises(CryptoSignalHold):
        query(instrument=invalid)


def test_synthetic_research_does_not_assert_trading_performance():
    x=query()
    assert "profit_factor" not in x
    assert "win_rate" not in x
    assert "trade_executed" not in x
    assert "signal_accuracy_proven" in x
    assert x["signal_accuracy_proven"] is False
