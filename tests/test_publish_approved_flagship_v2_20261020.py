"""Atomic public flagship V2 switch tests; only disposable directories."""
import json
from pathlib import Path

import pytest

from scripts import publish_approved_flagship_v2_20261020 as launch
from scripts.review_flagship_full_export_union_20261020 import ReleaseHold


def test_atomic_exchange_preserves_previous_directory_with_no_partial_window(tmp_path):
    current = tmp_path / "out"
    new = tmp_path / "next"
    current.mkdir()
    new.mkdir()
    (current/"buy.html").write_text("previous approved website")
    (new/"buy.html").write_text("exact v2 candidate")
    launch._atomic_directory_swap(current,new)
    assert (current/"buy.html").read_text() == "exact v2 candidate"
    assert (new/"buy.html").read_text() == "previous approved website"
    launch._atomic_directory_swap(current,new)
    assert (current/"buy.html").read_text() == "previous approved website"


def test_no_approval_or_wrong_digest_cannot_invoke_deployment(monkeypatch):
    monkeypatch.setattr(launch.os, 'geteuid', lambda: 0)
    with pytest.raises(ReleaseHold, match="FOUNDER_APPROVED_INVENTORY_MISMATCH"):
        launch.publish("not-the-user-approved-hash")


def test_guarded_ready_copy_preserves_candidate_and_unrelated_files(tmp_path, monkeypatch):
    candidate=tmp_path/"sealed"
    ready=tmp_path/"prepared"
    live=tmp_path/"live"
    candidate.mkdir(); live.mkdir()
    (candidate/"buy.html").write_bytes(b"new")
    (live/"buy.html").write_bytes(b"old")
    (live/"customer-note.txt").write_bytes(b"leave intact")
    monkeypatch.setattr(launch,"ORIGINAL",candidate)
    monkeypatch.setattr(launch,"READY",ready)
    monkeypatch.setattr(launch,"ROLLBACK",tmp_path/"rollback")
    monkeypatch.setattr(launch,"RECEIPT",tmp_path/"receipt")
    monkeypatch.setattr(launch.pwd,"getpwnam",lambda _name:type("User",(),{"pw_uid":0,"pw_gid":0})())
    monkeypatch.setattr(launch.os, "chown", lambda *_args: None)
    from scripts.review_flagship_full_export_union_20261020 import _file_index
    original=_file_index(candidate)
    launch._prepare_stage(original)
    assert _file_index(ready)==original
    assert (live/"customer-note.txt").read_bytes()==b"leave intact"
    assert (candidate/"buy.html").read_bytes()==b"new"
    with pytest.raises(ReleaseHold,match="PUBLISH_PREEXISTING_STATE_HOLD"):
        launch._prepare_stage(original)


def test_exact_v2_never_accepts_missing_binary_candidate(monkeypatch, tmp_path):
    monkeypatch.setattr(launch,"ORIGINAL",tmp_path)
    with pytest.raises(ReleaseHold):
        launch._expected_inventory({"static_file_sha256":{}})


def test_no_standalone_cli_without_exact_approval(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        launch.main([])
    monkeypatch.setattr(launch,"publish",lambda arg:{
        "status":"EXACT_APPROVED_V2_WEBSITE_PUBLICATION_VERIFIED",
        "new_public_file_count":632,
        "founder_approved_inventory_sha256":arg,
        "runtime":{"buyer_post_submitted":False},
    })
    assert launch.main([
        "--apply-founder-approved-exact-v2",
        "--expected-inventory-sha256", launch.EXPECTED_INVENTORY,
    ]) == 0
    output=json.loads(capsys.readouterr().out)
    assert output["published_files"]==632
    assert output["runtime"]["buyer_post_submitted"] is False
