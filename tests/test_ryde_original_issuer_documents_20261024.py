"""Four real issuer-owned Ryde document types; no entitlement to bid."""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
import zipfile

import pytest

from scripts import reconcile_ryde_original_issuer_documents_20261024 as ryde

TENDER={
    "ocid":ryde.OCID,
    "official_notice_url":ryde.NOTICE,
    "bid_authorized":False,
    "bid_eligible":False,
    "policy_or_supplier_hold":"HOLD_CUSTOM_SCOPE_OR_SUPPLIER_FIT",
    "tender_closes_at_utc":"2026-10-26T12:00:00+00:00",
}


def deadline():
    return {
        "status":"DEADLINES_TRIAGED_REVIEW_ONLY",
        "external_bids_authorized":False,
        "source_qualified_customer_count":0,
        "items":[dict(TENDER)],
    }


def sample_pdf():
    return b"%PDF-1.7\n" + b"A"*1300 + b"\n%%EOF"


def sample_docx(label):
    if label=="pricing_schedule":
        fields=["Pricing schedule","GRAND TOTAL","Rate"]
    else:
        fields=["References","Reference 1","Reference 2"]
    paragraphs="".join(
        f'<w:p><w:r><w:t>{p}</w:t></w:r></w:p>' for p in fields
    )
    xml=(
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'+paragraphs+'</w:body></w:document>'
    )
    buff=BytesIO()
    with zipfile.ZipFile(buff,"w",compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("word/document.xml",xml)
        archive.writestr("docProps/custom.xml"," "*1100)
    return buff.getvalue()


def fixtures(monkeypatch):
    items={}
    originals={}
    for label,(name,mime,_digest) in ryde.FILES.items():
        body=sample_pdf() if name.endswith(".pdf") else sample_docx(label)
        url=ryde.URL_BASE+name
        items[url]={"status":200,"url":url,"content_type":mime,"body":body}
        originals[label]=(name,mime,hashlib.sha256(body).hexdigest())
    monkeypatch.setattr(ryde,"FILES",originals)
    return items


def test_genuine_issuer_file_structure_yields_no_customer_or_bid(monkeypatch):
    data=fixtures(monkeypatch)
    report=ryde.verify_public_documents(source_report=deadline(),fetch=lambda u:data[u])
    assert report["status"]==ryde.READY
    assert report["source_deadline_conflict"] is True
    assert report["clarification_deadline_from_issuer_document"]=="2026-10-26"
    assert report["quotation_deadline_from_issuer_document"]=="2026-11-02T12:00:00+00:00"
    assert report["buyer_closing_date_authoritatively_reconciled"] is False
    assert report["issuer_document_count"]==4
    assert report["payment_terms_as_stated_percent"]==[20,20,30,30]
    assert report["contract_value_in_issuer_pricing_template"] is None
    assert report["bid_eligibility_verified"] is False
    assert report["bid_authorized"] is False
    assert report["contact_authorized"] is False
    assert report["external_bid_submitted"] is False
    assert report["email_sent"] is False
    assert report["crm_writes"] is False
    assert report["payment_actions"] is False
    assert report["verified_profit_margin"] is None
    assert len(report["published_requirements"])>=10


@pytest.mark.parametrize("malfunction",[
    "missing_file","changed_bytes","wrong_mime","redirect",
    "bad_pdf","malformed_docx","unavailable",
])
def test_original_public_issuer_validation_fails_closed(monkeypatch,malfunction):
    data=fixtures(monkeypatch)
    target=ryde.URL_BASE+ryde.FILES["request_to_quote"][0]
    altered=ryde.URL_BASE+ryde.FILES["pricing_schedule"][0]
    if malfunction=="missing_file":data.pop(target)
    elif malfunction=="changed_bytes":data[target]["body"]+=b"more"
    elif malfunction=="wrong_mime":data[target]["content_type"]="text/html"
    elif malfunction=="redirect":data[target]["url"]="https://example.org/mirror"
    elif malfunction=="bad_pdf":
        b=b"notpdf"*220
        data[target]["body"]=b
        name,mime,_=ryde.FILES["request_to_quote"]
        ryde.FILES["request_to_quote"]=(name,mime,hashlib.sha256(b).hexdigest())
    elif malfunction=="malformed_docx":
        b=b"junk"*400
        data[altered]["body"]=b
        name,mime,_=ryde.FILES["pricing_schedule"]
        ryde.FILES["pricing_schedule"]=(name,mime,hashlib.sha256(b).hexdigest())
    elif malfunction=="unavailable":data[target]["status"]=403
    report=ryde.verify_public_documents(source_report=deadline(),fetch=lambda u:data[u])
    assert report["status"]==ryde.HELD
    assert report["bid_authorized"] is False
    assert report["external_bid_submitted"] is False
    assert "documents" not in report


def test_original_notice_changed_or_privileges_escalated_hold(monkeypatch):
    data=fixtures(monkeypatch)
    for field,value in [
        ("tender_closes_at_utc","2026-11-02T12:00:00+00:00"),
        ("policy_or_supplier_hold","HOLD_PAID_TRAFFIC_OR_UNCLEAR_PAID_SCOPE"),
        ("bid_eligible",True),
    ]:
        p=deadline()
        p["items"][0][field]=value
        result=ryde.verify_public_documents(source_report=p,fetch=lambda u:data[u])
        assert result["status"]==ryde.HELD


def test_unauthorized_url_rejected():
    assert not ryde._safe_url("https://rydetowncouncil.gov.uk.evil.test/file.pdf")
    assert not ryde._safe_url("http://rydetowncouncil.gov.uk/wp-content/uploads/2026/10/Request-to-Quote-Data-Audit-1.pdf")
    assert not ryde._safe_url(ryde.URL_BASE+"something-else.pdf")
    assert not ryde._safe_url(ryde.URL_BASE+"Request-to-Quote-Data-Audit-1.pdf?debug=1")


def test_private_result_locks_and_symlink(tmp_path,monkeypatch):
    data=fixtures(monkeypatch)
    report=ryde.verify_public_documents(source_report=deadline(),fetch=lambda u:data[u])
    p=tmp_path/ryde.OUTPUT
    p.parent.mkdir(parents=True)
    p.parent.chmod(0o700)
    assert ryde.write_private(tmp_path,report)==p
    assert p.stat().st_mode & 0o077==0
    content=json.loads(p.read_text())
    assert content["bid_eligibility_verified"] is False
    assert content["source_deadline_conflict"] is True
    p.unlink()
    outside=tmp_path/"untouched"
    outside.write_text("KEEP")
    p.symlink_to(outside)
    with pytest.raises(ValueError):
        ryde.write_private(tmp_path,report)
    assert outside.read_text()=="KEEP"
    with pytest.raises(ValueError):
        ryde.write_private(tmp_path,ryde.verify_public_documents(source_report={}))


def test_untrusted_existing_deadline_record_does_not_fetch():
    assert ryde.verify_public_documents(source_report={},fetch=lambda url:(_ for _ in ()).throw(AssertionError("NOT_EXPECTED")))["status"]==ryde.HELD
