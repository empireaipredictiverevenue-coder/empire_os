"""Synthetic safety checks: never run live publication from unit tests."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import os

import pytest

from scripts import owner_publish_saas_evidence_20261025 as owner
from scripts import review_saas_evidence_release_candidate_20261025 as qa


def test_real_founder_approval_matches_frozen_manifest_and_remains_held():
    obj=owner.verify_founder()
    assert obj["founder_approval_for_exact_candidate"] is True
    assert obj["publication_authorized_now"] is False
    summary=owner.read_only_preflight()
    assert summary["founder_exact_scope_approved"] is True
    assert summary["independent_website_owner_approval_verified"] is False
    assert summary["protected_root_backup_verified"] is False
    assert summary["publication_performed"] is False
    assert summary["replaced_files"]==sorted(qa.REPLACE)


def test_without_root_no_owner_backup_can_be_accepted(monkeypatch):
    monkeypatch.setattr(owner.os,"geteuid",lambda:1000)
    with pytest.raises(owner.SiteReleaseHeld, match="ROOT"):
        owner.verify_owner_and_backup(
            founder_sha="0"*64,expected={"test":"abc"})


@pytest.fixture()
def trees(tmp_path):
    live=tmp_path/"live"
    stage=tmp_path/"stage"
    live.mkdir()
    stage.mkdir()
    preserved={"index.html":b"DO_NOT_TOUCH_OTHER_OWNER"}
    existing={
        "predictive-revenue.html":b"OLD HTML",
        "predictive-revenue.txt":b"OLD RSC",
        **preserved,
    }
    for name,value in existing.items():
        (live/name).write_bytes(value)
        (stage/name).write_bytes(
            b"NEW HTML" if name=="predictive-revenue.html" else
            b"NEW RSC" if name=="predictive-revenue.txt" else value)
    for i in range(10):
        path=stage/f"_next/static/chunks/test-{i}.js"
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(f"PINNED_{i}".encode())
    return live,stage,qa.read_index(live),qa.read_index(stage)


def test_ten_asset_two_page_exact_transaction_only_changes_scope(trees):
    live,stage,baseline,final=trees
    def probe():
        assert qa.read_index(live)==final
    r=owner.transaction(live,stage,baseline,final,on_applied=probe)
    assert r["files_replaced"]==2
    assert r["new_hashed_static_assets"]==10
    assert r["other_existing_files_changed"]==0
    assert qa.read_index(live)==final
    assert (live/"index.html").read_bytes()==b"DO_NOT_TOUCH_OTHER_OWNER"


def test_failed_browser_probe_rolls_back_all_payloads_and_new_assets(trees):
    live,stage,baseline,final=trees
    def failure():
        assert qa.read_index(live)==final
        raise RuntimeError("INJECTED_RELEASE_FAILURE")
    with pytest.raises(RuntimeError,match="INJECTED_RELEASE_FAILURE"):
        owner.transaction(live,stage,baseline,final,on_applied=failure)
    assert qa.read_index(live)==baseline
    assert (live/"index.html").read_bytes()==b"DO_NOT_TOUCH_OTHER_OWNER"


def test_unreviewed_preexisting_asset_rejects_before_writes(trees):
    live,stage,baseline,final=trees
    new=next(k for k in final if k not in baseline)
    target=live/new
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(b"UNRELATED_ASSET")
    prior=qa.read_index(live)
    with pytest.raises(owner.SiteReleaseHeld,match="NEW_STATIC_ASSET"):
        owner.transaction(live,stage,baseline,final,on_applied=lambda:None)
    assert qa.read_index(live)==prior


def test_unrelated_modified_existing_page_is_rejected(trees):
    live,stage,baseline,final=trees
    final["index.html"]=sha256(b"UNAPPROVED_UPDATE").hexdigest()
    with pytest.raises(owner.SiteReleaseHeld,match="SCOPE_CHANGED"):
        owner.transaction(live,stage,baseline,final,on_applied=lambda:None)
    assert qa.read_index(live)==baseline
