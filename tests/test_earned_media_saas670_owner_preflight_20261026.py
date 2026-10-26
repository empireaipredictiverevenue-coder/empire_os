"""No legacy 672-file approval may unlock the 670-file ASTRA owner release."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from empire_os.earned_media_saas670_owner_preflight import (
    FOUNDER_SCHEMA, review, LIVE, CANDIDATE, FOUNDER,
)
from scripts.review_earned_media_saas670_owner_authority_20261026 import main


def test_existing_real_release_held_exact_missing_evidence(capsys):
    assert main(["--preflight"]) == 2
    x=json.loads(capsys.readouterr().out)
    assert x["status"] == "RELEASE_HELD_MISSING_INDEPENDENT_AUTHORITY"
    assert x["site_baseline_files"] == 662
    assert x["rebased_candidate_files"] == 670
    assert x["gates"]["exact_source_and_670_candidate_pinned"] is True
    assert x["gates"]["isolated_browser_hydration_and_consent_passed"] is True
    assert x["gates"]["current_scope_exact_two_route_eight_assets"] is True
    # Explicit approval was received for the immutable 670-file hash on 26 Oct.
    assert x["gates"]["revised_exact_payload_founder_approval_verified"] is True
    assert x["gates"]["root_owned_662_member_backup_verified"] is False
    assert x["gates"]["original_astra_owner_exact_receipt_verified"] is False
    assert x["publication_performed"] is False
    assert x["root_publisher_invoked"] is False
    assert x["publication_authorized_by_this_tool"] is False
    assert x["old_672_candidate_approval_not_reused"] is True


def test_wrong_old_672_file_approval_rejected(tmp_path):
    old=Path("/srv/empire_os/docs/website/release_candidates/SAAS_EVIDENCE_FOUNDER_APPROVAL_20261025.json")
    assert old.is_file()
    result=review(founder_path=old,verify_root_backup=False)
    assert result["gates"]["revised_exact_payload_founder_approval_verified"] is False
    assert result["gates"]["original_astra_owner_exact_receipt_verified"] is False


def test_invented_unbound_founder_approval_rejected(tmp_path):
    p=tmp_path/"founder.json"
    p.write_text(json.dumps({
        "schema_version":FOUNDER_SCHEMA,
        "decision":"FOUNDER_APPROVES_EXACT_REVISED_662_TO_670_PAYLOAD_FOR_ASTRA_REVIEW",
        "candidate_file_count":670,
        "source_live_inventory_sha256":"0"*64,
        "candidate_inventory_sha256":"1"*64,
        "original_website_release_owner":"EXISTING_ASTRA_WEBSITE_RELEASE_OWNER",
        "publication_performed":False,
    }))
    result=review(founder_path=p,verify_root_backup=False)
    assert result["gates"]["revised_exact_payload_founder_approval_verified"] is False


def test_unreadable_or_symlinked_founder_document_cannot_unlock(tmp_path):
    missing=tmp_path/"missing.json"
    x=review(founder_path=missing,verify_root_backup=False)
    assert not x["gates"]["revised_exact_payload_founder_approval_verified"]
    symlink=tmp_path/"founder.json"
    symlink.symlink_to(
        "/srv/empire_os/docs/website/release_candidates/SAAS_EVIDENCE_FOUNDER_APPROVAL_20261025.json"
    )
    x=review(founder_path=symlink,verify_root_backup=False)
    assert not x["gates"]["revised_exact_payload_founder_approval_verified"]


def test_changed_original_site_receipt_fails_closed(tmp_path):
    original=Path("/home/ubuntu/empire_releases/earned_media_saas_union_20261026/private_candidate_receipt.json")
    doc=json.loads(original.read_text())
    doc["source_live_inventory_sha256"]="a"*64
    invalid=tmp_path/"receipt.json"
    invalid.write_text(json.dumps(doc))
    x=review(receipt_path=invalid,verify_root_backup=False)
    assert x["gates"]["exact_source_and_670_candidate_pinned"] is False
    assert x["status"] == "RELEASE_HELD_MISSING_INDEPENDENT_AUTHORITY"


def test_missing_browser_report_is_not_a_verified_browser(tmp_path):
    x=review(browser_path=tmp_path/"absent.json",verify_root_backup=False)
    assert x["gates"]["isolated_browser_hydration_and_consent_passed"] is False
    assert x["publication_authorized_by_this_tool"] is False


def test_preflight_disallows_non_readonly_modes():
    with pytest.raises(SystemExit):
        main(["--apply"])
