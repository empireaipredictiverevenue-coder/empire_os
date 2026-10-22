"""Private owner CLI: corrected template, conservative OOS, no orders."""
from __future__ import annotations
from datetime import timedelta
import json
from pathlib import Path
import subprocess

import pytest

import scripts.review_predictive_crypto_personal_20261022 as cli
from tests.test_predictive_crypto_signal_research import START,PARAMS,bars


def test_readonly_private_capabilities(capsys):
    assert cli.main(["--read-only","--capabilities"])==0
    x=json.loads(capsys.readouterr().out)
    assert x["algorithm"]=="EMPIRE_REGIME_RISK_SIGNALS_V1"
    assert x["stop_policy"]=="MANDATORY_VOLATILITY_STOP_NOT_GUARANTEED"
    assert x["personal_use_only"] is True
    assert x["historical_market_data_authenticated"] is False
    assert x["ninety_nine_percent_accuracy_verified"] is False
    assert x["commercialization_approved"] is False
    assert x["exchange_orders_authorized"] is False
    assert x["execution_authority"]=="none"


def sample(*,count=38):
    x=cli.template()
    x["as_of"]=(START+timedelta(hours=count,minutes=5)).isoformat()
    x["candles"]=bars(count=count)
    if count>100:
        for i,r in enumerate(x["candles"]):
            r["volume"]=160 if i%8==7 else 100
    return x


def test_original_template_round_trip_and_mandatory_stop(tmp_path,capsys):
    d=sample()
    p=tmp_path/"sample.json"
    p.write_text(json.dumps(d))
    assert cli.main(["--read-only","--paper-file",str(p)])==0
    r=json.loads(capsys.readouterr().out)
    assert r["status"]=="PAPER_SIGNAL_CANDIDATE_NOT_VALIDATED"
    assert r["paper_stop_loss"] < r["paper_entry"] < r["paper_take_profit"]
    assert r["stop_fill_price_guaranteed"] is False
    assert r["personal_research_only"] is True
    assert r["source_exchange_market_data_authenticated"] is False
    assert r["live_exchange_market_orders_authorized"] is False


def test_historical_oos_includes_censored_not_fictitious_winners(tmp_path,capsys):
    d=sample(count=200)
    p=tmp_path/"test.json"
    p.write_text(json.dumps(d))
    assert cli.main(["--read-only","--walkforward-file",str(p)])==0
    r=json.loads(capsys.readouterr().out)
    assert r["schema_version"]=="empire.predictive_intelligence.crypto_personal_paper_walkforward.v1"
    assert r["input_observed_bar_count"]==200
    assert r["first_oos_bar_index"]==140
    assert r["right_censored_paper_trades_not_counted_as_wins"]>=1
    assert r["evaluated_closed_paper_trades"]==0
    assert r["research_scorecard"]["paper_positive_rate"] is None
    assert r["sale_of_signals_approved"] is False
    assert r["performance_tested_on_independent_exchange_fills"] is False
    assert r["wallet_or_exchange_credentials_used"] is False


@pytest.mark.parametrize("bad",["forged", "symlink", "truncated", "future", "unbounded"])
def test_poisoned_or_unsafe_data_fails_closed(tmp_path,capsys,bad):
    d=sample()
    p=tmp_path/"input.json"
    if bad=="forged":
        d["exchange_source_authenticated"]=True
    elif bad=="symlink":
        original=tmp_path/"owned.json"; original.write_text(json.dumps(d))
        p.symlink_to(original)
    elif bad=="truncated":
        d.pop("candles")
    elif bad=="future":
        d["candles"][-1]["ingested_at"]=(START+timedelta(hours=30)).isoformat()
    elif bad=="unbounded":
        p.write_text("{"+'"x":'+ '"' +"A"*1_000_010+'"}')
    if not p.exists() and not p.is_symlink():
        p.write_text(json.dumps(d))
    assert cli.main(["--read-only","--paper-file",str(p)])==2
    report=json.loads(capsys.readouterr().out)
    assert report["status"]=="PERSONAL_CRYPTO_SOURCE_OR_SCIENCE_HELD"
    assert report["exchange_orders_authorized"] is False
    assert report["database_writes"] is False


def test_private_public_snapshot_switches_do_not_enable_exchange_trading(monkeypatch,capsys):
    calls=[]
    def fake(*,instrument,interval_minutes):
        calls.append((instrument,interval_minutes))
        return {
            "schema_version":"empire.predictive_intelligence.crypto_personal_public_ohlcv.v1",
            "status":"PERSONAL_SPOT_SNAPSHOT_RESEARCH_ONLY",
            "paper_signal":{"status":"NO_TRADE"},
            "live_orders_or_wallet_access":False,
            "execution_authority":"none",
        }
    monkeypatch.setattr(cli,"read_personal_public_spot",fake)
    assert cli.main(["--read-only","--public-btc-hourly"])==0
    output=json.loads(capsys.readouterr().out)
    assert output["paper_signal"]["status"]=="NO_TRADE"
    assert output["live_orders_or_wallet_access"] is False
    assert cli.main(["--read-only","--public-eth-hourly"])==0
    capsys.readouterr()
    assert calls==[("BTC/USD",60),("ETH/USD",60)]


def test_private_release_source_contract():
    shell=(Path(__file__).resolve().parents[1]/
           "scripts/prepare_private_crypto_personal_release_20261022.sh")
    raw=shell.read_text()
    assert "REFUSE_DIRTY_PERSONAL_CRYPTO_RELEASE" in raw
    assert "sha256sum --status -c" in raw
    assert "predictive_crypto_paper_walkforward.py" in raw
    assert "predictive_crypto_kraken_personal.py" in raw
    assert "--public-btc-hourly" in raw
    assert "--public-eth-hourly" in raw
    assert "review_predictive_crypto_personal_20261022.py" in raw
    assert "LIVE_ORDERS_AND_PRODUCTION_UNCHANGED=true" in raw
    assert "git -C" in raw and "archive" in raw
    assert all(token not in raw for token in (
        "CREATE ROLE", "curl -X POST", "execute_order",
        "api_key", "exchange.set_leverage",
    ))
    invalid=subprocess.run(
        ["bash","-n",str(shell)],capture_output=True,text=True,timeout=10,
    )
    assert invalid.returncode==0
