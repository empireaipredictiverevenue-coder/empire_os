"""Founder report stays private, source-linked and immutable across reruns."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

from empire_os.data_brokerage_roofing_sample import (
    build_roofing_competitor_sample,render_roofing_sample_markdown,
)
from scripts import preview_roofing_competitor_gap_sample as runner


def test_preview_does_not_write_or_send(tmp_path,capsys):
    result=runner.main(["--read-only"],root=tmp_path)
    assert result==0
    d=json.loads(capsys.readouterr().out)
    assert d["status"]=="FOUNDER_REVIEW_SAMPLE_PREPARED"
    assert d["private_report_materialized"] is False
    assert d["live_backlinks_verified"]==0
    assert d["buyer_or_payment_verified"] is False
    assert d["paid_api_calls"]==0
    assert d["empiredb_writes"] is False
    assert d["outbound_sent"] is False
    assert not list(tmp_path.iterdir())


def test_private_output_restricted_to_canonical_runtime(tmp_path,capsys):
    result=runner.main(["--read-only","--write-private"],root=tmp_path)
    assert result==2
    d=json.loads(capsys.readouterr().out)
    assert d["status"]=="HOLD"
    assert not list(tmp_path.iterdir())


def test_private_report_and_receipt_hash_match_idempotently(tmp_path,monkeypatch):
    monkeypatch.setattr(runner,"ROOT",tmp_path)
    result=runner.main(["--read-only","--write-private"],root=tmp_path)
    assert result==0
    path=tmp_path/runner.REPORT
    receipt_path=tmp_path/runner.RECEIPT
    assert path.exists() and receipt_path.exists()
    assert path.stat().st_mode & 0o777==0o600
    assert receipt_path.stat().st_mode & 0o777==0o600
    text=path.read_text()
    receipt=json.loads(receipt_path.read_text())
    assert receipt["report_sha256"]==__import__("hashlib").sha256(
        text.encode("utf8")).hexdigest()
    assert receipt["source_evidence_sha256"]==build_roofing_competitor_sample()[
        "internal_evidence_sha256"]
    assert receipt["c2pa_signature_issued"] is False
    assert receipt["founder_independent_ownership_proven"] is False
    assert receipt["outbound_sent"] is False
    before=path.read_bytes()
    assert runner.main(["--read-only","--write-private"],root=tmp_path)==0
    assert path.read_bytes()==before


def test_private_report_tampering_refuses_rewrite(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(runner,"ROOT",tmp_path)
    assert runner.main(["--read-only","--write-private"],root=tmp_path)==0
    capsys.readouterr()
    path=tmp_path/runner.REPORT
    path.write_text("not an evidence-backed report")
    result=runner.main(["--read-only","--write-private"],root=tmp_path)
    assert result==2
    assert json.loads(capsys.readouterr().out)["status"]=="HOLD"
    assert path.read_text()=="not an evidence-backed report"


def test_missing_authority_or_wrong_file_symlink_refused(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(runner,"ROOT",tmp_path)
    assert runner.main(["--write-private"],root=tmp_path)==2
    capsys.readouterr()
    target=tmp_path/runner.REPORT
    target.parent.mkdir(parents=True)
    dummy=tmp_path/"dummy.md"
    dummy.write_text("pretend output")
    target.symlink_to(dummy)
    assert runner.main(["--read-only","--write-private"],root=tmp_path)==2
    assert dummy.read_text()=="pretend output"
