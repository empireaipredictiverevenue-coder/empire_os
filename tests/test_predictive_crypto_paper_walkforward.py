"""Personal crypto paper signals: causality, stop loss, gaps, paper OOS."""
from __future__ import annotations
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from empire_os.predictive_crypto_paper_walkforward import (
    SCHEMA,_exit_outcome,review_crypto_personal_walkforward,
)
from empire_os.predictive_crypto_signal_research import CryptoSignalHold
from tests.test_predictive_crypto_signal_research import bars,query,START,PARAMS


def data():
    result=bars(count=200)
    for i,b in enumerate(result):
        b["volume"]=160 if i%8==7 else 100
    return result


def evaluate(rows=None, *, params=None):
    return review_crypto_personal_walkforward(
        data() if rows is None else rows,
        as_of=(START+timedelta(hours=200,minutes=5)).isoformat(),
        **(PARAMS if params is None else params),
    )


def test_personal_fixed_algorithm_oos_without_99_percent_claim():
    before=data()
    output=evaluate(before)
    assert before==data()
    assert output["schema_version"]==SCHEMA
    assert output["algorithm"]=="EMPIRE_REGIME_RISK_SIGNALS_V1"
    assert output["input_observed_bar_count"]==200
    assert output["first_oos_bar_index"]==140
    assert output["evaluated_closed_paper_trades"]==0
    assert output["right_censored_paper_trades_not_counted_as_wins"]>=1
    assert output["research_scorecard"]["paper_positive_rate"] is None
    assert output["stop_first_same_bar_assumption"] is True
    assert output["entry_delayed_until_after_original_signal_availability"] is True
    assert output["market_gaps_can_exceed_planned_stop_risk"] is True
    assert output["trades_do_not_overlap"] is True
    assert output["fixed_rules_not_reoptimized_on_oos"] is True
    assert output["minimum_independent_oos_trades_for_performance_claim"]==100
    assert output["research_scorecard"]["ninety_nine_percent_accuracy_validated"] is False
    assert output["research_scorecard"]["research_outcomes_confirmed_out_of_sample"] is False
    for field in (
        "performance_tested_on_independent_exchange_fills",
        "data_source_issuer_authenticated","market_data_licensed_for_resale",
        "live_trade_signals_verified_99_percent_accurate",
        "sale_of_signals_approved","model_auto_training_or_optimization_used",
        "leverage_enabled","order_execution_authorized",
        "wallet_or_exchange_credentials_used","database_writes",
    ):
        assert output[field] is False
    assert output["execution_authority"]=="none"


def test_next_next_open_latency_and_stop_gap_breach():
    plan=query()
    stamp=START+timedelta(hours=38)
    entry=plan["paper_entry"]
    stop=plan["paper_stop_loss"]
    target=plan["paper_take_profit"]
    rows=[
        {"t":stamp+timedelta(hours=i),
         "open":entry,"high":entry*1.0002,
         "low":entry*.9998,"close":entry}
        for i in range(4)
    ]
    rows[3].update(open=stop*.7,high=stop*.72,
                   low=stop*.6,close=stop*.65)
    output,end=_exit_outcome(
        plan=plan,rows=rows,index=0,spread_bps=10,
        fee_bps_round_trip=20,stop_slippage_bps=35,equity=10000,
    )
    assert end==3
    assert output["status"]=="PAPER_STOP_LOSS"
    assert output["budget_exceeded_by_simulated_gap"] is True
    assert output["paper_entry_bar_closed_at"]==rows[2]["t"].isoformat()
    assert output["net_pnl_quote"] < -output["planned_risk_budget_quote"]
    assert output["stop_execution_guaranteed"] is False


def test_ambiguous_bar_prioritizes_stop_even_if_target_hit():
    plan=query()
    t=START+timedelta(hours=38)
    entry=plan["paper_entry"]
    stop=plan["paper_stop_loss"]
    target=plan["paper_take_profit"]
    rows=[{"t":t+timedelta(hours=i),"open":entry,
           "high":entry*1.0001,"low":entry*.9999,"close":entry}
          for i in range(4)]
    rows[2].update(high=target*1.01,low=stop*.99)
    o,_=_exit_outcome(
        plan=plan,rows=rows,index=0,
        spread_bps=10,fee_bps_round_trip=20,
        stop_slippage_bps=35,equity=10000,
    )
    assert o["status"]=="PAPER_STOP_LOSS"
    assert o["intrabar_stop_prioritized_over_target"] is True
    assert o["net_pnl_quote"]<0


def test_still_open_near_test_end_is_right_censored():
    plan=query()
    t=START+timedelta(hours=38)
    entry=plan["paper_entry"]
    rows=[{"t":t+timedelta(hours=i),"open":entry,
           "high":entry*1.0001,"low":entry*.9999,"close":entry}
          for i in range(5)]
    o,_=_exit_outcome(
        plan=plan,rows=rows,index=0,
        spread_bps=10,fee_bps_round_trip=20,
        stop_slippage_bps=35,equity=10000,
    )
    assert o["status"]=="PAPER_RIGHT_CENSORED"
    assert o["net_pnl_quote"] is None


@pytest.mark.parametrize("attack",["missing","late_ingestion","duplicate","future","invalid_fee","fake_instrument"])
def test_invalid_or_incomplete_ohlcv_never_backtested(attack):
    x=data()
    params=dict(PARAMS)
    if attack=="missing":
        x.pop(90)
    elif attack=="late_ingestion":
        x[80]["ingested_at"]=(START+timedelta(hours=205)).isoformat()
    elif attack=="duplicate":
        x[150]["closed_at"]=x[149]["closed_at"]
    elif attack=="future":
        x[185]["ingested_at"]=(START+timedelta(hours=205)).isoformat()
    elif attack=="invalid_fee":
        params["fee_bps_round_trip"]=1000
    else:
        params["instrument"]="@BTCUSD"
    with pytest.raises(CryptoSignalHold):
        evaluate(x,params=params)


def test_no_signal_does_not_invent_win_rate():
    rows=data()
    for x in rows: x["volume"]=100
    r=evaluate(rows)
    assert r["evaluated_closed_paper_trades"]==0
    assert r["research_scorecard"]["paper_positive_rate"] is None
    assert r["research_scorecard"]["ninety_nine_percent_accuracy_validated"] is False
