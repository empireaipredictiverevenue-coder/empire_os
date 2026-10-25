"""First-party original guide and existing consented intake are not revenue."""
from __future__ import annotations

import json
from pathlib import Path
from shutil import copyfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.earned_media_advisory_bridge import GROWTH_ARTICLE, review
from empire_os.earned_media_first_party_conversion import (
    ARTICLE_BRIEF, ARTICLE_DRAFT, PAGE, GUIDE, FRONT_ALLOWLIST,
    BACK_ALLOWLIST, COMMERCIAL_PAGE, CTA, EXPECTED_PATHS,
    review_owned_guide_enquiry,
)
from empire_os.founder_earned_media_api import create_founder_earned_media_router
from tests.test_earned_media_advisory_bridge_20261025 import prepared


REPO = Path(__file__).resolve().parents[1]


def _staged(tmp_path):
    main, pr = prepared(tmp_path)
    for rel in (ARTICLE_BRIEF, ARTICLE_DRAFT, PAGE, GUIDE,
                FRONT_ALLOWLIST, BACK_ALLOWLIST, COMMERCIAL_PAGE):
        dst = main / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        copyfile(REPO / rel, dst)
    return main, pr, review(main, pr_root=pr)


def test_realistic_owned_content_bridge_staged_not_live(tmp_path):
    root, _, packet = _staged(tmp_path)
    result = review_owned_guide_enquiry(packet, repo_root=root)
    assert result["state"] == "STAGED_EXISTING_GUIDE_TO_EXISTING_INTAKE_NOT_LIVE_VERIFIED"
    assert result["reviewed_entry_page"] == "/predictive-revenue"
    assert result["proposed_cta"] == CTA
    assert result["source_code_readiness"] is True
    assert result["founder_site_release_authorized"] is False
    assert result["consented_enquiry_verified"] is False
    assert result["source_click_verified"] is False
    assert result["attributable_enquiries"] is None
    assert result["attributable_revenue"] is None
    assert result["smart_crm_reads"] is False
    assert result["message_sent"] is False
    assert result["publication_executed"] is False
    assert result["payment_executed"] is False
    assert result["article_publication_state"] == (
        "SEPARATE_AI_READINESS_ARTICLE_DRAFT_NOT_AUTHORIZED"
    )
    assert "/insights/revenue-opportunity-assessment" not in EXPECTED_PATHS


def test_any_browser_backend_allowlist_drift_holds(tmp_path):
    root, pr, packet = _staged(tmp_path)
    p = root / FRONT_ALLOWLIST
    p.write_text(p.read_text().replace(
        '  "/industries/property",', '  "/industries/property", "/admin",'))
    assert review_owned_guide_enquiry(packet, repo_root=root)[
        "reason_code"] == "BROWSER_BACKEND_ENTRY_ALLOWLIST_DRIFT"


def test_backend_allowlist_widening_holds(tmp_path):
    root, _, packet = _staged(tmp_path)
    p = root / BACK_ALLOWLIST
    p.write_text(p.read_text().replace(
        '    "/industries/property",', '    "/industries/property", "/admin",'))
    assert review_owned_guide_enquiry(packet, repo_root=root)[
        "reason_code"] == "BROWSER_BACKEND_ENTRY_ALLOWLIST_DRIFT"


@pytest.mark.parametrize("target,old,new", [
    (GUIDE, 'href={ownedRevenueGuideProposalHref()}', 'href="/external"'),
    (COMMERCIAL_PAGE, 'contact_consent: consent', 'contact_consent: true'),
    (COMMERCIAL_PAGE, 'reuseCommercialInterestAttempt(', 'reuseUnverifiedAttempt('),
    (BACK_ALLOWLIST, '"organic_search_attributed": False', '"organic_search_attributed": True'),
])
def test_tampered_guide_or_consent_controls_holds(tmp_path, target, old, new):
    root, _, packet = _staged(tmp_path)
    p = root / target
    assert old in p.read_text()
    p.write_text(p.read_text().replace(old, new))
    assert review_owned_guide_enquiry(packet, repo_root=root)[
        "reason_code"] == "OWNED_GUIDE_OR_CONSENT_CAPTURE_UNVERIFIED"


def test_original_editorial_draft_not_automatically_published(tmp_path):
    root, pr, packet = _staged(tmp_path)
    p = root / ARTICLE_BRIEF
    obj = json.loads(p.read_text())
    obj["publication_authorized"] = True
    p.write_text(json.dumps(obj))
    assert review_owned_guide_enquiry(packet, repo_root=root)[
        "reason_code"] == "ARTICLE_DRAFT_PUBLICATION_AUTHORITY_UNVERIFIED"
    p = root / ARTICLE_BRIEF
    obj["publication_authorized"] = False
    p.write_text(json.dumps(obj))
    p = root / ARTICLE_DRAFT
    p.write_text(p.read_text().replace("INTERNAL EDITORIAL NOTES — NOT PUBLIC COPY", ""))
    new_packet = review(root, pr_root=pr)
    assert review_owned_guide_enquiry(new_packet, repo_root=root)[
        "reason_code"] == "ARTICLE_DRAFT_PUBLICATION_AUTHORITY_UNVERIFIED"


def test_stale_packet_hash_cannot_attach_changed_article(tmp_path):
    root, _, packet = _staged(tmp_path)
    p = root / GROWTH_ARTICLE
    p.write_text(p.read_text() + "\nmodified after owner review")
    assert review_owned_guide_enquiry(packet, repo_root=root)[
        "reason_code"] == "ARTICLE_DRAFT_PUBLICATION_AUTHORITY_UNVERIFIED"


def test_reject_missing_and_symlinked_site_source(tmp_path):
    root, _, packet = _staged(tmp_path)
    (root / GUIDE).unlink()
    result = review_owned_guide_enquiry(packet, repo_root=root)
    assert result["state"] == "HELD_SOURCE_OR_CONSENT_CONTRACT"
    assert result["proposed_cta"] is None
    source = root / GUIDE
    source.symlink_to(REPO / GUIDE)
    result = review_owned_guide_enquiry(packet, repo_root=root)
    assert result["state"] == "HELD_SOURCE_OR_CONSENT_CONTRACT"


def test_existing_founder_api_releases_only_readonly_review(tmp_path):
    root, pr, _ = _staged(tmp_path)
    app = FastAPI()
    app.include_router(create_founder_earned_media_router(
        enabled=True, repo_root=root, pr_root=pr, distribution_root=root,
    ))
    resp = TestClient(app).get("/v1/founder-earned-media/review")
    assert resp.status_code == 200
    payload = resp.json()
    review_data = payload["first_party_conversion"]
    assert review_data["source_code_readiness"] is True
    assert review_data["publication_executed"] is False
    assert payload["deployment_authorized"] is False
    for path, verbs in app.openapi()["paths"].items():
        assert set(verbs) == {"get"}


def test_corrupt_site_source_encoding_holds(tmp_path):
    root, _, packet = _staged(tmp_path)
    (root / GUIDE).write_bytes(bytes((255, 254)) + (root / GUIDE).read_bytes())
    held = review_owned_guide_enquiry(packet, repo_root=root)
    assert held["reason_code"] == "SOURCE_TEXT_INVALID_ENCODING"
    assert held["proposed_cta"] is None
