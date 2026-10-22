"""Private personal-use crypto signal evaluation with a conservative next-next-bar fill.

Own ERRS v1 algorithm (no external signal subscriptions), existing stop simulator
and paper scorecard. A signal inferred after the completed candle's ingestion
cannot be filled at the already-passed opening price of the immediately
following candle. Delay until the NEXT available opening; abstain on large
gaps, use pessimistic stop-first OHLC rules, include fees and slippage.

Never an authenticated exchange receipt, independent validated alpha, live
investment instruction, assured stop execution or commercial signal product.
"""
from __future__ import annotations

from datetime import timedelta
from math import isfinite
import json
from hashlib import sha256
from typing import Any

from empire_os.predictive_crypto_signal_research import (
    CryptoSignalHold, _bars, _time, _value, review_crypto_trade_signal,
)
from empire_os.predictive_crypto_research_scorecard import review_paper_outcomes

SCHEMA="empire.predictive_intelligence.crypto_personal_paper_walkforward.v1"
MIN_BARS=100
MAX_HOLD_BARS=24
DECISION_DELAY_BARS=2
TEST_SPLIT_FRACTION=.7


def _cancel(record: dict, reason: str) -> dict:
    return {
        "signal_closed_at":record["observed_at"],
        "status":"PAPER_ENTRY_CANCELLED",
        "reason":reason,
        "net_pnl_quote":None,
        "stop_execution_guaranteed":False,
    }


def _exit_outcome(*, plan: dict, rows: list[dict], index: int,
                  spread_bps: float, fee_bps_round_trip: float,
                  stop_slippage_bps: float, equity: float) -> tuple[dict,int] | None:
    # Plan created strictly from i's completed available candle. No fills
    # can occur until bar i+2 starts; i+1 open predates decision ingestion.
    start=index+DECISION_DELAY_BARS
    if start >= len(rows):
        return None
    first=rows[start]
    paper_ref=plan["paper_entry"]
    stop=plan["paper_stop_loss"]
    target=plan["paper_take_profit"]
    opening=first["open"]
    if (opening<=stop or opening>=target
            or abs(opening-paper_ref)/paper_ref>.0025):
        return _cancel(plan,"NEXT_AVAILABLE_OPEN_GAPPED_OR_CHASE"),start
    entry=opening*(1+spread_bps/20_000+stop_slippage_bps/10_000)
    if entry>=target or entry<=stop:
        return _cancel(plan,"EXECUTION_COST_INVALIDATES_RISK_PLAN"),start
    worst_stop=stop*(1-stop_slippage_bps/10_000)
    per_unit_loss=entry-worst_stop + (entry+worst_stop)*fee_bps_round_trip/20_000
    if per_unit_loss<=0:
        return _cancel(plan,"UNSAFE_COSTED_STOP"),start
    risk_budget=equity*.005
    quantity=min(risk_budget/per_unit_loss,equity/entry)
    if quantity<=0 or quantity*entry<1:
        return _cancel(plan,"MINIMUM_PAPER_SIZE_NOT_REACHED"),start

    final=min(len(rows)-1,start+MAX_HOLD_BARS-1)
    for j in range(start,final+1):
        bar=rows[j]
        if bar["low"]<=stop:
            exit_level=min(bar["open"],stop)*(1-stop_slippage_bps/10_000)
            kind="PAPER_STOP_LOSS"
        elif bar["high"]>=target:
            exit_level=target
            kind="PAPER_TAKE_PROFIT"
        elif j==final:
            if final<start+MAX_HOLD_BARS-1:
                # If the time horizon extends beyond the observed dataset,
                # this is RIGHT-CENSORED, never an artificial profitable exit.
                return {
                    "status":"PAPER_RIGHT_CENSORED",
                    "reason":"OPEN_HORIZON_UNOBSERVED",
                    "signal_closed_at":plan["observed_at"],
                    "net_pnl_quote":None,
                    "stop_execution_guaranteed":False,
                },j
            # A fully observed time-out pays exit slippage and fees.
            exit_level=bar["close"]*(1-stop_slippage_bps/10_000)
            kind="PAPER_TIME_EXIT"
        else:
            continue
        pnl=quantity*(exit_level-entry) - (
            quantity*(entry+exit_level)*fee_bps_round_trip/20_000
        )
        result={
            "signal_closed_at":plan["observed_at"],
            "paper_entry_bar_closed_at":first["t"].isoformat(),
            "paper_exit_bar_closed_at":bar["t"].isoformat(),
            "status":kind,
            "entry_quote":round(entry,8),
            "stop_quote":round(stop,8),
            "take_profit_quote":round(target,8),
            "paper_fill_quantity":round(quantity,10),
            "net_pnl_quote":round(pnl,8),
            "planned_risk_budget_quote":round(risk_budget,8),
            "risk_budget_may_be_exceeded_on_stop_gap":True,
            "budget_exceeded_by_simulated_gap":pnl<-risk_budget,
            "stop_execution_guaranteed":False,
            "intrabar_stop_prioritized_over_target":(
                bar["low"]<=stop and bar["high"]>=target
            ),
        }
        return result,j
    raise CryptoSignalHold("unresolved paper exit path")


def review_crypto_personal_walkforward(
    candles: Any, *, as_of: str, instrument: str, interval_minutes: int,
    equity_quote: float, spread_bps: float, fee_bps_round_trip: float,
    conservative_stop_slippage_bps: float,
) -> dict:
    now=_time(as_of)
    equity=_value(equity_quote)
    spread=_value(spread_bps,zero_ok=True)
    fees=_value(fee_bps_round_trip,zero_ok=True)
    slip=_value(conservative_stop_slippage_bps,zero_ok=True)
    # Reuse existing market and parameter admission; never use "99%".
    admitted=review_crypto_trade_signal(
        candles,as_of=as_of,instrument=instrument,
        interval_minutes=interval_minutes,equity_quote=equity,
        spread_bps=spread,fee_bps_round_trip=fees,
        conservative_stop_slippage_bps=slip,
    )
    parsed,withheld=_bars(candles,as_of=now)
    if (type(interval_minutes) is not int or
            len(parsed)>5000 or len(parsed)<MIN_BARS):
        raise CryptoSignalHold("at least 100 original completed market bars required")
    if withheld or len(parsed)!=len(candles):
        raise CryptoSignalHold("incomplete or delayed original market history")
    # Historical time gaps/duplicates are not legitimate continuous orders.
    for i in range(1,len(parsed)):
        interval=(parsed[i]["t"]-parsed[i-1]["t"]).total_seconds()/60
        if interval!=interval_minutes:
            raise CryptoSignalHold("missing or irregular original bar")
    # As-of needs an actual completed recently available bar.
    if (now-parsed[-1]["t"]).total_seconds()/60>2*interval_minutes:
        raise CryptoSignalHold("stale private market data")
    split=max(35,int(len(parsed)*TEST_SPLIT_FRACTION))
    accepted=[]
    cancellations=[]
    censored=0
    skipped=0
    halted=False
    idx=split
    last_completed_index=len(parsed)-1
    portfolio=equity
    initial=equity
    consecutive_losses=0
    while idx<last_completed_index-DECISION_DELAY_BARS:
        cutoff=_time(candles[idx]["ingested_at"])
        if cutoff>=parsed[idx+1]["t"]:
            skipped+=1;idx+=1
            continue
        # Only pass prefix <= decision time. This protects against future
        # candle information, including future corrections/ingestion.
        plan=review_crypto_trade_signal(
            candles[:idx+1],as_of=cutoff.isoformat(),
            instrument=instrument,interval_minutes=interval_minutes,
            equity_quote=portfolio,spread_bps=spread,
            fee_bps_round_trip=fees,
            conservative_stop_slippage_bps=slip,
        )
        if plan["status"]!="PAPER_SIGNAL_CANDIDATE_NOT_VALIDATED":
            skipped+=1;idx+=1
            continue
        filled=_exit_outcome(
            plan=plan,rows=parsed,index=idx,spread_bps=spread,
            fee_bps_round_trip=fees,stop_slippage_bps=slip,equity=portfolio,
        )
        if filled is None:
            break
        record,end=filled
        if record["net_pnl_quote"] is None:
            if record["status"]=="PAPER_RIGHT_CENSORED":
                censored+=1
            else:
                cancellations.append(record["reason"])
            idx=end+1
            continue
        accepted.append(record)
        portfolio+=record["net_pnl_quote"]
        consecutive_losses=(consecutive_losses+1
                           if record["net_pnl_quote"]<0 else 0)
        # Research circuit breaker: prevent runaway repeated experiments.
        if portfolio<=.98*initial or consecutive_losses>=3:
            halted=True
            break
        idx=end+1  # Single sequential spot position: no overlapping trades.
    outcomes=review_paper_outcomes([r["net_pnl_quote"] for r in accepted])
    summary={
        "schema_version":SCHEMA,
        "status":"PERSONAL_WALK_FORWARD_PAPER_ONLY_NOT_VALIDATED",
        "mode":"OBSERVE",
        "algorithm":admitted["algorithm"],
        "instrument":instrument,
        "bar_interval_minutes":interval_minutes,
        "input_observed_bar_count":len(parsed),
        "first_oos_bar_index":split,
        "test_bars_available":len(parsed)-split,
        "evaluated_closed_paper_trades":len(accepted),
        "entry_cancellation_count":len(cancellations),
        "right_censored_paper_trades_not_counted_as_wins":censored,
        "no_signal_or_held_step_count":skipped,
        "research_circuit_breaker_triggered":halted,
        "stop_first_same_bar_assumption":True,
        "entry_delayed_until_after_original_signal_availability":True,
        "market_gaps_can_exceed_planned_stop_risk":True,
        "trades_do_not_overlap":True,
        "fixed_rules_not_reoptimized_on_oos":True,
        "minimum_independent_oos_trades_for_performance_claim":100,
        "performance_tested_on_independent_exchange_fills":False,
        "data_source_issuer_authenticated":False,
        "market_data_licensed_for_resale":False,
        "live_trade_signals_verified_99_percent_accurate":False,
        "sale_of_signals_approved":False,
        "model_auto_training_or_optimization_used":False,
        "leverage_enabled":False,
        "order_execution_authorized":False,
        "wallet_or_exchange_credentials_used":False,
        "database_writes":False,
        "execution_authority":"none",
        "research_scorecard":outcomes,
        "evaluated_source_fingerprint_sha256_change_detection_only":
            admitted["change_detection_digest_only"],
    }
    # This scorecard is on a fixed historical slice; the timing, custody,
    # venue fees/spread and full trade outcomes are not exchange receipts.
    return summary
