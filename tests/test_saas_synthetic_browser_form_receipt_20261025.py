"""Integrity tests for real-browser *synthetic* SaaS form acceptance receipt.

Evidence of a locally mocked browser response must never be interpreted as
a real buyer, website deployment, CRM source event, or commercial authority.
"""
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path("/srv/empire_os")
PICKUP=ROOT/"docs/website/release_candidates/SAAS_EVIDENCE_ASTRA_OWNER_PICKUP_20261025.json"
RECEIPT=ROOT/"docs/website/release_candidates/SAAS_EVIDENCE_SYNTHETIC_FORM_ACCEPTANCE_20261025.json"
CANDIDATE=ROOT/"docs/website/release_candidates/SAAS_EVIDENCE_PAIRED_UNION_20261025.json"


def test_synthetic_intercept_never_promotes_a_customer_or_live_release():
    evidence=json.loads(RECEIPT.read_text())
    assert evidence["schema_version"]=="empire.website.saas_browser_form_synthetic_acceptance.v1"
    assert evidence["status"]=="ISOLATED_SAAS_FORM_CONSENT_RETRY_PASS"
    assert evidence["source_is_localhost"] is True
    assert evidence["consent_required_before_submit"] is True
    assert evidence["initial_unapproved_posts"]==0
    assert evidence["intercepted_posts"]==2
    assert evidence["retry_idempotency_reused"] is True
    assert evidence["accidental_duplicate_after_success_blocked"] is True
    assert evidence["unrelated_or_external_post_requests"]==0
    for flag in ("existing_customer_data_written","original_backend_invoked",
                 "founder_crm_mutated","authentic_buyer_observed",
                 "website_owner_release_authorized","candidate_published",
                 "new_sender_or_crm_authority"):
        assert evidence[flag] is False,flag
    assert evidence["original_reviewed_candidate_inventory_sha256"]==json.loads(
        CANDIDATE.read_text())["candidate_inventory_sha256"]


def test_receipt_script_digest_matches_and_astra_pickup_is_still_review_only():
    evidence=json.loads(RECEIPT.read_text())
    script=ROOT/evidence["qa_script_path"]
    assert script.is_file()
    assert sha256(script.read_bytes()).hexdigest()==evidence["qa_script_sha256"]
    pickup=json.loads(PICKUP.read_text())
    ref=pickup["pinned_evidence"]["synthetic_browser_form"]
    assert ROOT/ref["path"]==RECEIPT
    assert sha256(RECEIPT.read_bytes()).hexdigest()==ref["sha256"]
    assert pickup["automatic_astra_department_dispatch_submitted"] is False
    assert pickup["publication_authorized_now"] is False
    assert pickup["publication_performed"] is False
