"""The founder approved only the exact current 670-file ASTRA review candidate."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json

import pytest

from empire_os.earned_media_saas670_owner_preflight import FOUNDER, review
from scripts import record_earned_media_saas670_founder_review_approval_20261026 as record

TRACKED_RECEIPT = (
    Path(__file__).resolve().parents[1] /
    "docs/website/release_candidates/SAAS670_FOUNDER_EXACT_APPROVAL_20261026.json"
)
EXPECTED_RECEIPT_SHA256 = "835643ec77a5170b2906f97db8bcf0ad4f94745e1fa0183d371b86df8ca6e4c7"


def test_actual_founder_receipt_exact_source_equals_tracked_review_copy():
    original = FOUNDER.read_bytes()
    assert TRACKED_RECEIPT.read_bytes() == original
    assert sha256(original).hexdigest() == EXPECTED_RECEIPT_SHA256
    fields = json.loads(original)
    assert fields["founder_direct_quote"] == "yes i approve"
    assert fields["decision"] == record.DECISION
    assert fields["candidate_file_count"] == 670
    assert fields["candidate_inventory_sha256"] == record.APPROVED_CANDIDATE_SHA256
    assert fields["approval_scope"].endswith("THIS_EXACT_CANDIDATE_ONLY")
    assert fields["immediate_publication_authorized"] is False
    assert fields["publication_performed"] is False
    assert fields["independent_astra_owner_approval_verified"] is False
    assert fields["root_protected_rollback_verified"] is False


def test_founder_review_approval_passes_but_no_owner_launch_authority():
    result = review()
    assert result["gates"]["revised_exact_payload_founder_approval_verified"] is True
    assert result["gates"]["exact_source_and_670_candidate_pinned"] is True
    assert result["gates"]["root_owned_662_member_backup_verified"] is False
    assert result["gates"]["original_astra_owner_exact_receipt_verified"] is False
    assert result["publication_authorized_by_this_tool"] is False
    assert result["publication_performed"] is False


def test_recorder_refuses_to_replace_original_approval_receipt():
    before = FOUNDER.read_bytes()
    with pytest.raises(FileExistsError, match="NO_OVERWRITE"):
        record.record_founder_approval()
    assert FOUNDER.read_bytes() == before


def test_recorder_refuses_to_replace_any_unrelated_path(tmp_path):
    existing = tmp_path / "different_owner_receipt.json"
    existing.write_text("do not overwrite")
    with pytest.raises(FileExistsError, match="NO_OVERWRITE"):
        record.record_founder_approval(target=existing)
    assert existing.read_text() == "do not overwrite"


def test_approved_hash_cannot_be_silently_changed(monkeypatch):
    monkeypatch.setattr(
        record, "APPROVED_CANDIDATE_SHA256", "0"*64,
    )
    with pytest.raises(ValueError, match="EXACT_USER_APPROVED_CANDIDATE"):
        record.verified_approval_payload(approved_at_utc="2026-10-26T17:00:00+00:00")
