"""V16 one-shot operator always read-only, with fixed source IDs."""
import json
from datetime import datetime, timedelta, timezone
import pytest

from scripts import review_data_exchange_v16_temporal as cli
from tests.test_data_exchange_temporal_quality import NOW, custody, snap


def test_protected_dedicated_dsn_missing_holds(monkeypatch,capsys):
    monkeypatch.delenv("EMPIRE_DATA_EXCHANGE_CUSTODIAN_DSN",raising=False)
    assert cli.main([])==2
    report=json.loads(capsys.readouterr().out)
    assert report["status"]=="HOLD_UNVERIFIED_SOURCE_OR_CUSTODY"
    assert report["database_writes"] is False
    assert report["customer_delivery_enabled"] is False


def test_read_only_operator_returns_true_genesis_hold(monkeypatch):
    from tests.test_data_exchange_temporal_quality import custody
    class FakeStore:
        def __init__(self,dsn):
            assert dsn=="opaque-ephemeral-test"
        def read_window(self):
            return custody((NOW-timedelta(hours=1),"non-permissioned"))
    monkeypatch.setattr(cli,"EmpireDBConstructionCustody",FakeStore)
    report=cli.run_review(now=NOW,dsn="opaque-ephemeral-test",recheck=False)
    assert report["status"]=="HOLD_REVIEW_REQUIRED"
    assert report["observed_source_field_changes"]==0
    assert report["canonical_observation_count_in_window"]==1
    assert report["production_writes"] is False


def test_bounded_recheck_uses_existing_canonical_reader_only(monkeypatch):
    class FakeStore:
        def __init__(self,dsn):
            assert dsn=="opaque-ephemeral-test"
        def read_window(self):
            return custody((NOW-timedelta(hours=50),"non-permissioned"),
                           (NOW-timedelta(hours=25),"permissioned"))
    monkeypatch.setattr(cli,"EmpireDBConstructionCustody",FakeStore)
    called=[]
    def fetch(*,now):
        called.append(now)
        return snap(now-timedelta(seconds=5),status="permissioned")
    result=cli.run_review(now=NOW,dsn="opaque-ephemeral-test",
                          recheck=True,fetch_snapshot=fetch)
    assert result["same_source_recheck"]=="REPEAT_SAME_SOURCE_MATCH"
    assert result["observed_source_field_changes"]==3
    assert result["customer_delivery_enabled"] is False
    assert len(called)==1


def test_source_only_cannot_be_combined_with_recheck(capsys):
    assert cli.main(["--source-only","--recheck-official"])==2
    report=json.loads(capsys.readouterr().out)
    assert report["status"]=="HOLD_UNVERIFIED_SOURCE_OR_CUSTODY"
    assert report["database_writes"] is False


def test_source_only_does_not_open_custody_db(monkeypatch,capsys):
    def never_db(*a,**kw):
        raise AssertionError("must never connect to database")
    monkeypatch.setattr(cli,"EmpireDBConstructionCustody",never_db)
    monkeypatch.setattr(cli,"capture",
        lambda *,now:{"records":[{"record_id":ident} for ident in sorted(cli.PILOT_IDS)]})
    assert cli.main(["--source-only"])==0
    report=json.loads(capsys.readouterr().out)
    assert report["pilot_entity_count"]==3
    assert report["canonical_history_read"] is False
    assert report["canonical_observation_written"] is False


def test_source_only_rejects_partial_official_sample(monkeypatch,capsys):
    monkeypatch.setattr(cli,"capture",
        lambda *,now:{"records":[{"record_id":"1739547"}]})
    assert cli.main(["--source-only"])==2
    report=json.loads(capsys.readouterr().out)
    assert report["status"]=="HOLD_UNVERIFIED_SOURCE_OR_CUSTODY"


def test_errors_never_leak_source_data_or_db_password(monkeypatch,capsys):
    class FakeStore:
        def __init__(self,dsn):
            raise RuntimeError("password=very-secret PRIVATE@example.invalid")
    monkeypatch.setattr(cli,"EmpireDBConstructionCustody",FakeStore)
    monkeypatch.setenv("EMPIRE_DATA_EXCHANGE_CUSTODIAN_DSN","password=very-secret")
    assert cli.main([])==2
    raw=capsys.readouterr().out
    assert "very-secret" not in raw
    assert "PRIVATE" not in raw
    assert json.loads(raw)["error_type"]=="RuntimeError"


def test_no_automatic_write_approval_or_checkout_activation():
    from pathlib import Path
    body=Path(cli.__file__).read_text()
    assert ".append_once(" not in body
    assert "systemctl" not in body
    assert "pg_dump" not in body
    assert "send_email" not in body
    assert "supabase" not in body
