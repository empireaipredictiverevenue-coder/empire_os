"""One-shot read-only public Kraken spot candles for founder-private research.

No Kraken API key, account endpoint, order permissions, position or trade.
Historical candles are observed only at FETCH TIME, never backfilled with
fabricated 'first available' timestamps. No rights to resell provider data.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from hashlib import sha256
from math import isfinite
import json
from typing import Any,Callable
from urllib.request import Request,urlopen

from empire_os.predictive_crypto_signal_research import (
    CryptoSignalHold, review_crypto_trade_signal,
)

SCHEMA="empire.predictive_intelligence.crypto_personal_public_ohlcv.v1"
KRAKEN_BASE="https://api.kraken.com/0/public/OHLC"
PERSONAL_MARKETS={
    "BTC/USD": ("XBTUSD", frozenset(("XXBTZUSD","XBTUSD"))),
    "ETH/USD": ("ETHUSD", frozenset(("XETHZUSD","ETHUSD"))),
}
BAR_INTERVALS={60,240}
MAX_FETCH_BYTES=800_000


def read_personal_public_spot(
    *,
    instrument: str = "BTC/USD",
    interval_minutes:int = 60,
    now:datetime|None=None,
    fetch:Callable[...,Any]|None=None,
)->dict:
    if type(instrument) is not str or instrument not in PERSONAL_MARKETS:
        raise CryptoSignalHold("unsupported founder-private market")
    if type(interval_minutes) is not int or interval_minutes not in BAR_INTERVALS:
        raise CryptoSignalHold("unsupported research candle interval")
    stamp=now or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise CryptoSignalHold("UTC request time must be timezone aware")
    stamp=stamp.astimezone(timezone.utc)
    requested_pair, allowed_response_keys=PERSONAL_MARKETS[instrument]
    endpoint=f"{KRAKEN_BASE}?pair={requested_pair}&interval={interval_minutes}"
    if fetch is None:
        fetch=urlopen
    try:
        response=fetch(Request(endpoint,headers={
            "Accept":"application/json",
            "User-Agent":"EmpireOS-FounderPrivateResearch/1.0",
        }),timeout=8)
        with response:
            raw=response.read(MAX_FETCH_BYTES+1)
        if len(raw)>MAX_FETCH_BYTES or not raw:
            raise CryptoSignalHold("bounded original market response required")
        data=json.loads(raw.decode("utf-8"))
    except CryptoSignalHold:
        raise
    except Exception:
        raise CryptoSignalHold("public market source unavailable") from None
    if (type(data) is not dict or data.get("error")!=[]
            or type(data.get("result")) is not dict):
        raise CryptoSignalHold("unexpected venue response")
    result=data["result"]
    keys=[k for k in result if k!="last"]
    if (len(keys)!=1 or keys[0] not in allowed_response_keys
            or type(result[keys[0]]) is not list):
        raise CryptoSignalHold("unexpected market pair response")
    source_bars=result[keys[0]]
    if not 36<=len(source_bars)<=721:
        raise CryptoSignalHold("insufficient or excessive OHLC history")
    # Kraken explicitly includes one uncommitted final time frame.
    completed=source_bars[:-1]
    bars=[]
    interval=timedelta(minutes=interval_minutes)
    last=None
    for candle in completed:
        if (type(candle) not in (list,tuple) or len(candle)!=8
                or type(candle[0]) is not int):
            raise CryptoSignalHold("invalid original venue OHLC shape")
        origin=datetime.fromtimestamp(candle[0],timezone.utc)
        end=origin+interval
        if last is not None and end<=last:
            raise CryptoSignalHold("original venue candle chronology invalid")
        last=end
        if end>stamp-timedelta(seconds=5):
            raise CryptoSignalHold("uncommitted market candle included")
        try:
            prices=[float(candle[n]) for n in (1,2,3,4,6)]
        except (ValueError,TypeError):
            raise CryptoSignalHold("unreadable venue OHLC field") from None
        if any(not isfinite(v) or v<0 or v>1e12 for v in prices):
            raise CryptoSignalHold("non-finite venue market values")
        opening,high,low,closing,volume=prices
        if (opening<=0 or closing<=0 or low<=0 or
                not low<=min(opening,closing)<=max(opening,closing)<=high):
            raise CryptoSignalHold("inconsistent original spot OHLC")
        integrity=sha256(json.dumps(
            [instrument,interval_minutes,*candle],
            separators=(",",":"),ensure_ascii=True,
        ).encode("utf-8")).hexdigest()
        bars.append({
            "closed_at":end.isoformat(),
            "first_available_at":stamp.isoformat(),
            "ingested_at":stamp.isoformat(),
            "open":opening,"high":high,"low":low,"close":closing,
            "volume":volume,"evidence_sha256":integrity,
        })
    # These are *originally fetched now*; not independently signed exchange
    # receipts. Historical backtests must not fake earlier ingestion.
    if len(bars)<35:
        raise CryptoSignalHold("not enough completed market bars")
    signal=review_crypto_trade_signal(
        bars,as_of=stamp.isoformat(),instrument=instrument,
        interval_minutes=interval_minutes,equity_quote=10000,
        spread_bps=10,fee_bps_round_trip=20,
        conservative_stop_slippage_bps=35,
    )
    return {
        "schema_version":SCHEMA,
        "status":"PERSONAL_SPOT_SNAPSHOT_RESEARCH_ONLY",
        "mode":"OBSERVE",
        "source_endpoint_name":"KRAKEN_PUBLIC_SPOT_OHLC",
        "instrument":instrument,
        "bar_interval_minutes":interval_minutes,
        "candle_count":len(bars),
        "uncommitted_last_bar_dropped":True,
        "historical_candle_availability_pre_fetch_not_authenticated":True,
        "retrieved_at_utc":stamp.isoformat(),
        "last_completed_candle_closed_at":bars[-1]["closed_at"],
        "market_payload_digest_change_detection_only":sha256(raw).hexdigest(),
        "quote_equity_is_illustrative_not_owner_account_value":True,
        "spread_fee_and_slippage_are_modeled_not_venue_actuals":True,
        "source_terms_commercial_redistribution_approved":False,
        "no_exchanges_connected_to_owner_account":True,
        "paper_signal":signal,
        "personal_paper_only":True,
        "trade_signal_accuracy_proven":False,
        "commercial_subscriptions_approved":False,
        "live_orders_or_wallet_access":False,
        "database_writes":False,
        "execution_authority":"none",
    }
