"""Empire Regime-Risk Signals read-only private research CLI.

Never connects to exchanges or modifies a wallet. Original source integrity,
data licences and paper-trade accuracy remain unverified.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

from empire_os.predictive_crypto_signal_research import (
    SCHEMA,CryptoSignalHold,review_crypto_trade_signal,
)

MAX_BYTES=1_000_000
CONTRACT="empire.predictive_intelligence.crypto_completed_candles_intake.v1"


def capabilities() -> dict:
    return {
        "schema_version":SCHEMA,"algorithm":"EMPIRE_REGIME_RISK_SIGNALS_V1",
        "status":"PRIVATE_OBSERVE_PAPER_SIGNAL_RESEARCH_AVAILABLE",
        "research_sides":["LONG_RESEARCH_ONLY","NO_TRADE"],
        "risk_before_entry":True,
        "mandatory_stop_loss":True,
        "maximum_nominal_cash_risk_fraction_per_candidate":.005,
        "stop_fill_guaranteed":False,
        "included_research":["ema12_ema26_regime","10bar_breakout",
          "20bar_volume_confirmation","atr14_stop","spread_fees_slippage_gates",
          "take_profit_2r","gap_and_stop_first_paper_stress"],
        "source_data_connected":False,
        "live_crypto_signal_accuracy_measured":False,
        "99_percent_accuracy_promise":False,
        "strategy_out_of_sample_validated":False,
        "subscriber_distribution_approved":False,
        "UK_crypto_promotion_compliance_verified":False,
        "exchanges_traded":False,"private_key_accepted":False,
        "live_orders_or_margin_authorized":False,
        "database_writes":False,"execution_authority":"none",
    }


def template() -> dict:
    return {
        "schema_version":CONTRACT,
        "as_of":"<UTC source decision time ISO8601>",
        "instrument":"BTC/USDT",
        "interval_minutes":60,
        "research_assumptions":{
            "equity_quote":10000,
            "spread_bps":10,"fee_bps_round_trip":20,
            "conservative_stop_slippage_bps":35,
        },
        "candles":[],
        "exchange_source_authenticated":False,
        "exchange_licensing_approved":False,
        "customer_investment_advice_authorized":False,
    }


def _read(path:Path) -> dict:
    if (path.is_symlink() or not path.is_file()
            or not 0<path.stat().st_size<=MAX_BYTES):
        raise CryptoSignalHold("untrusted private candle file")
    try:
        doc=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,UnicodeError,ValueError):
        raise CryptoSignalHold("original crypto research envelope unavailable") from None
    if type(doc) is not dict or set(doc)!={
        "schema_version","as_of","instrument","interval_minutes",
        "research_assumptions","candles",
    } or doc["schema_version"]!=CONTRACT:
        raise CryptoSignalHold("unapproved market data source structure")
    assumptions=doc["research_assumptions"]
    if type(assumptions) is not dict or set(assumptions)!={
        "equity_quote","spread_bps","fee_bps_round_trip",
        "conservative_stop_slippage_bps",
    }:
        raise CryptoSignalHold("unbounded market risk assumption")
    return review_crypto_trade_signal(
        doc["candles"],as_of=doc["as_of"],instrument=doc["instrument"],
        interval_minutes=doc["interval_minutes"],**assumptions,
    )


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",required=True,action="store_true")
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--template",action="store_true")
    mode.add_argument("--series-file")
    args=parser.parse_args(argv)
    try:
        if args.template:
            result=template()
        elif args.series_file:
            result={
                **_read(Path(args.series_file)),
                "owner_supplied_file_is_verified_market_feed":False,
                "production_signal_dispatch_authorized":False,
            }
        else:
            result=capabilities()
        returncode=0
    except (CryptoSignalHold,OSError,ValueError,TypeError,KeyError):
        result={
            "schema_version":SCHEMA,
            "status":"CRYPTO_RESEARCH_INPUT_HELD",
            "mode":"OBSERVE","market_data_rights_verified":False,
            "real_trade_execution_authorized":False,
            "database_writes":False,"execution_authority":"none",
        }
        returncode=2
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return returncode


if __name__=="__main__":
    raise SystemExit(main())
