"""Public Kraken read-only spot OHLC: completed only, no original backfill."""
from __future__ import annotations

from datetime import timedelta,timezone
from io import BytesIO
import json
import pytest

from empire_os.predictive_crypto_kraken_personal import (
    read_personal_public_spot,
)
from empire_os.predictive_crypto_signal_research import CryptoSignalHold
from tests.test_predictive_crypto_signal_research import START


NOW=START+timedelta(hours=39,minutes=5)


def feed(*,poison=None,count=38):
    records=[]
    for i in range(count+1):
        open_at=int((START+timedelta(hours=i)).timestamp())
        px=100+i*.30
        record=[open_at,str(px-.14),str(px+.13),
                str(px-.42),str(px),"100.0",
                "160" if i==count-1 else "100",100]
        records.append(record)
    if poison=="invalid":
        records[3][3]="200.0"
    elif poison=="future_completed":
        records[-2][0]=int((NOW+timedelta(hours=2)).timestamp())
    elif poison=="duplicate":
        records[10][0]=records[9][0]
    elif poison=="not_list":
        records[9]={"open":1}
    elif poison=="short":
        records=records[:10]
    if poison=="venue_error":
        return {"error":["EQuery:fail"],"result":{}}
    if poison=="unexpected_pair":
        return {"error":[],"result":{"XXBTZUSD":records,"OTHER":records,"last":123}}
    return {"error":[],"result":{"XXBTZUSD":records,"last":123}}


def fake(data):
    capture=[]
    def fetch(request,*,timeout):
        capture.append((request.full_url,timeout,dict(request.headers)))
        return BytesIO(json.dumps(data).encode())
    return fetch,capture


def test_live_style_public_fetch_drops_forming_bar_and_preserves_custody():
    fetch,calls=fake(feed())
    report=read_personal_public_spot(
        instrument="BTC/USD",interval_minutes=60,now=NOW,fetch=fetch,
    )
    assert len(calls)==1
    assert calls[0][0]=="https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60"
    assert calls[0][1]==8
    assert report["source_endpoint_name"]=="KRAKEN_PUBLIC_SPOT_OHLC"
    assert report["candle_count"]==38
    assert report["uncommitted_last_bar_dropped"] is True
    assert report["historical_candle_availability_pre_fetch_not_authenticated"] is True
    assert report["source_terms_commercial_redistribution_approved"] is False
    assert report["no_exchanges_connected_to_owner_account"] is True
    assert report["paper_signal"]["real_trade_execution_authorized"] is False
    assert report["paper_signal"]["ninety_nine_percent_accuracy_proven"] is False
    assert report["personal_paper_only"] is True
    assert report["live_orders_or_wallet_access"] is False
    assert report["database_writes"] is False
    assert report["execution_authority"]=="none"


@pytest.mark.parametrize("attack",[
    "invalid","future_completed","duplicate","not_list",
    "short","venue_error","unexpected_pair",
])
def test_bad_source_cannot_invent_personal_signals(attack):
    fetch,_=fake(feed(poison=attack))
    with pytest.raises(CryptoSignalHold):
        read_personal_public_spot(
            instrument="BTC/USD",interval_minutes=60,now=NOW,fetch=fetch,
        )


@pytest.mark.parametrize("instrument,interval",[
    ("DOGE/USDT",60),("BTC/USD",61),("ETH/USD",True),
    ("BTC/USD",0),("ETH/GBP",60),
])
def test_arbitrary_market_not_queried(instrument,interval):
    def fail(*a,**kw):
        raise AssertionError("must not fetch")
    with pytest.raises(CryptoSignalHold):
        read_personal_public_spot(
            instrument=instrument,interval_minutes=interval,now=NOW,fetch=fail,
        )


def test_fetch_exception_is_redacted_not_a_trade():
    def offline(*args,**kwargs):raise RuntimeError("token=private")
    with pytest.raises(CryptoSignalHold) as exc:
        read_personal_public_spot(now=NOW,fetch=offline)
    assert "private" not in str(exc.value)


def test_latest_received_candles_are_not_backdated_into_oos(monkeypatch):
    import empire_os.predictive_crypto_kraken_personal as mod
    observed=[]
    def fake_signal(bars,**kwargs):
        observed.extend(bars)
        return {
            "real_trade_execution_authorized":False,
            "ninety_nine_percent_accuracy_proven":False,
        }
    monkeypatch.setattr(mod,"review_crypto_trade_signal",fake_signal)
    fetch,_=fake(feed())
    report=read_personal_public_spot(now=NOW,fetch=fetch)
    assert len(observed)==report["candle_count"]
    assert all(r["first_available_at"]==NOW.isoformat() for r in observed)
    assert all(r["ingested_at"]==NOW.isoformat() for r in observed)
    assert observed[-1]["closed_at"]<NOW.isoformat()
