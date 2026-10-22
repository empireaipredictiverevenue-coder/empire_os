"""One-bar paper-only exit-risk stress evaluator for Empire Regime-Risk Signals.

No exchange orders. A triggered stop is NOT guaranteed to fill at its level.
Conservative rules: market gap beyond stop exits at unfavorable open minus
modeled slippage; both stop and take-profit touched => stop FIRST.
A single candle never establishes accuracy or a backtested edge.
"""
from __future__ import annotations

from datetime import datetime,timezone
from math import isfinite
from typing import Any

from empire_os.predictive_crypto_signal_research import (
    CryptoSignalHold,_time,_value,
)

SCHEMA="empire.predictive_intelligence.crypto_stop_loss_paper_stress.v1"


def paper_exit_stress(
    signal: dict, next_candle: dict, *,
    quote_fee_bps_round_trip: float,
    stop_slippage_bps: float,
    paper_position_assumed_open: bool = False,
) -> dict:
    if (type(signal) is not dict
            or signal.get("algorithm")!="EMPIRE_REGIME_RISK_SIGNALS_V1"
            or signal.get("mode")!="OBSERVE"
            or signal.get("status")!="PAPER_SIGNAL_CANDIDATE_NOT_VALIDATED"
            or signal.get("signal_side")!="LONG_RESEARCH_ONLY"
            or signal.get("real_trade_execution_authorized") is not False
            or signal.get("source_issuer_authenticated") is not False
            or signal.get("ninety_nine_percent_accuracy_proven") is not False):
        raise CryptoSignalHold("invalid paper signal source")
    entry=_value(signal.get("paper_entry"))
    stop=_value(signal.get("paper_stop_loss"))
    target=_value(signal.get("paper_take_profit"))
    quantity=_value(signal.get("paper_position_quantity"))
    budget=_value(signal.get("paper_cash_risk_budget"))
    fees=_value(quote_fee_bps_round_trip,zero_ok=True)
    slip=_value(stop_slippage_bps,zero_ok=True)
    if (not stop<entry<target or fees>500 or slip>500
            or budget>1e8 or quantity>1e9
            or type(paper_position_assumed_open) is not bool):
        raise CryptoSignalHold("invalid paper stop/target/risk bounds")
    if type(next_candle) is not dict or set(next_candle)!={
        "closed_at","open","high","low","close",
    }:
        raise CryptoSignalHold("one complete future OHLC candle required")
    t=_time(next_candle["closed_at"])
    if t<=_time(signal["as_of"]):
        raise CryptoSignalHold("paper outcome must close after signal generation")
    o=_value(next_candle["open"]);h=_value(next_candle["high"])
    l=_value(next_candle["low"]);c=_value(next_candle["close"])
    if not l<=min(o,c)<=max(o,c)<=h:
        raise CryptoSignalHold("future OHLC inconsistent")
    base={
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "source_is_untrusted_paper_research":True,
        "entry_filled_or_submitted_to_exchange":False,
        "already_open_position_is_simulated_only":paper_position_assumed_open,
        "paper_signal_not_backtested_or_verified_for_accuracy":True,
        "stop_execution_price_guaranteed":False,
        "stop_may_be_worse_than_modeled_slippage":True,
        "execution_authority":"none","database_writes":False,
        "exchange_order_submitted":False,"wallet_or_margin_permissions":False,
        "validated_live_profit_or_trade_receipt":False,
    }
    # Entry assumed at signal price, only to isolate stop-risk impact.
    # If the market opens beyond the intended entry or already under stop,
    # the simulation cancels rather than pretending a fill occurred.
    if (not paper_position_assumed_open and
            (o<=stop or o>=target or abs(o-entry)/entry>0.0025)):
        return {**base,"status":"PAPER_ENTRY_CANCELLED_GAP_OR_CHASE",
                "hypothetical_net_pnl_quote":None,
                "slippage_model_applied":False,
                "planned_risk_exceeded":None}
    if l<=stop:
        kind="PAPER_STOP_HIT"
        # A gap in a LATER intrabar path is unknowable from OHLC; conservatively
        # assume at least the modeled adverse stop slippage.
        price=min(stop,o)*(1-slip/10_000)
    elif h>=target:
        kind="PAPER_TAKE_PROFIT_HIT"
        price=target
    else:
        kind="PAPER_STILL_OPEN"
        price=None
    pnl=None
    if price is not None:
        pnl=quantity*(price-entry)-(quantity*(entry+price)*fees/20_000)
    return {
        **base,"status":kind,
        "hypothetical_exit_price":round(price,8) if price is not None else None,
        "hypothetical_net_pnl_quote":round(pnl,8) if pnl is not None else None,
        "planned_risk_exceeded":(
            pnl < -budget-max(1e-6,budget*1e-8)
            if pnl is not None else None
        ),
        "both_stop_and_take_profit_hit_conservatively_prioritized_stop":(
            l<=stop and h>=target),
        "slippage_model_applied": l<=stop,
    }
