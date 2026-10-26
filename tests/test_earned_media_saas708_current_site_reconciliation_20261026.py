"""New website owner's 700-file baseline, 708-file private SaaS release."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from empire_os.earned_media_saas700_reconciliation import (
    DESTINATION,LIVE,PREVIOUS,RECEIPT,verify,prepare,
    LIVE_700_PIN,OLD_670_PIN,
)
from empire_os.earned_media_saas_rebased_release import read_index,index_digest,LINK
from empire_os.earned_media_saas_private_backup_audit import inspect_private_backup
from scripts.rehearse_earned_media_saas708_private_restore_20261026 import (
    ARCHIVE,rehearse,
)


def test_old_670_is_unchanged_but_current_site_is_now_700():
    assert len(read_index(LIVE))==700
    assert index_digest(read_index(LIVE))==LIVE_700_PIN
    assert len(read_index(PREVIOUS))==670
    assert index_digest(read_index(PREVIOUS))==OLD_670_PIN


def test_only_two_routes_and_eight_assets_changed_from_current_700():
    result=verify()
    assert result["status"]=="PRIVATE_708_FILE_REBASE_INTEGRITY_PASS_REVIEW_ONLY"
    assert result["original_live_file_count"]==700
    assert result["new_candidate_file_count"]==708
    assert result["new_static_assets_count"]==8
    assert result["other_original_files_preserved_exactly"]==698
    assert result["site_publication_performed"] is False


def test_original_recent_seo_commercial_page_bytes_unchanged():
    live=read_index(LIVE)
    proposed=read_index(DESTINATION)
    assert proposed["commercial.html"]==live["commercial.html"]
    assert proposed["commercial.txt"]==live["commercial.txt"]
    assert proposed["predictive-revenue.html"]!=live["predictive-revenue.html"]
    assert proposed["predictive-revenue.txt"]!=live["predictive-revenue.txt"]
    assert LINK in (DESTINATION/"predictive-revenue.html").read_text()
    assert LINK not in (LIVE/"predictive-revenue.html").read_text()
    assert all(proposed[k]==live[k] for k in live if k not in {
        "predictive-revenue.html","predictive-revenue.txt"
    })


def test_new_708_requires_new_explicit_approval_not_old_670_receipt():
    receipt=json.loads(RECEIPT.read_text())
    assert receipt["old_founder_approval_does_not_cover_new_candidate"] is True
    assert receipt["new_founder_approval_verified"] is False
    assert receipt["site_publication_authorized"] is False
    assert receipt["site_publication_performed"] is False
    assert receipt["root_backup_verified"] is False
    assert receipt["payment_or_outbound"] is False


def test_no_overwrite_existing_private_candidate():
    with pytest.raises(Exception,match="ALREADY_EXISTS_NO_REPLACE"):
        prepare()


def test_user_owned_new_700_backup_all_bytes_verified():
    result=inspect_private_backup(ARCHIVE,LIVE,expected_count=700)
    assert result["verified_regular_files"]==700
    assert result["live_site_inventory_sha256"]==LIVE_700_PIN
    assert result["status"]=="PRIVATE_700_ARCHIVE_MEMBER_HASHES_EXACT"
    assert result["private_user_backup_only"] is True
    assert result["independent_root_protected_backup_verified"] is False


def test_forward_to_708_and_exact_700_recovery_no_production_write():
    result=rehearse()
    assert result["status"]=="PASS_PRIVATE_700_TO_708_AND_EXACT_700_RECOVERY"
    assert result["original_file_count"]==700
    assert result["candidate_file_count"]==708
    assert result["restored_file_count"]==700
    assert result["new_immutable_assets"]==8
    assert result["founder_new_708_payload_approved"] is False
    assert result["production_site_modified"] is False
