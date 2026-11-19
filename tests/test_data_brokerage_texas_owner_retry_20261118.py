"""Unit checks: Texas recovery stays inside original brokerage owner cooldown."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
from unittest.mock import patch

from empire_os import data_brokerage_texas_retry as retry
from scripts.run_data_brokerage_source_mining import run_due_brokerage_source_mining

NOW=datetime(2026,11,18,10,0,tzinfo=timezone.utc)
SOURCE_AT=datetime(2026,11,17,22,30,tzinfo=timezone.utc)
PREVIOUS={
    "observed_at":SOURCE_AT.isoformat(),
    "next_eligible_at":datetime(2026,11,18,10,30,tzinfo=timezone.utc).isoformat(),
    "us_construction_official_research":{"status":"OFFICIAL_US_CONSTRUCTION_AGGREGATE_RESEARCH_ONLY"},
}
def test_no_new_scheduler_or_network_before_source_retry_window(tmp_path,monkeypatch):
    monkeypatch.setattr(retry,"ROOT",tmp_path.resolve())
    seen=[]
    def probe(*args,**kwargs):
        seen.append(1)
        return {}
    r=retry.retry_in_original_owner(tmp_path,now=SOURCE_AT+timedelta(minutes=5),
                                    previous=PREVIOUS,texas_runner=probe)
    assert r["status"]=="NO_RETRY_OUTSIDE_COOLDOWN_WINDOW"
    assert not seen and not (tmp_path/retry.STATE).exists()

def test_failed_source_attempt_stays_held_rate_limited(tmp_path,monkeypatch):
    monkeypatch.setattr(retry,"ROOT",tmp_path.resolve())
    calls=[]
    def source(*args,**kwargs):
        calls.append(kwargs)
        return {"status":"DALLAS_OFFICIAL_SOURCE_HOLD",
                "source_receipts_committed":False,"outreach_sent":False}
    with patch("empire_os.data_brokerage_texas_agent.load_state",return_value=None):
        a=retry.retry_in_original_owner(tmp_path,now=NOW,previous=PREVIOUS,
                                        texas_runner=source)
        b=retry.retry_in_original_owner(tmp_path,now=NOW+timedelta(minutes=1),
                                        previous=PREVIOUS,texas_runner=source)
    assert a["status"]=="RETRY_SOURCE_HELD"
    assert a["reason_code"]=="DALLAS_OFFICIAL_SOURCE_HOLD"
    assert b["status"]=="TEXAS_RETRY_COOLDOWN"
    assert len(calls)==1
    assert calls[0]["trigger"]=="ORIGINAL_BROKERAGE_COOLDOWN_RETRY"
    marker=retry._existing(tmp_path)
    assert marker["status"]=="RETRY_SOURCE_HELD"
    assert (tmp_path/retry.STATE).stat().st_mode & 0o077==0

def test_retry_at_most_once_per_hour_after_failure(tmp_path,monkeypatch):
    monkeypatch.setattr(retry,"ROOT",tmp_path.resolve())
    calls=[]
    def held(*args,**kwargs):
        calls.append(kwargs)
        return {"status":"DALLAS_OFFICIAL_SOURCE_HOLD",
                "source_receipts_committed":False,"outreach_sent":False}
    with patch("empire_os.data_brokerage_texas_agent.load_state",return_value=None):
        retry.retry_in_original_owner(tmp_path,now=SOURCE_AT+timedelta(minutes=16),
                                      previous=PREVIOUS,texas_runner=held)
        again=retry.retry_in_original_owner(
            tmp_path,now=SOURCE_AT+timedelta(minutes=77),
            previous=PREVIOUS,texas_runner=held)
    assert again["status"]=="RETRY_SOURCE_HELD"
    assert len(calls)==2

def test_owner_cooldown_propagates_retry_status_without_main_network(tmp_path,monkeypatch):
    root=tmp_path.resolve()
    monkeypatch.setattr(retry,"ROOT",root)
    with patch("scripts.run_data_brokerage_source_mining.load_verified_cycle",
               return_value=PREVIOUS), patch(
        "scripts.run_data_brokerage_source_mining.due_source_cycle",
               return_value=False), patch(
        "scripts.run_data_brokerage_source_mining.build_brokerage_source_mining"
    ) as main_source:
        result=run_due_brokerage_source_mining(root,now=NOW,persist=True)
    assert result["status"]=="SOURCE_MINING_COOLDOWN_REUSED"
    assert result["texas_original_brokerage_retry"]["status"]=="NONCANONICAL_NO_RETRY"
    assert result["provider_requests"]==result["mining_requests"]==0
    main_source.assert_not_called()

def test_retry_receipt_refuses_tamper_or_invalid_filesystem(tmp_path,monkeypatch):
    monkeypatch.setattr(retry,"ROOT",tmp_path.resolve())
    with patch("empire_os.data_brokerage_texas_agent.load_state",return_value=None):
        retry.retry_in_original_owner(
            tmp_path,now=NOW,previous=PREVIOUS,
            texas_runner=lambda *args,**kwargs:{"status":"DALLAS_OFFICIAL_SOURCE_HOLD"})
    file=tmp_path/retry.STATE
    record=json.loads(file.read_text())
    record["outreach_sent"]=True
    file.write_text(json.dumps(record))
    assert retry._existing(tmp_path) is None
    file.unlink()
    file.symlink_to(tmp_path/"unrelated_file")
    assert retry._existing(tmp_path) is None

def test_current_texas_snapshot_prevents_second_source_read(tmp_path,monkeypatch):
    monkeypatch.setattr(retry,"ROOT",tmp_path.resolve())
    recent={"observed_at":SOURCE_AT.isoformat()}
    with patch("empire_os.data_brokerage_texas_agent.load_state",return_value=recent):
        r=retry.retry_in_original_owner(
            tmp_path,now=NOW,previous=PREVIOUS,
            texas_runner=lambda *args,**kwargs:1/0)
    assert r["status"]=="TEXAS_RESEARCH_CURRENT_WITH_ORIGINAL_OWNER"

def test_no_retry_after_general_cycle_due(tmp_path,monkeypatch):
    monkeypatch.setattr(retry,"ROOT",tmp_path.resolve())
    r=retry.retry_in_original_owner(
        tmp_path,now=NOW+timedelta(hours=1),
        previous=PREVIOUS,texas_runner=lambda *args,**kwargs:1/0)
    assert r["status"]=="NO_RETRY_OUTSIDE_COOLDOWN_WINDOW"

def test_successful_owner_retry_commits_and_suppresses_repeat(tmp_path,monkeypatch):
    monkeypatch.setattr(retry,"ROOT",tmp_path.resolve())
    observed={"observed_at":NOW.isoformat(),
              "execution_trigger":"ORIGINAL_BROKERAGE_COOLDOWN_RETRY"}
    with patch("empire_os.data_brokerage_texas_agent.load_state",
               side_effect=[None,observed,observed]) as reader:
        result=retry.retry_in_original_owner(
            tmp_path,now=NOW,previous=PREVIOUS,
            texas_runner=lambda *args,**kwargs:{
                "status":"TEXAS_AGENT_DALLAS_AND_FORT_WORTH_RESEARCH_VERIFIED",
                "source_receipts_committed":True,"outreach_sent":False,
            })
        repeat=retry.retry_in_original_owner(
            tmp_path,now=NOW+timedelta(minutes=4),previous=PREVIOUS,
            texas_runner=lambda *args,**kwargs:1/0)
    assert result["status"]=="RETRY_CONFIRMED"
    assert result["source_receipts_committed"] is True
    assert repeat["status"]=="TEXAS_RESEARCH_CURRENT_WITH_ORIGINAL_OWNER"
    assert retry._existing(tmp_path)["status"]=="RETRY_CONFIRMED"
    assert reader.call_count==3
