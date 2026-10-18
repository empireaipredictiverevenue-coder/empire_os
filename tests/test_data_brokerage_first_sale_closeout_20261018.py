"""Production-frozen first-sale evidence contract; no outbound, DB or payment."""
from __future__ import annotations
import json
from hashlib import sha256
from pathlib import Path
from scripts import review_data_brokerage_first_sale_closeout_20261018 as review


def test_actual_frozen_source_manifest_and_four_product_catalog_pass():
    result=review.inspect(root=review.ROOT)
    assert result["status"]=="BROKERAGE_PRIVATE_SAMPLE_VERIFIED_FIRST_SALE_HELD"
    assert result["original_report_private_and_integrity_verified"] is True
    assert result["report_sha256"]==review.RECEIPT_SHA
    assert result["product_count"]==4
    assert result["list_price_usd"]==199
    assert result["private_sample_not_customer_deliverable"] is True
    assert result["first_sale_ready"] is False
    assert result["revenue_or_payment_verified"] is False
    assert result["customer_export"] is False
    assert result["outbound_sent"] is False
    assert result["spc_research_only"] is True
    assert "BUYER_RECIPIENT_ROLE_AND_SUPPRESSION_UNVERIFIED" in result["blockers"]
    assert "customer" not in str(result.get("report_sha256",""))


def test_source_hash_tamper_fails_closed_without_exposing_bytes(monkeypatch):
    original=review._private_bytes
    def corrupt(p,n):
        if Path(p).name==review.REPORT.name:
            return b"bogus report with an unverified SEO ranking claim"
        return original(p,n)
    monkeypatch.setattr(review,"_private_bytes",corrupt)
    result=review.inspect()
    assert result["status"]=="HOLD_PRIVATE_BROKERAGE_EVIDENCE_UNVERIFIED"
    assert result["failure_stage"]=="RIGHTS_RECEIPT_OR_COMMERCIAL_GOVERNANCE"
    assert "bogus" not in json.dumps(result)


def test_forged_outbound_clearance_rejected(monkeypatch):
    original=review._private_bytes
    def forged(p,n):
        data=original(p,n)
        if Path(p).name==review.FOUNDER_REVIEW.name:
            x=json.loads(data)
            x["outbound_authorized"]=True
            return json.dumps(x).encode()
        return data
    monkeypatch.setattr(review,"_private_bytes",forged)
    result=review.inspect()
    assert result["status"].startswith("HOLD_")
    assert result["outbound_sent"] is False


def test_forged_product_rights_clearance_rejected(monkeypatch):
    original=review._private_bytes
    def forged(p,n):
        data=original(p,n)
        if Path(p).name==review.CATALOG.name:
            x=json.loads(data)
            x["products"][0]["raw_third_party_resale_cleared"]=True
            return json.dumps(x).encode()
        return data
    monkeypatch.setattr(review,"_private_bytes",forged)
    result=review.inspect()
    assert result["status"].startswith("HOLD_")
    assert result["failure_stage"]=="PRODUCT_CATALOG_STATUS_UNTRUSTED"


def test_private_source_requires_mode_0600_and_no_symlink(tmp_path):
    private=tmp_path/"check.json"
    private.write_text("{}")
    private.chmod(0o644)
    try:
        review._private_bytes(private,512)
    except ValueError:
        pass
    else:
        raise AssertionError("world-readable source accepted")
    private.chmod(0o600)
    ref=tmp_path/"link"
    ref.symlink_to(private)
    try:
        review._private_bytes(ref,512)
    except ValueError:
        pass
    else:
        raise AssertionError("symbolic link to private source accepted")


def test_no_flag_never_accesses_private_files(capsys,monkeypatch):
    monkeypatch.setattr(review,"inspect",lambda:(_ for _ in ()).throw(
        AssertionError("should not inspect")))
    assert review.main([])==2
    assert "HOLD_EXPLICIT_READ_ONLY_REQUIRED" in capsys.readouterr().out
