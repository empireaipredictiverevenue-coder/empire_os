"""Crypto research CLI: never executes, sells signals or asserts market proof."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from datetime import datetime,timedelta,timezone
import json
import pytest

import scripts.review_predictive_crypto_signals_20261022 as cli
from tests.test_predictive_crypto_signal_research import bars, PARAMS,START

def intake():
    return {
        "schema_version":cli.CONTRACT,
        "as_of":(START+timedelta(hours=38,minutes=5)).isoformat(),
        "instrument":PARAMS["instrument"],
        "interval_minutes":PARAMS["interval_minutes"],
        "research_assumptions":{k:PARAMS[k] for k in (
            "equity_quote","spread_bps","fee_bps_round_trip",
            "conservative_stop_slippage_bps",
        )},
        "candles":bars(),
    }


def test_status_advertises_only_research_never_99_percent_accuracy(capsys):
    assert cli.main(["--read-only"])==0
    d=json.loads(capsys.readouterr().out)
    assert d["mandatory_stop_loss"] is True
    assert d["99_percent_accuracy_promise"] is False
    assert d["source_data_connected"] is False
    assert d["live_crypto_signal_accuracy_measured"] is False
    assert d["UK_crypto_promotion_compliance_verified"] is False
    assert d["live_orders_or_margin_authorized"] is False
    assert d["database_writes"] is False
    assert d["execution_authority"]=="none"


def test_readonly_research_from_original_ohlcv_file(tmp_path,capsys):
    p=tmp_path/"candles.json"
    p.write_text(json.dumps(intake()))
    assert cli.main(["--read-only","--series-file",str(p)])==0
    d=json.loads(capsys.readouterr().out)
    assert d["status"]=="PAPER_SIGNAL_CANDIDATE_NOT_VALIDATED"
    assert d["paper_stop_loss"]<d["paper_entry"]
    assert d["market_data_rights_verified"] is False
    assert d["owner_supplied_file_is_verified_market_feed"] is False
    assert d["source_issuer_authenticated"] is False
    assert d["production_signal_dispatch_authorized"] is False


def test_template_empty_and_non_trading(capsys):
    assert cli.main(["--read-only","--template"])==0
    d=json.loads(capsys.readouterr().out)
    assert d["candles"]==[]
    assert d["exchange_source_authenticated"] is False
    assert d["customer_investment_advice_authorized"] is False


@pytest.mark.parametrize("attack",["symlink","oversize","fake_authority","nan","unknown_structure"])
def test_file_input_failure_redacted_and_execution_denied(tmp_path,capsys,attack):
    p=tmp_path/"market.json"
    doc=intake()
    if attack=="symlink":
        q=tmp_path/"original.json"
        q.write_text(json.dumps(doc))
        p.symlink_to(q)
    elif attack=="oversize":
        p.write_text("{"+"a"*1_000_001+"}")
    else:
        if attack=="fake_authority":
            doc["exchange_source_authenticated"]=True
        elif attack=="nan":
            doc["candles"][4]["high"]=float("nan")
        else:
            doc.pop("research_assumptions")
        p.write_text(json.dumps(doc))
    assert cli.main(["--read-only","--series-file",str(p)])==2
    d=json.loads(capsys.readouterr().out)
    assert d["status"]=="CRYPTO_RESEARCH_INPUT_HELD"
    assert d["real_trade_execution_authorized"] is False
    assert d["database_writes"] is False


def test_pinned_private_release_includes_reader_and_no_live_permission():
    content=(Path(__file__).resolve().parents[1]/
             "scripts/prepare_predictive_readonly_release_20261020.sh").read_text()
    for fragment in (
        "empire_os/predictive_crypto_signal_research.py",
        "empire_os/predictive_crypto_stop_loss_simulator.py",
        "scripts/review_predictive_crypto_signals_20261022.py",
        "crypto|crypto-template|crypto-series",
        '"$command" == "crypto-series"',
        '"$command" == "crypto-template"',
        '"$command" == "crypto"',
    ):
        assert fragment in content
