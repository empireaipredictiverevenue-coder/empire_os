"""Empire Regime-Risk Signals (ERRS v1) — proprietary paper-only crypto research.

No exchange connectivity, market orders, private keys, investment advice or
promised accuracy. Source timestamps/hashes are assertions, NOT signatures.
Uses *completed and available* candles, with deterministic no-trade gates.
Conservative bar-based stop evaluation is deliberately separate from signal
formation to prevent look-ahead and intrabar optimistic fills.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
from statistics import mean
import json
from typing import Any

SCHEMA = "empire.predictive_intelligence.crypto_regime_risk_signals.v1"
MAX_BARS = 5000
MIN_BARS = 35


class CryptoSignalHold(ValueError):
    """Untrusted price/clock/market information is not admitted."""


def _time(value: Any) -> datetime:
    if type(value) is not str or not 19 <= len(value) <= 48:
        raise CryptoSignalHold("UTC source clock required")
    try:
        t=datetime.fromisoformat(value.replace("Z","+00:00"))
        if t.utcoffset() is None:
            raise ValueError("source time lacks zone")
        return t.astimezone(timezone.utc)
    except (ValueError,OverflowError):
        raise CryptoSignalHold("invalid source clock") from None


def _value(v: Any, *, zero_ok: bool = False) -> float:
    if (type(v) not in (int,float) or not isfinite(v) or v<0
            or (not zero_ok and v==0) or v>1e12):
        raise CryptoSignalHold("invalid numerical market value")
    return float(v)


def _bars(observations: Any, *, as_of: datetime) -> tuple[list[dict],int]:
    if type(observations) not in (list,tuple) or len(observations)>MAX_BARS:
        raise CryptoSignalHold("bounded bar history required")
    required={
        "closed_at","first_available_at","ingested_at",
        "open","high","low","close","volume","evidence_sha256",
    }
    parsed=[]
    last=None
    withheld=0
    for b in observations:
        if type(b) is not dict or set(b)!=required:
            raise CryptoSignalHold("unexpected candle envelope")
        t=_time(b["closed_at"])
        available=_time(b["first_available_at"])
        ingested=_time(b["ingested_at"])
        if last is not None and t<=last:
            raise CryptoSignalHold("candles must be unique chronological")
        last=t
        if not t<=available<=ingested:
            raise CryptoSignalHold("untrustworthy source chronology")
        if (type(b["evidence_sha256"]) is not str
                or len(b["evidence_sha256"])!=64
                or any(c not in "0123456789abcdef" for c in b["evidence_sha256"])):
            raise CryptoSignalHold("invalid evidence change digest")
        o=_value(b["open"]);h=_value(b["high"]);l=_value(b["low"])
        c=_value(b["close"]);vol=_value(b["volume"],zero_ok=True)
        if not (l<=min(o,c)<=max(o,c)<=h):
            raise CryptoSignalHold("inconsistent OHLC")
        if t>as_of or available>as_of or ingested>as_of:
            withheld+=1
            continue
        parsed.append({"t":t,"open":o,"high":h,"low":l,"close":c,"volume":vol,
                       "hash":b["evidence_sha256"]})
    return parsed,withheld


def _ema(values: list[float], window: int) -> float:
    if len(values)<window:
        raise CryptoSignalHold("inadequate EMA history")
    alpha=2/(window+1)
    acc=mean(values[:window])
    for v in values[window:]:
        acc=alpha*v+(1-alpha)*acc
    return acc


def _atr(bars: list[dict], lookback: int = 14) -> float:
    if len(bars)<lookback+1:
        raise CryptoSignalHold("inadequate ATR history")
    ranges=[]
    for i in range(len(bars)-lookback,len(bars)):
        b=bars[i];prev=bars[i-1]["close"]
        ranges.append(max(b["high"]-b["low"],abs(b["high"]-prev),
                          abs(b["low"]-prev)))
    return mean(ranges)


def _base(*, instrument: str, interval_minutes: int, as_of: datetime,
          points: list[dict], withheld:int) -> dict:
    digest=sha256(json.dumps([
        (p["t"].isoformat(),p["open"],p["high"],p["low"],
         p["close"],p["volume"],p["hash"]) for p in points
    ],separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {
        "schema_version":SCHEMA,"algorithm":"EMPIRE_REGIME_RISK_SIGNALS_V1",
        "mode":"OBSERVE","instrument":instrument,"bar_interval_minutes":interval_minutes,
        "as_of":as_of.isoformat(),"as_of_available_candle_count":len(points),
        "future_or_late_bars_withheld":withheld,
        "change_detection_digest_only":digest,
        "status":"NO_TRADE","reason":"INSUFFICIENT_HISTORY",
        "market_regime":"UNKNOWN","signal_side":"NONE",
        "paper_entry":None,"paper_stop_loss":None,"paper_take_profit":None,
        "paper_position_quantity":None,"paper_cash_risk_budget":None,
        "stop_fill_price_guaranteed":False,
        "paper_trade_entry_order_placed":False,"real_trade_execution_authorized":False,
        "source_issuer_authenticated":False,"market_data_rights_verified":False,
        "signal_accuracy_proven":False,"ninety_nine_percent_accuracy_proven":False,
        "future_profit_guaranteed":False,"leverage_authorized":False,
        "exchange_credentials_used":False,"wallet_access_used":False,
        "database_writes":False,"execution_authority":"none",
    }


def review_crypto_trade_signal(
    candles: Any, *,
    as_of: str, instrument: str, interval_minutes: int,
    equity_quote: float, spread_bps: float, fee_bps_round_trip: float,
    conservative_stop_slippage_bps: float,
) -> dict:
    """Long-only, risk-limited *paper hypothesis*; never buy/sell advice."""
    asof=_time(as_of)
    if (type(instrument) is not str or not 3<=len(instrument)<=30
            or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/_-" for c in instrument)
            or type(interval_minutes) is not int or interval_minutes not in (5,15,60,240,1440)):
        raise CryptoSignalHold("unsupported paper market or bar interval")
    equity=_value(equity_quote)
    spread=_value(spread_bps,zero_ok=True)
    fees=_value(fee_bps_round_trip,zero_ok=True)
    slip=_value(conservative_stop_slippage_bps,zero_ok=True)
    if equity>1e9 or any(x>500 for x in (spread,fees,slip)):
        raise CryptoSignalHold("unbounded research cost assumptions")
    bars,withheld=_bars(candles,as_of=asof)
    out=_base(instrument=instrument,interval_minutes=interval_minutes,
              as_of=asof,points=bars,withheld=withheld)
    if len(bars)<MIN_BARS:
        return out
    # Closed candle must be recent; stale market feeds are not actionable.
    lag=(asof-bars[-1]["t"]).total_seconds()/60
    if lag>2*interval_minutes:
        return {**out,"reason":"STALE_COMPLETED_CANDLE"}
    recent_gaps=[
        (bars[i]["t"]-bars[i-1]["t"]).total_seconds()/60
        for i in range(max(1,len(bars)-35),len(bars))
    ]
    if any(g<interval_minutes or g>1.5*interval_minutes for g in recent_gaps):
        return {**out,"reason":"MISSING_OR_IRREGULAR_MARKET_BARS"}
    last=bars[-1];prices=[b["close"] for b in bars]
    atr=_atr(bars)
    ema_fast=_ema(prices,12);ema_slow=_ema(prices,26)
    atr_fraction=atr/last["close"]
    volume_mean=mean(b["volume"] for b in bars[-21:-1])
    above=last["close"]>max(x["high"] for x in bars[-11:-1])
    liquid=(volume_mean>0 and last["volume"]>=1.10*volume_mean)
    trend=ema_fast>ema_slow*1.001
    market_regime=("TREND_UP" if trend else
                   "TREND_DOWN" if ema_fast<ema_slow*.999 else "RANGE")
    out.update(
        market_regime=market_regime,
        observed_at=last["t"].isoformat(),
        indicator_snapshot={
            "ema12":round(ema_fast,8),"ema26":round(ema_slow,8),
            "atr14":round(atr,8),"atr_fraction":round(atr_fraction,7),
            "breakout_10_completed_candles":above,
            "volume_above_1p1x_20bar_mean":liquid,
        },
    )
    if atr<=0 or not 0.003<=atr_fraction<=0.08:
        return {**out,"reason":"VOLATILITY_REGIME_UNSUITABLE"}
    if spread>25:
        return {**out,"reason":"SPREAD_TOO_WIDE"}
    if fees+spread+slip>100:
        return {**out,"reason":"ALL_IN_FRICTION_EXCESSIVE"}
    if not trend or not above or not liquid:
        return {**out,"reason":"REGIME_OR_ENTRY_CONFIRMATION_MISSING"}
    entry=last["close"]*(1+spread/20_000)
    # Stop wider than 2 ATR and beyond the prior 6-bar swing low.
    stop=min(entry-2*atr,min(b["low"] for b in bars[-7:-1])-0.25*atr)
    risk_distance=entry-stop
    if stop<=0 or risk_distance<=0 or risk_distance/entry>0.08:
        return {**out,"reason":"STOP_INVALID_OR_EXCESSIVE_DISTANCE"}
    worst_stop=stop*(1-slip/10_000)
    effective_loss_per_unit=(entry-worst_stop)+(entry+worst_stop)*fees/20_000
    if effective_loss_per_unit<=0:
        return {**out,"reason":"RISK_COST_ASSUMPTIONS_INVALID"}
    # Risk no more than 0.5% of hypothetical quote equity per signal.
    budget=equity*0.005
    qty=min(budget/effective_loss_per_unit, equity/entry)
    if qty<=0 or qty*entry < 1:
        return {**out,"reason":"PAPER_SIZE_TOO_SMALL"}
    # Gross take profit must cover a 2R gain and round-trip friction.
    target=entry+2*risk_distance+(entry*fees/10_000)
    return {**out,
            "status":"PAPER_SIGNAL_CANDIDATE_NOT_VALIDATED",
            "reason":"MATCHED_RESEARCH_INDICATORS_RISK_BUDGET_VALID",
            "signal_side":"LONG_RESEARCH_ONLY",
            "paper_entry":round(entry,8),
            "paper_stop_loss":round(stop,8),
            "paper_take_profit":round(target,8),
            "paper_position_quantity":round(qty,10),
            "paper_cash_risk_budget":round(budget,6),
            "paper_max_planned_loss_including_modeled_slippage_and_fees":round(
                qty*effective_loss_per_unit,6),
            "stop_order_may_gap_and_exceed_planned_loss":True,
            "paper_stop_trigger_mode":"MARKET_EXIT_SIMULATION_NOT_GUARANTEED",
            "research_profit_target_reward_multiple":2.0,
            "risk_sizing_fraction":0.005,
            "unvalidated_hypothesis_not_a_live_signal":True,
            }
