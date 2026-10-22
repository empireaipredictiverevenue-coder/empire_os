"""Paper trade research scorecard; never independently certifies 99% accuracy.

No prediction model, trader authentication, external outcome receipts or real
funds are inferred. Won trades can coexist with negative expectancy.
"""
from __future__ import annotations

from math import sqrt,isfinite
from statistics import mean
from typing import Any

SCHEMA="empire.predictive_intelligence.crypto_signal_paper_scorecard.v1"


class CryptoScorecardHold(ValueError):
    pass


def review_paper_outcomes(outcomes: Any) -> dict:
    if type(outcomes) not in (list,tuple) or len(outcomes)>10000:
        raise CryptoScorecardHold("bounded independent trade evidence needed")
    pnl=[]
    for x in outcomes:
        if type(x) not in (float,int) or not isfinite(x) or abs(x)>1e9:
            raise CryptoScorecardHold("finite net profit or loss in same quote unit required")
        pnl.append(float(x))
    n=len(pnl)
    won=sum(x>0 for x in pnl)
    lost=sum(x<0 for x in pnl)
    win_fraction=won/n if n else None
    # 95% Wilson lower confidence bound for wins (NOT a calibrated
    # forecast or proof of independent observations).
    lower=None
    if n:
        z=1.959963984540054
        p=win_fraction
        lower=max(0.0,(p+z*z/(2*n)-z*sqrt(
            p*(1-p)/n+z*z/(4*n*n)
        ))/(1+z*z/n))
    equity=0.0;peak=0.0;worst_drawdown=0.0
    streak=0;max_loss_streak=0
    for x in pnl:
        equity+=x
        peak=max(equity,peak)
        worst_drawdown=max(worst_drawdown,peak-equity)
        if x<0:
            streak+=1;max_loss_streak=max(max_loss_streak,streak)
        else:
            streak=0
    gains=sum(x for x in pnl if x>0)
    losses=-sum(x for x in pnl if x<0)
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"UNAUTHENTICATED_PAPER_PERFORMANCE_NOT_CERTIFIED",
        "paper_outcome_count":n,
        "paper_positive_count":won,
        "paper_negative_count":lost,
        "paper_flat_count":n-won-lost,
        "paper_positive_rate":round(win_fraction,7) if n else None,
        "paper_positive_rate_wilson_lower_95":round(lower,7) if lower is not None else None,
        "paper_mean_net_quote_pnl":round(mean(pnl),7) if pnl else None,
        "paper_total_net_quote_pnl":round(equity,7),
        "paper_max_quote_drawdown":round(worst_drawdown,7),
        "paper_longest_losing_streak":max_loss_streak,
        "paper_profit_factor":round(gains/losses,7) if losses>0 else None,
        "paper_outcomes_authenticated_from_exchange":False,
        "research_outcomes_confirmed_out_of_sample":False,
        "multiple_strategy_tests_adjusted":False,
        "live_order_fill_slippage_independently_measured":False,
        "ninety_nine_percent_accuracy_validated":False,
        "future_99_percent_accuracy_promised":False,
        "approved_signal_subscription_product":False,
        "execution_authority":"none","database_writes":False,
    }
