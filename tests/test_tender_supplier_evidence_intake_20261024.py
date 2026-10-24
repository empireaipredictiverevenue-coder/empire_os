"""Supplier RFQ drop: file custody is never professional validation or bid authority."""
from __future__ import annotations
from datetime import datetime, timezone
from io import BytesIO
import json
import os
import zipfile
import pytest
from empire_os import tender_supplier_evidence_intake as s

NOW=datetime(2026,10,24,13,32,tzinfo=timezone.utc)

def make_root(tmp_path):
    folder=tmp_path/s.BASE
    folder.mkdir(parents=True)
    folder.chmod(0o700)
    return tmp_path

def stage(path, data, mode=0o600):
    path.write_bytes(data)
    path.chmod(mode)
    os.utime(path,(NOW.timestamp()-10,NOW.timestamp()-10))
    return path

def pdf():
    return b"%PDF-1.7\n"+b"data"*160+b"\n%%EOF"

def docx():
    data=BytesIO()
    with zipfile.ZipFile(data,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml",'<Types xmlns="abc"></Types>')
        archive.writestr("word/document.xml",'<w:document xmlns:w="a">test</w:document>')
    return data.getvalue()

def test_missing_supplier_rfq_stays_await_not_bid_ready(tmp_path):
    root=make_root(tmp_path)
    pending=s.inventory(root,now=NOW)
    assert pending["status"]==s.AWAIT
    path=s.ensure_private_drop(root)
    assert path==root/s.DROP
    assert path.stat().st_mode & 0o077 == 0
    again=s.inventory(root,now=NOW)
    assert again["status"]==s.AWAIT
    assert again["document_count"]==0
    assert again["full_rfq_reviewed"] is False
    assert again["price_approved"] is False
    assert again["bid_authorized"] is False
    assert again["crm_writes"] is False
    saved=s.save_private(root,again)
    assert saved.stat().st_mode & 0o077==0
    assert json.loads(saved.read_text())["supplier_eligibility_verified"] is False

def test_pdf_and_docx_received_only_never_validated(tmp_path):
    root=make_root(tmp_path)
    folder=s.ensure_private_drop(root)
    stage(folder/"CA18567_RFQ.pdf",pdf())
    stage(folder/"SupplierResponse.docx",docx())
    report=s.inventory(root,now=NOW)
    assert report["status"]==s.OBSERVED
    assert report["document_count"]==2
    assert sorted(x["content_format"] for x in report["documents"])==["DOCX","PDF"]
    for doc in report["documents"]:
        assert doc["source_document_sha256"]
        assert doc["issuer_authenticity_verified"] is False
        assert doc["human_specialist_reviewed"] is False
        assert doc["parsed_as_supplier_authority"] is False
        assert doc["latest_amendment_verified"] is False
    assert report["full_rfq_reviewed"] is False
    assert report["scored_quality_criteria_verified"] is False
    assert report["supplier_eligibility_verified"] is False
    assert report["bid_ready"] is False
    assert report["bid_authorized"] is False
    assert report["buyer_contacted"] is False
    assert report["external_bid_submitted"] is False
    assert report["revenue_verified"] is False

@pytest.mark.parametrize("mode",["public","malformed","symlink","hardlink","future","wrong_name","docx_invalid"])
def test_bad_supplier_files_fail_closed(tmp_path,mode):
    root=make_root(tmp_path)
    drop=s.ensure_private_drop(root)
    src=drop/"CA18567_RFQ.pdf"
    if mode=="public":stage(src,pdf(),mode=0o644)
    elif mode=="malformed":stage(src,b"fake"*160)
    elif mode=="symlink":
        elsewhere=root/"external.pdf"
        stage(elsewhere,pdf())
        src.symlink_to(elsewhere)
    elif mode=="hardlink":
        elsewhere=root/"external.pdf"
        stage(elsewhere,pdf())
        os.link(elsewhere,src)
    elif mode=="future":
        stage(src,pdf())
        os.utime(src,(NOW.timestamp()+400,NOW.timestamp()+400))
    elif mode=="wrong_name":stage(drop/"CA18567 confidential.pdf",pdf())
    else:stage(drop/"SupplierResponse.docx",b"%PDF-not-ooxml"+b"X"*200)
    report=s.inventory(root,now=NOW)
    assert report["status"]==s.HELD
    assert report["bid_ready"] is False
    assert report["full_rfq_reviewed"] is False
    assert report["document_count"]==0
    with pytest.raises(ValueError):
        s.save_private(root,report)

def test_private_permissions_and_unexpected_folders_fail(tmp_path):
    root=make_root(tmp_path)
    parent=s.ensure_private_drop(root).parent
    parent.chmod(0o755)
    assert s.inventory(root,now=NOW)["status"]==s.HELD
    with pytest.raises(ValueError):
        s.ensure_private_drop(root)
    parent.chmod(0o700)
    s.ensure_private_drop(root).chmod(0o755)
    assert s.inventory(root,now=NOW)["status"]==s.HELD
    with pytest.raises(ValueError):
        s.ensure_private_drop(root)

def test_symlink_receipt_not_overwritten(tmp_path):
    root=make_root(tmp_path)
    s.ensure_private_drop(root)
    report=s.inventory(root,now=NOW)
    target=root/s.RECEIPT
    outsider=root/"outside.json"
    outsider.write_text("untouched")
    target.symlink_to(outsider)
    with pytest.raises(ValueError):
        s.save_private(root,report)
    assert outsider.read_text()=="untouched"

def test_tender_drop_rejects_more_than_eight_documents(tmp_path):
    root=make_root(tmp_path)
    drop=s.ensure_private_drop(root)
    for i in range(9):stage(drop/f"RFQ_{i}.pdf",pdf())
    assert s.inventory(root,now=NOW)["status"]==s.HELD

def test_other_file_is_not_automatically_trusted(tmp_path):
    root=make_root(tmp_path)
    drop=s.ensure_private_drop(root)
    stage(drop/"folder_is_not_document.pdf",pdf())
    (drop/"README.txt").write_text("Drop content")
    assert s.inventory(root,now=NOW)["status"]==s.HELD
