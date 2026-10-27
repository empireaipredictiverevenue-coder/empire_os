"""Founder-approved immutable 708-file review package, never publish authority."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts import record_earned_media_saas708_founder_review_approval_20261026 as recorder
from empire_os.earned_media_saas700_reconciliation import verify

TRACKED = Path(__file__).resolve().parents[1] / (
    "docs/website/release_candidates/SAAS708_FOUNDER_EXACT_APPROVAL_20261026.json"
)
RECEIPT_SHA = "9c50507dc469678b2e4f69c57bba035c6ea45c07832acab1d0dd89e7b9c67ee6"


def test_authorized_founder_receipt_is_exact_and_not_root_publish_approval():
    actual = recorder.FILE.read_bytes()
    assert actual == TRACKED.read_bytes()
    assert sha256(actual).hexdigest() == RECEIPT_SHA
    r = json.loads(actual)
    assert r["schema_version"] == recorder.SCHEMA
    assert r["founder_quote"] == "yes i approve"
    assert r["decision"] == recorder.DECISION
    assert r["source_live_inventory_sha256"] == recorder.PINNED_SOURCE_SHA
    assert r["candidate_inventory_sha256"] == recorder.PINNED_CANDIDATE_SHA
    assert r["scope"] == "EXACT_708_FILE_CANDIDATE_FOR_ASTRA_FINAL_REVIEW_ONLY"
    assert r["live_file_count"] == 700 and r["candidate_file_count"] == 708
    assert r["older_670_approval_not_transferred"] is True
    assert r["immediate_publication_authorized"] is False
    assert r["root_protected_rollback_verified"] is False
    assert r["website_owner_independent_signoff_verified"] is False
    assert r["publication_performed"] is False


def test_current_candidate_is_same_one_as_explicitly_approved():
    report = verify()
    assert report["original_index_sha256"] == recorder.PINNED_SOURCE_SHA
    assert report["candidate_index_sha256"] == recorder.PINNED_CANDIDATE_SHA
    assert report["site_publication_authorized"] is False
    assert report["site_publication_performed"] is False


def test_recorder_exclusively_creates_and_refuses_duplicate():
    before = recorder.FILE.read_bytes()
    with pytest.raises(FileExistsError, match="NO_OVERWRITE"):
        recorder.record()
    assert recorder.FILE.read_bytes() == before


def test_stale_or_changed_708_candidate_hash_never_passes(monkeypatch):
    monkeypatch.setattr(recorder, "PINNED_CANDIDATE_SHA", "a"*64)
    with pytest.raises(ValueError, match="EXACT_708_CANDIDATE"):
        recorder.build_receipt(recorded_at_utc="2026-10-26T00:00:00+00:00")


def test_receipt_does_not_fabricate_owner_or_payment_authority():
    r = json.loads(TRACKED.read_text())
    assert r["outbound_or_payment_authorized"] is False
    assert r["crm_writes_authorized"] is False
    assert r["genuine_buyer_enquiry_verified"] is False
    assert r["actual_revenue_verified"] is False
