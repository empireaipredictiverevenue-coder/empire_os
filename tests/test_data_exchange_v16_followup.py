"""V16 approved manual follow-up gate; mocks only, no EmpireDB writes."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import json
import pytest

from empire_os.data_exchange_observation_custody import (
    CustodyIntegrityError, plan_custody_append,
)
from scripts import operate_data_exchange_v16_followup as op
from test_data_exchange_temporal_quality import NOW, snap


def first(hrs_ago=26):
    return plan_custody_append(
        snap(NOW-timedelta(hours=hrs_ago)),
        previous=None, assessed_at=NOW)["row"]


def test_minimum_24_hour_gate_is_strict():
    for n in (1, 23, 23.999):
        report=op.due_check([first(n)],now=NOW)
        assert report["eligible"] is False
        assert report["status"]=="HOLD_MINIMUM_24H_SEPARATION"
        assert report["database_writes"] is False
    report=op.due_check([first(24)],now=NOW)
    assert report["eligible"] is True
    assert report["status"]=="ELIGIBLE_FOR_EXPLICIT_ONE_SHOT_CAPTURE"
    assert report["seconds_until_eligible"]==0


def test_expired_gap_is_not_eligible_for_blind_append():
    report=op.due_check([first(24*89)],now=NOW+timedelta(days=3))
    assert report["status"]=="HOLD_MAX_90_DAY_GAP"
    assert report["eligible"] is False


def test_no_region_wide_coverage_claim_for_three_pilot_records():
    report=op.due_check([first()],now=NOW)
    assert report["canonical_previous_sequence"]==0
    assert report["customer_delivery_enabled"] is False
    assert report["payment_execution"] is False
    assert report["execution_authority"]=="NONE"


def test_forged_head_fails_before_network():
    row=first()
    row["chain_sha256"]="f"*64
    with pytest.raises(CustodyIntegrityError):
        op.due_check([row],now=NOW)


def test_incomplete_sample_cannot_schedule_capture():
    partial=snap(NOW-timedelta(hours=26),ids={"1739547"})
    row=plan_custody_append(partial,previous=None,assessed_at=NOW)["row"]
    with pytest.raises(CustodyIntegrityError,match="scope incomplete"):
        op.due_check([row],now=NOW)


def test_manual_readiness_does_not_fetch_or_append():
    class Fake:
        def read_window(self):
            return [first()]
        def append_once(self,*a,**kw):
            raise AssertionError("no writes in default mode")
    def no_fetch(*a,**kw):
        raise AssertionError("no fresh GET in default mode")
    result=op.run_once(reader=Fake(),now=NOW,append=False,fetch_snapshot=no_fetch)
    assert result["eligible"] is True
    assert result["database_writes"] is False


def test_one_gated_second_observation_uses_canonical_append_only():
    previous=first(30)
    latest_at=NOW-timedelta(seconds=2)
    new_snap=snap(latest_at)
    following=plan_custody_append(new_snap,previous=previous,assessed_at=NOW)["row"]
    calls=[]
    class Fake:
        def read_window(self):
            calls.append("READ")
            return [previous] if calls.count("READ")==1 else [previous,following]
        def append_once(self,item,*,now):
            assert item==new_snap
            calls.append("APPEND")
            return {"mode":"CANONICAL_APPEND_COMMITTED",
                    "database_writes":True,"sequence":1,
                    "head_chain_sha256":following["chain_sha256"]}
    fetched=[]
    def capture(*,now):
        fetched.append(now)
        return new_snap
    result=op.run_once(reader=Fake(),now=NOW,append=True,fetch_snapshot=capture)
    assert result["status"]=="SECOND_CANONICAL_OBSERVATION_COMMITTED"
    assert result["canonical_head_sequence"]==1
    assert result["source_record_count"]==3
    assert result["observed_source_field_changes"]==0
    assert result["board_status"]=="NO_OBSERVED_FIELD_CHANGES"
    assert result["database_writes"] is True
    assert result["customer_delivery_enabled"] is False
    assert calls==["READ","APPEND","READ"]
    assert fetched==[NOW]


def test_expired_due_check_does_not_fetch_or_insert():
    class Fake:
        def read_window(self):
            return [first(3)]
        def append_once(self,*a,**kw):
            raise AssertionError("not due")
    def no_fetch(*a,**kw):
        raise AssertionError("not due")
    r=op.run_once(reader=Fake(),now=NOW,append=True,fetch_snapshot=no_fetch)
    assert r["eligible"] is False
    assert r["database_writes"] is False


def test_missing_approval_or_protected_dsn_returns_hold(monkeypatch,capsys):
    monkeypatch.delenv(op.DSN_ENV,raising=False)
    assert op.main([])==2
    r=json.loads(capsys.readouterr().out)
    assert r["status"]=="HOLD"
    assert r["database_writes"] is False
    monkeypatch.setenv(op.DSN_ENV,"opaque-test-dsn")
    assert op.main(["--append"])==2
    r=json.loads(capsys.readouterr().out)
    assert r["database_writes"] is False


def test_only_prior_custody_gate_and_existing_fetcher_used():
    from pathlib import Path
    content=Path(op.__file__).read_text()
    assert "systemctl" not in content
    assert "cron" not in content
    assert "send_email" not in content
    assert "supabase" not in content
    assert "CREATE TABLE" not in content
    assert "appends_allowed" not in content
    assert "CUSTOMER_EXPORT" not in content
