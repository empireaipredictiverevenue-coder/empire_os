import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
from empire_os import public_gateway as gateway

ROOT=Path(__file__).resolve().parents[1]


def test_guide_page_is_behind_original_reviewed_content_gate(tmp_path):
    assert gateway._STATIC_REVIEWED_ROUTES["roofing/cost-guide"] == "roofing/cost-guide.html"
    missing=tmp_path/"missing-receipt.json"
    page=tmp_path/"roofing"/"cost-guide.html"
    page.parent.mkdir()
    page.write_text("<main>Testing only, not a published homeowner notice</main>")
    assert gateway._approved_static_content_path(
        "roofing/cost-guide",site_root=tmp_path,receipt_path=missing) is None


def test_live_public_guide_does_not_open_without_approved_receipt():
    # This checks the current authorized site: an absent release receipt is
    # always a noindex 404. It never signs off a production document.
    response=TestClient(gateway.app).get("/roofing/cost-guide")
    assert response.status_code==404
    assert response.headers.get("x-robots-tag")=="noindex, nofollow"


def test_fake_hash_receipt_alone_cannot_release_without_editorial_buyer_legal_approval(tmp_path):
    site=tmp_path/"site"
    (site/"roofing").mkdir(parents=True)
    page=site/"roofing/cost-guide.html"
    page.write_text("<main>Synthetic reviewer fixture only</main>")
    payload={"schema_version":"empire.public-reviewed-content.v1",
        "founder_publication_authorized":True,
        "founder_approval_ref":"SYNTHETIC_TEST_NOT_REAL_APPROVAL",
        "legal_review_complete":True,
        "legal_review_ref":"SYNTHETIC_TEST_NOT_REAL_REVIEW",
        "privacy_request_handling_verified":True,
        "source_lane":"OWNED_FIRST_PARTY_US_HOMEOWNER",
        "indexation_enabled":False, "live_call_enabled":False,
        "execution_authority":"none",
        "buyer_landing_page_approved":False,
        "buyer_approval_ref":None,
        "content_quality_review_complete":False,
        "content_quality_review_ref":None,
        "approved_page_sha256":{
            "roofing/cost-guide":hashlib.sha256(page.read_bytes()).hexdigest(),
        },
    }
    receipt=tmp_path/"synthetic.json"
    receipt.write_text(json.dumps(payload))
    assert gateway._approved_static_content_path(
        "roofing/cost-guide",site_root=site,receipt_path=receipt) is None


def test_optional_subscriber_form_never_visible_without_readiness():
    page=(ROOT/"apps/empire-public-site/src/app/roofing/cost-guide/page.tsx").read_text()
    signup=(ROOT/"apps/empire-public-site/src/app/roofing/cost-guide/signup.tsx").read_text()
    assert 'No email address, signup, or purchase is needed' in page
    assert 'GuideSignup' in page
    assert 'readiness ? <form' in signup
    assert 'OPTIN_COLLECTION_ENABLED' in signup
    assert 'subscription_product === "EMPIRE_AI_OWN_BRAND_HOMEOWNER_UPDATES"' in signup
    assert 'optional_named_buyer_referral: false' in signup
    assert 'required checked={consent}' in signup
    assert '"/v1/consumer-optin/roofing/status"' in signup
    assert '"/v1/consumer-optin/roofing"' in signup


def test_existing_business_crm_not_used_for_consumer_subscriber_data():
    signup=(ROOT/"apps/empire-public-site/src/app/roofing/cost-guide/signup.tsx").read_text()
    for forbidden in (
        "/v1/checkout/commercial/interests",
        "/v1/leads/direct-intake",
        "localStorage.setItem",
        "buyer_consent: true",
    ):
        assert forbidden not in signup
