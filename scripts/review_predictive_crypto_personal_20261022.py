"""Founder-private spot signal research: paper only, never orders or advice.

Uses existing ERRS signal logic and scorecard. Strict local source envelopes
are research inputs, NOT proof of exchange authenticity or data rights.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from empire_os.predictive_crypto_signal_research import (
    CryptoSignalHold,review_crypto_trade_signal,
)
from empire_os.predictive_crypto_paper_walkforward import (
    SCHEMA,review_crypto_personal_walkforward,
)
from empire_os.predictive_crypto_kraken_personal import (
    read_personal_public_spot,
)

MAX_BYTES=1_000_000
CONTRACT="empire.predictive_intelligence.crypto_completed_candles_intake.v1"

def template()->dict:
    return {
        "schema_version":CONTRACT,
        "as_of":"<original latest completed candle receipt timestamp in UTC>",
        "instrument":"BTC/USDT",
        "interval_minutes":60,
        "research_assumptions":{
            "equity_quote":10000,
            "spread_bps":10,
            "fee_bps_round_trip":20,
            "conservative_stop_slippage_bps":35,
        },
        "candles":[],
        "exchange_source_authenticated":False,
        "exchange_licensing_approved":False,
        "customer_investment_advice_authorized":False,
    }

def _read(path:Path)->dict:
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=MAX_BYTES:
        raise CryptoSignalHold("original research file unavailable")
    try:
        doc=json.loads(path.read_text("utf-8"))
    except (OSError,UnicodeError,ValueError):
        raise CryptoSignalHold("invalid original research file") from None
    if type(doc) is not dict:
        raise CryptoSignalHold("original source envelope missing")
    baseline={
        "schema_version","as_of","instrument","interval_minutes",
        "research_assumptions","candles",
    }
    optional={
        "exchange_source_authenticated","exchange_licensing_approved",
        "customer_investment_advice_authorized",
    }
    if (not baseline.issubset(doc) or not set(doc).issubset(baseline|optional)
            or doc.get("schema_version")!=CONTRACT
            or any(doc[k] is not False for k in optional if k in doc)
            or type(doc["research_assumptions"]) is not dict
            or set(doc["research_assumptions"]) != {
                "equity_quote","spread_bps","fee_bps_round_trip",
                "conservative_stop_slippage_bps"
            }):
        raise CryptoSignalHold("original market data schema invalid")
    return doc

def _private_paper(document:dict, *, replay:bool)->dict:
    scorer=review_crypto_personal_walkforward if replay else review_crypto_trade_signal
    return {
        **scorer(
            document["candles"],
            as_of=document["as_of"],instrument=document["instrument"],
            interval_minutes=document["interval_minutes"],
            **document["research_assumptions"],
        ),
        "personal_research_only":True,
        "source_exchange_market_data_authenticated":False,
        "signal_service_available_to_subscribers":False,
        "financial_promotion_approved":False,
        "live_exchange_market_orders_authorized":False,
    }

def main(argv=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",required=True,action="store_true")
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--capabilities",action="store_true")
    group.add_argument("--template",action="store_true")
    group.add_argument("--paper-file")
    group.add_argument("--walkforward-file")
    group.add_argument("--public-btc-hourly",action="store_true")
    group.add_argument("--public-eth-hourly",action="store_true")
    args=parser.parse_args(argv)
    try:
        if args.template:
            output=template()
        elif args.capabilities:
            output={
                "schema_version":SCHEMA,
                "mode":"OBSERVE",
                "status":"PERSONAL_CRYPTO_STOP_LOSS_PAPER_HARNESS_READY",
                "algorithm":"EMPIRE_REGIME_RISK_SIGNALS_V1",
                "entry_policy":"LONG_SPOT_RESEARCH_ONLY",
                "stop_policy":"MANDATORY_VOLATILITY_STOP_NOT_GUARANTEED",
                "paper_signal_data_source_attached":False,
                "fixed_research_risk_fraction":.005,
                "historical_walkforward_available":True,
                "historical_market_data_authenticated":False,
                "public_spot_snapshot_manual_fetch_available":True,
                "public_spot_snapshot_is_historical_backtest_evidence":False,
                "ninety_nine_percent_accuracy_verified":False,
                "personal_use_only":True,
                "commercialization_approved":False,
                "exchange_orders_authorized":False,
                "database_writes":False,
                "execution_authority":"none",
            }
        elif args.public_btc_hourly or args.public_eth_hourly:
            output=read_personal_public_spot(
                instrument="BTC/USD" if args.public_btc_hourly else "ETH/USD",
                interval_minutes=60,
            )
        else:
            input_path=Path(args.paper_file or args.walkforward_file)
            output=_private_paper(_read(input_path),replay=bool(args.walkforward_file))
        code=0
    except (CryptoSignalHold,ValueError,OSError,TypeError,KeyError):
        output={
            "schema_version":SCHEMA,
            "mode":"OBSERVE",
            "status":"PERSONAL_CRYPTO_SOURCE_OR_SCIENCE_HELD",
            "ninety_nine_percent_accuracy_verified":False,
            "exchange_orders_authorized":False,
            "database_writes":False,
            "execution_authority":"none",
        }
        code=2
    print(json.dumps(output,sort_keys=True,allow_nan=False))
    return code

if __name__=="__main__":
    raise SystemExit(main())
