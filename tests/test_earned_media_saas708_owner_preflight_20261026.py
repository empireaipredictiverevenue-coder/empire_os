"""Independent owner gate: exact founder-approved 708 payload is not publish authority."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from empire_os.earned_media_saas708_owner_preflight import (
    FOUNDER_PATH, FOUNDER_SHA, SOURCE_SHA, CANDIDATE_SHA,
    read_json, review, verify_protected_site_backup, ROOT_ARCHIVE,
)
from empire_os.earned_media_saas700_reconciliation import LIVE, DESTINATION
from empire_os.earned_media_saas_rebased_release import read_index, index_digest
from scripts.review_earned_media_saas708_original_owner_20261026 import main


def test_exact_founder_approved_release_has_two_external_holds(capsys):
    assert main(["--preflight"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "RELEASE_HELD_MISSING_INDEPENDENT_OWNER_EVIDENCE"
    assert result["gates"]["live_700_and_candidate_708_exact_sha256"] is True
    assert result["gates"]["private_candidate_scope_preserved"] is True
    assert result["gates"]["explicit_708_founder_review_approval"] is True
    assert result["gates"]["isolated_real_browser_cta_consent"] is True
    assert result["gates"]["original_owner_root_700_member_backup"] is False
    assert result["gates"]["independent_original_astra_owner_release_approval"] is False
    assert result["publisher_invoked"] is False
    assert result["website_modified"] is False


def test_current_700_and_708_are_pinned_and_unmodified():
    original = read_index(LIVE)
    staged = read_index(DESTINATION)
    assert len(original) == 700 and index_digest(original) == SOURCE_SHA
    assert len(staged) == 708 and index_digest(staged) == CANDIDATE_SHA
    assert sha256(FOUNDER_PATH.read_bytes()).hexdigest() == FOUNDER_SHA


def test_superseded_670_founder_approval_is_rejected():
    old = Path("/srv/empire_os/docs/website/release_candidates/SAAS670_FOUNDER_EXACT_APPROVAL_20261026.json")
    result = review(founder_path=old)
    assert result["gates"]["explicit_708_founder_review_approval"] is False
    assert result["gates"]["independent_original_astra_owner_release_approval"] is False


def test_tampered_founder_708_approval_is_rejected(tmp_path):
    bogus = tmp_path/"founder.json"
    contents = json.loads(FOUNDER_PATH.read_text())
    contents["immediate_publication_authorized"] = True
    bogus.write_text(json.dumps(contents))
    result = review(founder_path=bogus)
    assert result["gates"]["explicit_708_founder_review_approval"] is False


def test_symlinked_founder_approval_is_rejected(tmp_path):
    symlink = tmp_path/"founder.json"
    symlink.symlink_to(FOUNDER_PATH)
    result = review(founder_path=symlink)
    assert result["gates"]["explicit_708_founder_review_approval"] is False


def test_absent_private_browser_receipt_cannot_pass(tmp_path):
    result = review(browser_path=tmp_path/"missing.json")
    assert result["gates"]["isolated_real_browser_cta_consent"] is False


def test_unprotected_or_missing_backup_never_counts(tmp_path):
    root = tmp_path/"unprotected"
    root.mkdir()
    archive = root/"backup.tar.gz"
    archive.write_bytes(b"not a root-owned verified archive")
    assert verify_protected_site_backup(
        read_index(LIVE),root=root,archive=archive
    ) == (False, None)


def test_root_owned_receipt_does_not_count_without_backup(tmp_path):
    owner = tmp_path/"owner.json"
    owner.write_text(json.dumps({
        "schema_version":"empire.website.saas708_astra_owner_authority.v1",
        "independent_exact_scope_release_authorized":True,
    }))
    result=review(owner_path=owner)
    assert result["gates"]["independent_original_astra_owner_release_approval"] is False


def test_preflight_cli_never_accepts_apply(capsys):
    with pytest.raises(SystemExit):
        main(["--apply"])
    assert "--preflight" in capsys.readouterr().err


def test_protected_json_requires_root_owner_when_flagged(tmp_path):
    test = tmp_path/"claim.json"
    test.write_text('{"review": true}')
    assert read_json(test,protected=True) is None


def test_older_original_672_publisher_stays_incompatible():
    r=review()
    assert r["original_old_publisher_672_not_applicable"] is True
    assert r["production_publication_authorized_by_preflight"] is False
