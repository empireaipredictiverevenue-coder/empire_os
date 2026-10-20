"""Private original-site hash state vs historic checkout manifest; no mutation."""
from hashlib import sha256
import json

from empire_os import flagship_v2_live_attestation as v2
from scripts import review_founder_three_streams_20261020 as control
from test_review_founder_three_streams_20261020 import (
    NOW, fixture, original_ops,
)


def test_exact_static_release_passes_and_single_file_tamper_fails(tmp_path, monkeypatch):
    live=tmp_path/"apps/empire-public-site/out"
    live.mkdir(parents=True)
    receipts={}
    for i in range(632):
        name=f"chunks/page-{i:04}.js"
        p=live/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(f"owner-proof-{i}".encode())
        receipts[name]=sha256(p.read_bytes()).hexdigest()
    expected=sha256(json.dumps(receipts,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    receipt=tmp_path/"original-owner-receipt.json"
    receipt.write_text(json.dumps({
        "schema_version":v2.EXPECTED_SCHEMA,
        "status":"PRIVATE_MIXED_GENERATION_STATIC_CANDIDATE_ASSEMBLED",
        "candidate_integrity_verified":True,
        "new_public_release_authorized":False,
        "public_files_modified":False,
        "mixed_next_build_routing_navigation_review_required":True,
        "static_file_sha256":receipts,
    }))
    monkeypatch.setattr(v2,"CANONICAL_ROOT",tmp_path)
    monkeypatch.setattr(v2,"V2_RECEIPT",receipt)
    monkeypatch.setattr(v2,"EXPECTED_INVENTORY",expected)
    assert v2.attest_public_flagship_v2(tmp_path)["exact_published_bytes_verified"] is True
    assert v2.attest_public_flagship_v2(tmp_path)["payment_and_outbound_authorized"] is False
    (live/"chunks/page-0019.js").write_bytes(b"tampered")
    assert v2.attest_public_flagship_v2(tmp_path)["exact_published_bytes_verified"] is False


def test_sandbox_cannot_claim_actual_live_v2(tmp_path):
    result=v2.attest_public_flagship_v2(tmp_path)
    assert result["exact_published_bytes_verified"] is None


def test_three_stream_treats_v2_as_published_but_keeps_legacy_pin_hold(tmp_path, monkeypatch):
    raw=original_ops()
    root=fixture(tmp_path,raw)
    monkeypatch.setattr(control,"attest_public_flagship_v2",lambda root:{
        "status":"EXACT_APPROVED_V2_PUBLIC_STATIC_BYTES_VERIFIED",
        "exact_published_bytes_verified":True,
        "verified_static_file_count":632,
        "payment_and_outbound_authorized":False,
    })
    result=control.build_checkpoint(root=root,now=NOW)
    site=result["streams"][1]
    assert site["current_state"]=="FLAGSHIP_V2_PUBLISHED_VERIFIED_HISTORICAL_CHECKOUT_PIN_PENDING"
    assert site["legacy_buy_html_release_status"]=="LEGACY_BUY_UI_HTML_OR_ASSET_INTEGRITY_RELEASE_HOLD"
    assert site["next_action"]=="ITERATE_PUBLISHED_FLAGSHIP_V2_AND_REVIEW_NEW_BUY_MANIFEST"
    assert result["streams"][0]["current_state"]=="ZERO_RECORDED_FIRST_PARTY_SALES_ENQUIRIES"
    assert result["payment_or_revenue_recorded"] is False
