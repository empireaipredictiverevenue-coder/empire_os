"""V17 scientific review reuses existing root-only V16 inspector."""
from datetime import timedelta
import json
from pathlib import Path

import pytest

from scripts import inspect_data_exchange_v16_live as inspector
from tests.test_data_exchange_temporal_quality import NOW, custody


def store_for(rows):
    class Reader:
        def __init__(self,dsn):
            assert dsn == "opaque-fixture"
        def read_window(self):
            return rows
        def append_once(self,*a,**kw):
            raise AssertionError("read-only science must not append")
    return Reader


def test_live_inspector_single_genesis_scientific_hold(monkeypatch):
    rows=custody((NOW-timedelta(hours=2),"non-permissioned"))
    monkeypatch.setattr(inspector,"RELEASED_GENESIS_SHA256",rows[0]["chain_sha256"])
    result=inspector.inspect_live(
        now=NOW, dsn="opaque-fixture", scientific_review=True,
        store_factory=store_for(rows))
    science=result["scientific_evidence_review"]
    assert science["status"]=="HOLD_INSUFFICIENT_SCIENTIFIC_EVIDENCE"
    assert science["existing_agi_review_status"]=="NOT_RUN_REQUIRES_TWO_GENUINE_OBSERVATIONS"
    assert science["canonical_head_sha256"]==result["canonical_head_sha256"]
    assert science["v14_observed_field_changes_in_window"]==0
    assert result["database_writes"] is False


def test_two_true_observations_launch_existing_readonly_agi(monkeypatch):
    rows=custody((NOW-timedelta(hours=51),"non-permissioned"),
                 (NOW-timedelta(hours=25),"permissioned"))
    monkeypatch.setattr(inspector,"RELEASED_GENESIS_SHA256",rows[0]["chain_sha256"])
    report=inspector.inspect_live(
        now=NOW,dsn="opaque-fixture",scientific_review=True,
        store_factory=store_for(rows))
    science=report["scientific_evidence_review"]
    assert science["existing_agi_review_status"]=="EXISTING_AGI_EVIDENCE_REVIEW_OBSERVE_ONLY"
    assert science["existing_agi_research_workstreams"]
    assert science["v14_observed_field_changes_in_window"]==report["v14_observed_field_change_count"]==3
    assert science["claims"]["commercial_buyer_intent"]=="NOT_VERIFIED"
    assert science["model_inference_performed"] is False
    assert report["customer_delivery_enabled"] is False


def test_existing_inspector_output_unchanged_by_default(monkeypatch):
    rows=custody((NOW-timedelta(hours=1),"non-permissioned"))
    monkeypatch.setattr(inspector,"RELEASED_GENESIS_SHA256",rows[0]["chain_sha256"])
    report=inspector.inspect_live(
        now=NOW,dsn="opaque-fixture",store_factory=store_for(rows))
    assert "scientific_evidence_review" not in report
    assert report["status"]=="CANONICAL_CUSTODY_READONLY_VERIFIED"


def test_scientific_cross_check_disallows_fake_verification(monkeypatch):
    rows=custody((NOW-timedelta(hours=1),"non-permissioned"))
    monkeypatch.setattr(inspector,"RELEASED_GENESIS_SHA256",rows[0]["chain_sha256"])
    monkeypatch.setattr(inspector,"build_scientific_custody_review",
                        lambda *a,**kw:{
                            "canonical_head_sha256":"f"*64,
                            "v14_observed_field_changes_in_window":0,
                            "customer_delivery_enabled":False,
                            "production_writes":False})
    with pytest.raises(inspector.InspectionHold,match="SCIENTIFIC_EVIDENCE_AND_CUSTODY_MISMATCH"):
        inspector.inspect_live(
            now=NOW,dsn="opaque-fixture",scientific_review=True,
            store_factory=store_for(rows))


def test_science_flag_cannot_bypass_root(monkeypatch,capsys):
    monkeypatch.setattr(inspector.os,"geteuid",lambda:1000)
    monkeypatch.setattr(inspector,"protected_dsn",
                        lambda:(_ for _ in ()).throw(AssertionError("unprivileged secret read")))
    assert inspector.main(["--read-only","--scientific-review"])==2
    report=json.loads(capsys.readouterr().out)
    assert report["reason_code"]=="AUTHORISED_ROOT_READ_ACCESS_REQUIRED"
    assert report["database_writes"] is False


def test_root_science_mode_never_exposes_secret(monkeypatch,capsys):
    monkeypatch.setattr(inspector.os,"geteuid",lambda:0)
    monkeypatch.setattr(inspector,"CANONICAL_ROOT",Path.cwd())
    monkeypatch.setattr(inspector,"protected_dsn",lambda:"secretfixture")
    monkeypatch.setattr(inspector,"inspect_live",
                        lambda **kwargs:(_ for _ in ()).throw(
                            RuntimeError("source-error private@email.invalid password=secretfixture")))
    assert inspector.main(["--read-only","--scientific-review"])==2
    raw=capsys.readouterr().out
    assert "secretfixture" not in raw and "private@" not in raw
    assert json.loads(raw)["status"]=="HOLD"


def test_no_separate_scientific_runtime_or_source_write():
    from pathlib import Path
    source=Path(inspector.__file__).read_text(encoding="utf-8")
    assert '.append_once(' not in source
    assert 'systemctl start' not in source
    assert 'schedule=' not in source
    assert 'send_email(' not in source
