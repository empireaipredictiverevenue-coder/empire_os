"""Synthetic legal admission tests; NO real legal approval or publish receipt."""
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from empire_os import public_gateway as gateway


def prepare(tmp_path):
    site=tmp_path/"site"
    site.mkdir()
    digests={}
    for name in ("privacy","terms"):
        text="<html><head><meta name='robots' content='noindex'></head><body>Reviewed fictional test fixture only.</body></html>"
        (site/f"{name}.html").write_text(text)
        digests[name]=hashlib.sha256(text.encode()).hexdigest()
    receipt={
        "schema_version":"empire.public-reviewed-content.v1",
        "founder_publication_authorized":True,
        "founder_approval_ref":"TEST_FIXTURE_ONLY_not_a_real_approval",
        "legal_review_complete":True,
        "legal_review_ref":"TEST_FIXTURE_ONLY_not_a_legal_signoff",
        "privacy_request_handling_verified":True,
        "source_lane":"OWNED_FIRST_PARTY_US_HOMEOWNER",
        "indexation_enabled":False,
        "live_call_enabled":False,
        "execution_authority":"none",
        "approved_page_sha256":digests,
    }
    f=tmp_path/"synthetic.json"
    f.write_text(json.dumps(receipt))
    return site,f,receipt


def update_fixture(site,receipt_path,receipt,route,html):
    (site/f"{route}.html").write_text(html)
    receipt["approved_page_sha256"][route]=hashlib.sha256(html.encode()).hexdigest()
    receipt_path.write_text(json.dumps(receipt))


def test_hypothetical_final_release_needs_exact_hash_and_all_fields(tmp_path):
    site,path,receipt=prepare(tmp_path)
    assert gateway._approved_static_content_path(
        "privacy",site_root=site,receipt_path=path)==site/"privacy.html"
    (site/"privacy.html").write_text("MODIFIED AFTER REVIEW")
    assert gateway._approved_static_content_path(
        "privacy",site_root=site,receipt_path=path) is None
    assert gateway._approved_static_content_path(
        "roofing/unknown",site_root=site,receipt_path=path) is None


@pytest.mark.parametrize("marker",[
    "Founder/legal review draft",
    "not an approved or effective policy",
    "Research draft",
    "This is a working draft",
    "Status: PROPOSED",
    "NOT EFFECTIVE OR PUBLISHED",
    "final review copy",
])
@pytest.mark.parametrize("route",["privacy","terms"])
def test_review_copy_never_released_even_if_digests_and_flags_match(
        tmp_path,marker,route):
    site,path,receipt=prepare(tmp_path)
    update_fixture(site,path,receipt,route,f"<html><body>{marker}</body></html>")
    assert gateway._approved_static_content_path(
        route,site_root=site,receipt_path=path) is None


def test_real_review_documents_remain_proposed_and_have_no_release_authority(tmp_path):
    for name in ("PRIVACY_POLICY","TERMS"):
        text=Path(f"docs/LEAD_SMART_{name}_FINAL_REVIEW_20261012.md").read_text()
        assert "Status: PROPOSED; NOT EFFECTIVE OR PUBLISHED" in text
    site,path,_=prepare(tmp_path)
    path.unlink()
    assert gateway._approved_static_content_path(
        "privacy",site_root=site,receipt_path=path) is None
    assert gateway._approved_static_content_path(
        "terms",site_root=site,receipt_path=path) is None


def test_live_gateway_unapproved_routes_remain_404_and_noindex():
    client=TestClient(gateway.app)
    for route in ("/privacy","/terms"):
        response=client.get(route)
        assert response.status_code==404
        assert response.headers.get("x-robots-tag")=="noindex, nofollow"
        assert "tel:" not in response.text
