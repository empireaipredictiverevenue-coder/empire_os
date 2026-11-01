"""Approved /buy HTML source drift from genuine 747→753→756 website releases.

Synthetic fixture only. Keeps the original immutable-asset checks, rejects
mutable current live values, and never exercises release/restarts/payments.
"""
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts import deploy_direct_bsc_buyer_status_release as r


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _fixture(tmp_path, monkeypatch):
    base = tmp_path / "apps/empire-public-site/out"
    legacy = tmp_path / "docs/commercial"
    base.mkdir(parents=True)
    legacy.mkdir(parents=True)
    current = b"new-current-approved-website-HTML"
    actual = _hash(current)
    (base / "buy.html").write_bytes(current)
    (base / "_next/static/chunks").mkdir(parents=True)
    (base / "_next/static/chunks/legacy.js").write_bytes(b"legacy immutable")
    (legacy / "DIRECT_BSC_BUY_UI_STATIC_EXPORT_MANIFEST_20261013.json").write_text(
        json.dumps({
            "buy_sha256":_hash(b"old-october-thirteen-buy-html"),
            "assets":[{"path":"_next/static/chunks/legacy.js",
                       "sha256":_hash(b"legacy immutable")}],
        }),
    )
    before={"buy.html":actual}
    before.update({f"page-{i}.html":_hash(f"old-{i}".encode()) for i in range(746)})
    replacements={f"page-{i}.html":_hash(f"new-{i}".encode()) for i in range(5)}
    adds={f"_next/static/chunks/pricing-{i}.js":_hash(f"p-{i}".encode()) for i in range(6)}
    middle={**before,**replacements,**adds}
    second_replaced={f"page-{i}.html":_hash(f"scoped-{i}".encode()) for i in range(5)}
    second_added={f"_next/static/chunks/scoped-{i}.js":_hash(f"s-{i}".encode()) for i in range(3)}
    first={
        "schema_version":"empire.website.predictive.focused_pricing.scoped_v1",
        "founder_publication_approval":"2026-10-30 explicit: publish the pricing",
        "qa_status":"PRIVATE_BROWSER_QA_PASS",
        "customer_checkout_and_terms_remain_disabled":True,
        "no_database_checkout_card_payment_or_outbound_change":True,
        "publication_performed":False,
        "live_static_file_count":747,"target_static_file_count":753,
        "live_all_sha256":before,"replace_sha256":replacements,"add_sha256":adds,
    }
    second={
        "schema_version":"empire.website.predictive.scoped_crm_form.v1",
        "merged_browser_qa_status":"OFFLINE_SCOPED_CRM_BROWSER_PASS",
        "payment_or_binding_terms_authorized":False,
        "no_real_database_customer_or_payment_calls":True,
        "published":False,"live_original_file_count":753,"target_file_count":756,
        "live_all_sha256":middle,"replace_sha256":second_replaced,
        "add_sha256":second_added,
    }
    price=tmp_path/"price.json";scoped=tmp_path/"scoped.json"
    price.write_text(json.dumps(first));scoped.write_text(json.dumps(second))
    monkeypatch.setattr(r,"ROOT",tmp_path)
    monkeypatch.setattr(r,"PRICING_RELEASE_MANIFEST",price)
    monkeypatch.setattr(r,"SCOPED_RELEASE_MANIFEST",scoped)
    monkeypatch.setattr(r,"PRICING_RELEASE_SHA",_hash(price.read_bytes()))
    monkeypatch.setattr(r,"SCOPED_RELEASE_SHA",_hash(scoped.read_bytes()))
    monkeypatch.setattr(r,"APPROVED_LATER_BUY_SHA",actual)
    return base,price,scoped,first,second


def test_original_legacy_and_later_approved_buy_both_remain_accepted(tmp_path,monkeypatch):
    base,price,scoped,first,second = _fixture(tmp_path,monkeypatch)
    r._published_checkout_verified()
    assert r._approved_later_checkout_buy_sha256() == _hash((base/"buy.html").read_bytes())


def test_unreviewed_current_page_is_not_silently_re_pinned(tmp_path,monkeypatch):
    base,*_ = _fixture(tmp_path,monkeypatch)
    (base/"buy.html").write_bytes(b"unapproved-html-change")
    with pytest.raises(ValueError,match="not verified"):
        r._published_checkout_verified()


def test_original_immutable_asset_still_must_match(tmp_path,monkeypatch):
    base,*_ = _fixture(tmp_path,monkeypatch)
    (base/"_next/static/chunks/legacy.js").write_bytes(b"wrong-asset")
    with pytest.raises(ValueError,match="immutable asset changed"):
        r._published_checkout_verified()


def test_pinned_later_manifests_cannot_be_modified_after_review(tmp_path,monkeypatch):
    _,price,*_ = _fixture(tmp_path,monkeypatch)
    price.write_bytes(price.read_bytes()+b"\n")
    with pytest.raises(ValueError,match="receipt changed"):
        r._published_checkout_verified()


def test_fake_intermediate_manifests_fail_even_when_both_hash_pins_updated(tmp_path,monkeypatch):
    base,price,scoped,first,second = _fixture(tmp_path,monkeypatch)
    second["live_all_sha256"]["page-0.html"]="0"*64
    scoped.write_text(json.dumps(second))
    monkeypatch.setattr(r,"SCOPED_RELEASE_SHA",_hash(scoped.read_bytes()))
    with pytest.raises(ValueError,match="lineage mismatch"):
        r._published_checkout_verified()


def test_later_website_receipt_must_not_claim_payment_enablement(tmp_path,monkeypatch):
    _,price,scoped,first,second = _fixture(tmp_path,monkeypatch)
    second["payment_or_binding_terms_authorized"]=True
    scoped.write_text(json.dumps(second))
    monkeypatch.setattr(r,"SCOPED_RELEASE_SHA",_hash(scoped.read_bytes()))
    with pytest.raises(ValueError,match="scope unverified"):
        r._published_checkout_verified()


def test_fraudulent_replacement_of_buy_html_in_overlay_rejected(tmp_path,monkeypatch):
    _,price,scoped,first,second = _fixture(tmp_path,monkeypatch)
    second["replace_sha256"]["buy.html"]="0"*64
    scoped.write_text(json.dumps(second))
    monkeypatch.setattr(r,"SCOPED_RELEASE_SHA",_hash(scoped.read_bytes()))
    with pytest.raises(ValueError,match="inventory invalid"):
        r._published_checkout_verified()


def test_manifest_missing_or_untrusted_fails_closed(tmp_path,monkeypatch):
    _,price,scoped,*_ = _fixture(tmp_path,monkeypatch)
    price.unlink()
    with pytest.raises(ValueError,match="receipt absent"):
        r._published_checkout_verified()


def test_restricted_production_service_can_read_pinned_original_evidence():
    """ProtectHome=yes root timer must never depend on /home/ubuntu files."""
    from hashlib import sha256
    owner=Path(__file__).resolve().parents[1]
    for deployed,checksum in (
        (r.PRICING_RELEASE_MANIFEST,r.PRICING_RELEASE_SHA),
        (r.SCOPED_RELEASE_MANIFEST,r.SCOPED_RELEASE_SHA),
    ):
        assert str(deployed).startswith('/srv/empire_os/docs/commercial/original_release_evidence/')
        original=owner / deployed.relative_to('/srv/empire_os')
        assert original.is_file() and not original.is_symlink()
        assert sha256(original.read_bytes()).hexdigest()==checksum
        assert original.stat().st_mode & 0o444
