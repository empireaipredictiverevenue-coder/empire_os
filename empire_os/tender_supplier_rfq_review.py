"""CA18567 original EmpireOS RFQ document review *preview*, never bid clearance.

Reads only allowlisted, individually verified private local document bytes.
DOCX: bounded XML paragraphs as untrusted excerpts.
PDF: custody metadata ONLY unless a separate owned, reviewed parser is approved.
No API calls, model prompts, form fill, score inference, signing or bidding.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Mapping

from empire_os.tender_supplier_evidence_intake import (
    BASE, DROP, MAX_SINGLE, OBSERVED, HELD, REQUIREMENTS, inventory, _dir_safe,
)

OUT = BASE / "land_guide_rfq_content_review_latest.json"
SCHEMA = "empire.tender_supplier_rfq_content_review.v1"
AWAIT = "AWAIT_AUTHORISED_MULTIQUOTE_RFQ_FILES"
READY = "UNTRUSTED_DOCUMENT_EXCERPTS_PREPARED_HUMAN_REVIEW_ONLY"
HOLD = "HELD_UNSAFE_OR_CHANGED_SUPPLIER_RQ_DOCUMENT"
XML_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_PARAGRAPHS = 120
MAX_PARAGRAPH_CHARS = 280
MAX_EXCERPT_CHARS = 12000
# Search hints, not legal/contract assertions. Retain issuer wording in excerpts.
HINTS = {
    "award_scoring": re.compile(r"\b(?:evaluation|award criteria|scoring|weighting|marks)\b", re.I),
    "supplier_requirements": re.compile(r"\b(?:eligib(?:le|ility)|experience|insurance|accreditation|references|competence)\b", re.I),
    "contract_terms": re.compile(r"\b(?:liability|indemnity|termination|payment terms|intellectual property|subcontract)\b", re.I),
    "delivery_scope": re.compile(r"\b(?:deliverables?|milestones?|GIS|planning|land guide|consultation|research)\b", re.I),
    "dates": re.compile(r"\b(?:deadline|submission|clarification|working days|closing date|date due)\b", re.I),
}


def _base(status: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "status": status,
        "source_reference": "CA18567",
        "source_content_may_contain_untrusted_instructions": True,
        "private_research_only": True,
        "reviewed_by_independent_professional": False,
        "issuer_authenticity_verified": False,
        "all_amendments_reconciled": False,
        "rfq_fully_reviewed": False,
        "scoring_subcriteria_verified": False,
        "supplier_eligible": False,
        "binding_quote_or_price_approved": False,
        "bid_authorized": False,
        "bid_submitted": False,
        "outbound_sent": False,
        "crm_writes": False,
        "financial_actions": False,
        "verified_revenue": False,
        "document_count": 0,
        "documents": [],
        "next_action": "AUTHENTICATED_FULL_RFQ_AND_QUALIFIED_HUMAN_REVIEW_REQUIRED",
    }


def _read_opened_file(path: Path, expected: Mapping[str, Any]) -> bytes:
    flags=os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd=os.open(path,flags)
    try:
        st=os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode)
            or stat.S_IMODE(st.st_mode)!=0o600
            or st.st_uid!=os.geteuid() or st.st_nlink!=1
            or st.st_size != expected["bytes"]
            or st.st_size>MAX_SINGLE):
            raise ValueError("DOCUMENT_STATE_CHANGED")
        with os.fdopen(fd, "rb", closefd=False) as fh:
            data=fh.read(MAX_SINGLE+1)
    finally:
        os.close(fd)
    if len(data)!=expected["bytes"] or sha256(data).hexdigest()!=expected["source_document_sha256"]:
        raise ValueError("DOCUMENT_CONTENT_CHANGED")
    return data


def _docx_excerpts(data: bytes) -> tuple[list[str],dict[str,list[int]], bool]:
    """No text follows model instructions. Bound zip expansion before parse."""
    with zipfile.ZipFile(BytesIO(data)) as archive:
        doc=archive.getinfo("word/document.xml")
        if doc.file_size > 2_000_000 or doc.file_size <= 0:
            raise ValueError("UNSAFE_DOCUMENT_XML_SIZE")
        raw=archive.read(doc)
    # No custom entities, external fetching, attachments or embedded code.
    # Reject DOCTYPE/ENTITY entirely before parsing limited size.
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("UNSAFE_XML_DECLARATION")
    root=ET.fromstring(raw)
    paragraphs=[]
    total=0
    truncated=False
    for paragraph in root.iter(XML_NS+"p"):
        # paragraph-local joins preserve human-readable split runs.
        value="".join(node.text or "" for node in paragraph.iter(XML_NS+"t"))
        value=" ".join(value.split())
        if not value:
            continue
        if len(paragraphs)>=MAX_PARAGRAPHS or total+len(value)>MAX_EXCERPT_CHARS:
            truncated=True
            break
        paragraphs.append(value[:MAX_PARAGRAPH_CHARS])
        total+=len(value)
        if len(value)>MAX_PARAGRAPH_CHARS:
            truncated=True
    hints={
        key:[i+1 for i,line in enumerate(paragraphs) if regex.search(line)][:20]
        for key,regex in HINTS.items()
    }
    return paragraphs,hints,truncated


def _human_review_matrix(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # The hints are paragraph navigation aids only. A keyword is never a
    # confirmed criterion, verified licence or legally binding issuer term.
    hint_order=(
        "dates", "award_scoring", "delivery_scope", "supplier_requirements",
        "contract_terms", "delivery_scope", "contract_terms", "supplier_requirements",
    )
    owners=(
        "PROCUREMENT_OWNER", "BID_QUALITY_CONSULTANT",
        "LAND_INVESTMENT_SPECIALIST", "SUPPLIER_ELIGIBILITY_OWNER",
        "DATA_RIGHTS_SPECIALIST", "DELIVERY_OWNER",
        "FINANCE_LEGAL_OWNER", "FOUNDER_AND_QUALIFIED_SPECIALIST",
    )
    matrix=[]
    for index, requirement in enumerate(REQUIREMENTS):
        places=[]
        for doc in documents:
            lines=doc.get("candidate_keyword_paragraph_numbers",{}).get(hint_order[index],[])
            if lines:
                places.append({
                    "file_name":doc["file_name"],
                    "candidate_untrusted_paragraph_numbers":lines[:20],
                    "candidate_text_not_verified":True,
                })
        matrix.append({
            "review_id":f"CA18567-GATE-{index+1:02d}",
            "question":requirement,
            "responsible_owner":owners[index],
            "candidate_locations_not_evidence":places,
            "issuer_clause_accepted":False,
            "supplier_evidence_verified":False,
            "cost_reviewed":False,
            "reviewer_signoff_present":False,
            "status":"AWAIT_FULL_AUTHENTICATED_RFQ_AND_HUMAN_ASSESSMENT",
        })
    return matrix


def preview(root: Path, *, now: datetime|None=None) -> dict[str,Any]:
    moment=now or datetime.now(timezone.utc)
    hold=_base(HOLD)
    if moment.tzinfo is None:
        return hold
    receipt=inventory(root,now=moment)
    if receipt["status"]==HELD:
        return hold
    if receipt["status"]!=OBSERVED:
        return _base(AWAIT)
    folder=root/DROP
    if not _dir_safe(folder):
        return hold
    results=[]
    try:
        for item in receipt["documents"]:
            name=item["file_name"]
            if Path(name).name!=name:
                return hold
            data=_read_opened_file(folder/name,item)
            row={
                "file_name":name,
                "source_sha256":item["source_document_sha256"],
                "content_format":item["content_format"],
                "document_provenance":"UNATTESTED_PRIVATE_STAGED_FILE",
                "document_publisher_authenticity_verified":False,
                "document_reviewed_by_professional":False,
                "all_scoring_clauses_verified":False,
                "issuer_requirements_verified":False,
                "document_can_grant_bid_authority":False,
                "keyword_hints_are_authoritative":False,
            }
            if item["content_format"]=="DOCX":
                excerpts,hints,truncated=_docx_excerpts(data)
                row.update({
                    "extraction_status":"UNTRUSTED_DOCX_TEXT_PREVIEW",
                    "private_untrusted_text_paragraphs":excerpts,
                    "candidate_keyword_paragraph_numbers":hints,
                    "content_truncated":truncated,
                })
            elif item["content_format"]=="PDF":
                row.update({
                    "extraction_status":"PDF_CUSTODY_ONLY_NO_APPROVED_TEXT_PARSER",
                    "private_untrusted_text_paragraphs":[],
                    "candidate_keyword_paragraph_numbers":{},
                    "content_truncated":False,
                })
            else:
                return hold
            results.append(row)
    except (OSError,KeyError,TypeError,ValueError,zipfile.BadZipFile,ET.ParseError,RuntimeError):
        return hold
    return {
        **_base(READY),
        "generated_at_utc":moment.astimezone(timezone.utc).isoformat(),
        "document_count":len(results),
        "documents":results,
        "docx_preview_count":sum(x["content_format"]=="DOCX" for x in results),
        "pdf_pending_extraction_count":sum(x["content_format"]=="PDF" for x in results),
        "human_review_matrix":_human_review_matrix(results),
        "unverified_review_gates_remaining":len(REQUIREMENTS),
        "verified_review_gates":0,
        "next_action":"OWNER_AUTHENTICATE_FILE_ORIGIN_THEN_INDEPENDENT_CONSULTANT_REVIEW_FULL_RFQ_AND_ATTACHMENTS",
    }


def write_private(root: Path, result: Mapping[str,Any]) -> Path:
    if result.get("status") not in (AWAIT,READY):
        raise ValueError("HELD_PREVIEW_CANNOT_BE_SAVED")
    root=Path(root).resolve(strict=True)
    folder=root/BASE
    target=root/OUT
    if (not _dir_safe(folder) or target.is_symlink()
        or (target.exists() and (
            not target.is_file() or stat.S_IMODE(target.stat().st_mode)!=0o600))):
        raise ValueError("UNSAFE_PRIVATE_CONTENT_PREVIEW")
    fd,temp=tempfile.mkstemp(prefix=".rfq-review-",suffix=".json",dir=folder)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            os.fchmod(f.fileno(),0o600)
            json.dump(result,f,indent=2,sort_keys=True)
            f.write("\n")
            f.flush();os.fsync(f.fileno())
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return target
