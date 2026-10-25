"""No-write acceptance proofs for exact public SaaS release GET verifier."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from scripts import verify_public_saas_preview_release_20261025 as v
from scripts import review_saas_evidence_release_candidate_20261025 as qa


@pytest.fixture()
def case():
    m=v._load_pinned_documents()
    before=(qa.LIVE/"predictive-revenue.html").read_bytes()
    after=(qa.CANDIDATE/"predictive-revenue.html").read_bytes()
    catalog=json.dumps({"products":[{"product_code":f"verified_product_{i}"}
                                     for i in range(5)]}).encode()
    def fake(mode,overrides=None):
        src={"/predictive-revenue":before if mode=="before" else after,
             "/v1/checkout/predictive-revenue/products":catalog,
             "/privacy":b"<html><body>Privacy policy</body></html>"}
        if mode=="after":
            for item in m["added_static_assets"]:
                src["/"+item["path"]]=(qa.CANDIDATE/item["path"]).read_bytes()
        src.update(overrides or {})
        requested=[]
        def get(path):
            requested.append(path)
            return src[path]
        return get,requested
    return m,before,after,fake


def test_before_release_is_verified_without_fake_customer_or_success(case):
    m,_,_,fake=case
    get,paths=fake("before")
    result=v.assess("before",manifest=m,get=get)
    assert result["status"]=="EXISTING_PUBLIC_PAGE_VERIFIED_NEW_PREVIEW_NOT_LIVE"
    assert result["public_preview_visible"] is False
    assert paths==["/predictive-revenue",
                   "/v1/checkout/predictive-revenue/products","/privacy"]
    assert result["publication_authorized_by_this_check"] is False
    assert result["database_writes"] is False


def test_full_672_inventory_and_all_ten_served_asset_bytes_pass(case):
    m,_,_,fake=case
    get,requested=fake("after")
    r=v.assess("after",manifest=m,get=get,
               local_index=qa.read_index(qa.CANDIDATE))
    assert r["public_preview_visible"] is True
    assert r["new_hashed_static_assets_get_verified"]==10
    assert r["local_paired_rsc_inventory_verified"] is True
    assert r["public_rsc_txt_endpoint_verified"] is False
    assert r["separate_real_browser_navigation_check_required"] is True
    assert r["independent_website_owner_root_receipt_verified"] is False
    assert r["publication_authorized_by_this_check"] is False
    assert all(path.startswith("/") for path in requested)
    assert len(requested)==13


def test_after_must_not_accept_original_public_html(case):
    m,before,_,fake=case
    get,_=fake("after",overrides={"/predictive-revenue":before})
    with pytest.raises(v.PublicSaaSReleaseHold,match="PUBLIC_HTML_NOT_MATCHING"):
        v.assess("after",manifest=m,get=get,
                 local_index=qa.read_index(qa.CANDIDATE))


def test_after_detects_single_public_asset_divergence(case):
    m,_,_,fake=case
    target="/"+m["added_static_assets"][0]["path"]
    get,_=fake("after",overrides={target:b"tampered"})
    with pytest.raises(v.PublicSaaSReleaseHold,match="STATIC_ASSET_NOT_MATCHING"):
        v.assess("after",manifest=m,get=get,
                 local_index=qa.read_index(qa.CANDIDATE))


def test_local_rsc_stale_even_if_public_html_matches(case):
    m,_,_,fake=case
    get,_=fake("after")
    index=qa.read_index(qa.CANDIDATE)
    index["predictive-revenue.txt"]=m["original_rsc_sha256"]
    with pytest.raises(v.PublicSaaSReleaseHold):
        v.assess("after",manifest=m,get=get,local_index=index)


@pytest.mark.parametrize("broken,diagnosis",[
    ({"/v1/checkout/predictive-revenue/products":b'{"products":[]}'},
     "CATALOGUE_HAS_UNEXPECTED"),
    ({"/privacy":b"<html>nothing here</html>"},
     "PRIVACY_DOCUMENT_NOT_GROUNDED"),
    ({"/v1/checkout/predictive-revenue/products":b'{"products":"wrong"}'},
     "UNTRUSTED_PUBLIC_CATALOGUE"),
])
def test_privacy_or_live_catalogue_is_required(case,broken,diagnosis):
    m,_,_,fake=case
    get,_=fake("before",overrides=broken)
    with pytest.raises(v.PublicSaaSReleaseHold,match=diagnosis):
        v.assess("before",manifest=m,get=get)


@pytest.mark.parametrize("unsafe",[
    "//attacker.com/", "/../admin", "/predictive-revenue?source=spam",
    "/predictive-revenue#fragment", "/_next/%2e%2e/trick.js",
    "https://other.test/index.html", "/path\\secret"
])
def test_no_arbitrary_user_supplied_get_path(unsafe):
    with pytest.raises(v.PublicSaaSReleaseHold):
        v.fetch_public_get(unsafe)


def test_wrong_founder_receipt_does_not_authorize_publication(case):
    m,_,_,fake=case
    changed=deepcopy(m)
    changed["added_static_assets"][0]["sha256"]="0"*64
    get,_=fake("after")
    with pytest.raises(v.PublicSaaSReleaseHold):
        v.assess("after",manifest=changed,get=get,
                 local_index=qa.read_index(qa.CANDIDATE))
